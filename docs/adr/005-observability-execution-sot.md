# ADR-005: Observability — execution trace source of truth (SoT)

> **Status:** Accepted (2026-05-25)  
> **Scope:** Wave E **IEVO-03** · D6-1 · partial close GH **#22** (icebox class)  
> **Related:** ADR-003 (runtime home) · E-006/E-007 (monitor + recorder isolation) · **D6-2** ObservabilityBus → **deferred**

---

## Context

MimirAether records agent runs through several overlapping mechanisms (D17 / EV-L13 audit):

| Mechanism | Storage | Primary consumer |
|-----------|---------|------------------|
| **ExecutionRecorder** | `$MIMIR_AETHER_HOME/data/trajectories/YYYY-MM-DD/<session_id>.jsonl` | `execution_pipeline` → post-analysis → skill evolution |
| **SessionTracker** | `$MIMIR_AETHER_HOME/data/sessions/sessions.db` (SQLite) | Ops queries, token/tool aggregates, `/health` inputs |
| **monitor** | `$MIMIR_AETHER_HOME/data/monitor_alerts.json` | Sliding-window tool error rate (E-006) |
| **InsightsEngine** | SessionDB or in-memory | LLM usage metrics in agent loop |
| **trajectory.py** | `$MIMIR_AETHER_HOME/data/trajectories/*.jsonl` (aggregate filenames) | ShareGPT export / offline tooling |
| **core_loop._save_trajectory** | `{git_repo}/trajectory/trajectory_*.jsonl` | Legacy opt-in (`save_trajectories`); **not** runtime home |

Without a declared SoT, operators and evolution code cannot answer: *which file is authoritative for “what did the agent do on this session?”*

---

## Decision

### 1. Canonical SoT — **ExecutionRecorder** (per session JSONL)

**Authoritative trace for a completed or in-flight agent session** is the append-only JSONL file created by `agent.execution_recorder.ExecutionRecorder` and wired through `agent.execution_pipeline`:

- **Path:** `get_mimir_data_dir() / "trajectories" / "<UTC-date>" / "<session_id>.jsonl"`
- **API entry:** `start_execution_pipeline()` → `record_tool_call()` → `close_execution_pipeline()` → `trajectory_path` in the close result
- **Record types:** `session_start`, `tool_call`, `agent_action`, `analysis` (structured; see `execution_recorder.py`)
- **Downstream:** `format_trajectory_for_analysis()`, `SkillEvolutionPipeline`, `tests/agent/test_evolution_loop_integration.py`

**Rule:** New features that need a full session tool trace for analysis, evolution, or audit MUST read this JSONL (or the in-memory `ExecutionRecorder` before `close()`), not invent a parallel write path.

### 2. Derived / aggregate stores (not SoT)

| Store | Role | May diverge from SoT? |
|-------|------|------------------------|
| **SessionTracker** (`sessions.db`, `tool_calls` table) | Fast SQL aggregates, session lifecycle events | Yes — fed from `record_tool_call()` best-effort; used for dashboards, not evolution prompts |
| **monitor** | Ephemeral window + `monitor_alerts.json` | Yes — health signals only |
| **InsightsEngine** | Token/cost metrics via SessionDB | Yes — billing/usage, not tool-level trace |
| **trajectory.py** (`trajectory_samples.jsonl`) | ShareGPT-shaped **batch** export | Yes — legacy Hermes shape; do not treat as pipeline SoT |
| **trajectory_compressor.py** | Offline compression of JSONL dirs | Reads files; does not define SoT |

These layers MUST NOT be the **only** persistence for evolution-altering decisions. If SessionTracker write fails, the JSONL SoT still holds.

### 3. Legacy paths (deprecated for new work)

| Path | Status |
|------|--------|
| `{repo_root}/trajectory/trajectory_*.jsonl` (`core_loop._save_trajectory`) | **Legacy** — repo-relative, bypasses `MIMIR_AETHER_HOME`; disable for new deploys (`save_trajectories=False` default). Migration: route through ExecutionRecorder or explicit export from SoT JSONL. |
| `OPENCLAW_TRAJECTORY_DIR` override on `trajectory.get_trajectory_dir()` | **Legacy env** — prefer `MIMIR_AETHER_HOME`; document-only until removal (ADR-003 sunset). |

**No new code** may add a third runtime trajectory root under `~/.openclaw` or the git checkout.

### 4. D6-2 ObservabilityBus

**Deferred** — see **[ADR-007](./007-observability-bus-defer.md)** (OBS-B1-01, 2026-05-26). Current wiring: `execution_pipeline.record_tool_call()` fans out synchronously with fail-open `try/except` per sink. No separate bus module.

### 5. Implementation alignment (IEVO-03)

`execution_recorder._get_trajectory_dir()` MUST use `mimir_constants.get_mimir_data_dir() / "trajectories"` (same tree as ADR-003 home), not ad-hoc `os.getenv("MIMIR_AETHER_HOME")` duplication.

---

## Consequences

### Positive

- Evolution pipeline, tier0 tests, and ops runbooks share one trace path.
- Partial close of D6 icebox: **D6-1** satisfied; **D6-2/D6-3** remain backlog.

### Negative / follow-ups

- **Unify** `trajectory.py` aggregate files with per-session JSONL layout — separate chore (not IEVO-03).
- **Retire** `core_loop._save_trajectory` repo-relative writes — needs product flag audit.
- **Contract:** `tests/contract/test_observability_sot_ievo03.py` guards ADR presence and recorder path resolver.

---

## Verification

```bash
./run_ralph_tier0.sh   # includes test_observability_sot_ievo03
rg 'trajectory_path|ExecutionRecorder' agent/execution_pipeline.py
```

---

## References

- [`path-contract.md`](../path-contract.md) — three roots
- [`MIMIR_EV_L_INDUSTRIAL_LEARNING.md`](../MIMIR_EV_L_INDUSTRIAL_LEARNING.md) §13
- `agent/execution_recorder.py`, `agent/execution_pipeline.py`, `agent/session_tracker.py`, `agent/monitor.py`
- E-007 `tests/agent/test_e007_evolution_security.py` (recorder session isolation)
