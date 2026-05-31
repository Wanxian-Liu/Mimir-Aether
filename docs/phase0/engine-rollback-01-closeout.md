# ENGINE-ROLLBACK-01 closeout — evolution rollback guardrails (STAB-05)

> **Grain:** ENGINE-ROLLBACK-01 · Wave 15+ · §20.1 #1  
> **Baseline:** `bb238cf` (§20 queue v2) · logic **`7b6dfdc`** (STAB-05, 2026-05-25)  
> **Date:** 2026-05-28  
> **Verdict:** **No new runtime code** — STAB-05 already satisfies this grain.

## Problem (GH #26 · GATEWAY_STABILITY gstack P0 · #5 自修无回滚)

Skill self-evolution (FIX / DERIVED / CAPTURED) could write unsafe `SKILL.md` content with no backup or in-place restore when `skills_guard` blocks install → broken or malicious bundled skills.

## Evidence chain (production paths)

| Layer | Mechanism | Location |
|-------|-----------|----------|
| **Backup** | Pre-write copy to `$MIMIR_AETHER_HOME/data/evolution_backups/{skill}-{stamp}.SKILL.md.bak` | `agent/evolution_rollback.py` `save_skill_evolution_backup` |
| **FIX rollback** | Write → `skills_guard` scan → restore `prior_content` on block | `write_skill_md_guarded` |
| **DERIVED/CAPTURED** | Create dir + write → scan → `shutil.rmtree` on block | `create_skill_dir_guarded` / `remove_skill_directory` |
| **Pipeline wiring** | FIX/DERIVED/CAPTURED call guarded writers | `agent/skill_evolution.py` (`evolve_from_suggestions`) |
| **Ops doc** | STAB-05 summary + backup path | `docs/OPERATIONS_GATEWAY.md` §4.1 |
| **STAB-05** | GH #26 closed · `7b6dfdc` | `docs/GATEWAY_STABILITY_BACKLOG.md` |

## Backup & rollback paths

| Path | Purpose |
|------|---------|
| `$MIMIR_AETHER_HOME/data/evolution_backups/` | Timestamped pre-evolution `SKILL.md` backups |
| In-place restore | `write_skill_md_guarded` rewrites `SKILL.md` from `prior_content` when scan blocks |
| Dir removal | `create_skill_dir_guarded` removes new skill directory when DERIVED/CAPTURED fails scan |

## Tests (tier0)

| Test | Asserts |
|------|---------|
| `tests/agent/test_evolution_rollback_stab05.py` | FIX rolls back on dangerous content; backup on success; DERIVED removes dir on block; unit helpers |
| `tests/contract/test_horizon_engine_rollback_01.py` | Grain wiring + tier0 registration |

## Gateway ops

**No config change.** **No Gateway restart required** (agent-side skill evolution only; no gateway code in this grain).

## References

- `docs/GATEWAY_STABILITY_BACKLOG.md` — #26 · STAB-05  
- `docs/evolution_log.md` — STAB-05 row (`7b6dfdc`, 5 tests, tier0 267+2)  
- `docs/MIMIR_EXEC_BACKLOG.md` §15 STAB-05

## Verify

```bash
./run_ralph_tier0.sh
pytest -q tests/agent/test_evolution_rollback_stab05.py tests/contract/test_horizon_engine_rollback_01.py
```
