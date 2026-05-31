# ADR-008: Evolution — canonical production path (D5-ADR)

> **Status:** Accepted (2026-05-19, D5-ADR engineering closeout)  
> **Scope:** backlog §6 **d5** · §20.3 **D5-ADR** · partial close GH **#21**  
> **Related:** ADR-001 (persistent single-writer) · ADR-003 (runtime home) · ADR-005 (execution trace SoT) · ADR-007 (ObservabilityBus defer) · [`M6_EVOLUTION.md`](../M6_EVOLUTION.md)

---

## Context

D17 / wiki audits (d5) flagged **parallel evolution stacks** without a declared production owner:

| Stack | Location | Risk if unconstrained |
|-------|----------|------------------------|
| Post-close SKILL writes | `agent/post_close_analysis.py` → `agent/skill_evolution.py` | **Intended** production path (E-009, IEVO, IQ-P3-11) |
| JEPA codebase analysis | `agent/self_evolution/` + `agent/jepa_session_hook.py` | Could be mistaken for production SKILL mutation |
| Mimicore three-ring | `mimicore/evolve/*` + skill `mimiraether-self_evolution` | Legacy Hermes/spring loop; stubs and low call rate |
| Batch learner | `scheduler/tasks/learn_and_evolve_8h.py` | Writes repo files outside Gateway guards |

Hermes embeds evolution in curator/background_review; Mimir uses a **structured** `SkillEvolutionEngine` (FIX / DERIVED / CAPTURED / DEPRECATE) — see [`hermes-comparison-detailed.md`](../hermes-comparison-detailed.md). That design choice is **not** reversed here; this ADR only names **which code path may write production skills** under `$MIMIR_AETHER_HOME`.

Prior gates already in force:

- **D5-1 / IEVO-01:** no `simulated:true` on production evolution paths ([`agent/evolution_audit.py`](../../agent/evolution_audit.py))
- **D5-2 / E-009:** single pathway `apply_evolution_from_analysis` → SKILL.md
- **D5-3 / IEVO-02:** tier0 evolution manifest
- **ADR-005:** ExecutionRecorder JSONL is analysis/evolution input SoT
- **Synthetic sessions:** tier0 IDs must not mutate production home ([`agent/synthetic_sessions.py`](../../agent/synthetic_sessions.py))

---

## Decision

### 1. Canonical production path — **Path A** only

**Authoritative automated evolution that writes or updates `SKILL.md` under the runtime skills tree** MUST go through:

```text
close_execution_pipeline
  → run_post_analysis_sync (MIMIR_AUTO_ANALYSIS=1)
  → apply_evolution_from_analysis (MIMIR_AUTO_EVOLVE=1)
  → apply_evolution_from_suggestions_async
  → agent/skill_evolution.py (SkillEvolutionPipeline)
  → $MIMIR_AETHER_HOME/skills/...
```

**Rules:**

| Rule | Detail |
|------|--------|
| Env gates | `MIMIR_AUTO_ANALYSIS` and `MIMIR_AUTO_EVOLVE` must be enabled for automated writes; default-off in new deploys until ops explicitly enables |
| Input trace | Post-analysis reads **ExecutionRecorder** JSONL per ADR-005; do not invent parallel evolution inputs |
| Guards | `skill_path_guard`, `evolution_rollback`, `evolution_audit`, `synthetic_sessions.evolution_allowed_for_session` |
| Actions | FIX / DERIVED / CAPTURED / DEPRECATE per `EvolutionAction`; DEPRECATE does not write SKILL (IQ-P3-11) |
| Home | Skills root via `mimir_constants.get_skills_dir()` or explicit `skills_root` on `EvolutionContext` — never default test artifacts into production home |

**No new Gateway or `agent/core_loop` hook may write skills without updating this ADR.**

### 2. Path B — JEPA (`agent/self_evolution`) — analysis only

| Item | Status |
|------|--------|
| Trigger | `schedule_post_close_jepa_cycle` when `MIMIR_JEPA_CYCLE=1` ( **default off** ) |
| Execution | `run_jepa_cycle_sync` uses `execute_callback=None` — **no file apply** in production hook |
| Role | Codebase risk / cost analysis for future human or ADR-gated work |
| Forbidden | Replacing Path A; writing `SKILL.md` from JEPA without a new ADR |

### 3. Path C — Mimicore / three-ring — non-default

| Item | Status |
|------|--------|
| Code | `mimicore/evolve/*`, skill [`mimiraether-self_evolution`](../../skills/mimiraether/mimiraether-self_evolution/), [`activate_self_evolution.py`](../../activate_self_evolution.py) |
| Classification | **Spring / experimental** per [`MIMIR_MIMICORE_SPRING_SCOPE.md`](../MIMIR_MIMICORE_SPRING_SCOPE.md) §3–4.2 |
| Allowed | Explicit human invocation, skill tool calls, maintenance scripts |
| Forbidden | Wiring into Gateway post-close as a second automatic SKILL writer; filling executor stubs and claiming production evolution without tier0 + M6 |

`agent/` and `gateway/` MUST NOT add default imports of `mimicore.evolve` for session-close evolution.

### 4. Path D — `learn_and_evolve_8h.py` — batch research

| Item | Status |
|------|--------|
| Role | Offline Hermes-topic learning script; **not** Gateway evolution SoT |
| Forbidden | Treating its JSON log or file writes as production evolution metrics (ok%, M6) without separate ADR |

### 5. Relationship to ADR-001 (persistent.json)

Skill evolution writes **`SKILL.md` under `skills/`**, not `persistent.json` segments. Any future evolution that touches `persistent.json` MUST use the **MemoryWriteFacade / single-writer** pattern (ADR-001, ENGINE-P3W-01) — not a second RMW path from mimicore or JEPA.

### 6. Relationship to Hermes

Mimir keeps the **standalone** `skill_evolution` module for structured actions and confirmation/retry. Parity work should align **behavior** (when to evolve, audit), not merge mimicore three-ring into Path A.

---

## Consequences

### Positive

- Operators and tier0 tests share one answer for “what evolved production skills?”
- Closes **D5-ADR**; d5 table **6/6** without expanding mimicore stubs.
- GH **#21** scope for ADR is satisfied; wide KPI metrics remain icebox.

### Negative / follow-ups

- Production **ok%** (post_analysis `ok=1`) is a **runtime evidence** problem, not solved by this ADR — see [`iq-55-phase3-closeout.md`](../phase0/iq-55-phase3-closeout.md).
- Retire or document unused mimicore evolve modules — separate chore (extraction boundary design).
- **Contract:** `tests/contract/test_d5_adr_evolution_canonical.py` guards ADR presence and canonical keywords.

---

## Verification

```bash
./run_ralph_tier0.sh   # includes test_d5_adr_evolution_canonical
rg 'apply_evolution_from_analysis|SkillEvolutionPipeline' agent/execution_pipeline.py agent/post_close_analysis.py
```

---

## Approval (§20.3)

| Role | Decision | Date |
|------|----------|------|
| Engineering (Cursor) | Path A canonical; B/C/D non-default as above | 2026-05-19 |
| 刘哥 | Accept ADR-008 for production policy | _pending sign-off_ |

---

## References

- [`docs/phase0/d5-adr-closeout.md`](../phase0/d5-adr-closeout.md)
- [`docs/phase0/p2-long-iev0-closeout.md`](../phase0/p2-long-iev0-closeout.md)
- `agent/execution_pipeline.py`, `agent/post_close_analysis.py`, `agent/skill_evolution.py`
- [`docs/MIMIR_MIMICORE_SPRING_SCOPE.md`](../MIMIR_MIMICORE_SPRING_SCOPE.md)
