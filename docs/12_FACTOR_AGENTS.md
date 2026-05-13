# 12 Factor Agents — MimirAether Alignment

Mapping MimirAether to the 12 Factor methodology for AI agents
(HumanLayer/ai-boost adaptation of 12factor.net).

## Alignment Table

| # | Factor | MimirAether | Status |
|:--|:--|:--|:--:|
| 1 | **One codebase, one agent** | Single repo (`MimirAether`), single identity (`SOUL.md`) | ✅ |
| 2 | **Explicit dependencies** | `requirements.txt` + `pyproject.toml` | ✅ |
| 3 | **Config in environment** | `get_env()` tool + `.env` + `OPENCLAW_*` vars | ✅ |
| 4 | **Backing services as resources** | Gateway, API server, OpenRouter — all via URLs/env | ✅ |
| 5 | **Build, release, run** | `git commit` (build) → `git push` (release) → Gateway restart (run) | ✅ |
| 6 | **Stateless processes** | State in `data/persistent.json`, not in memory | ✅ |
| 7 | **Port binding** | API server on `:18789`, Gateway on own port | ✅ |
| 8 | **Scale via process model** | `delegate_task` for fan-out; subagent for parallel work | ⚠️ |
| 9 | **Disposability** | Gateway crash recovery skill; fast restart | ✅ |
| 10 | **Dev/prod parity** | Same repo, same tools, same Gateway | ✅ |
| 11 | **Logs as event streams** | `logging` → stdout; `session_tracker` for structured events | ⚠️ |
| 12 | **Admin processes** | `scripts/` for maintenance; `run_ralph_tier0.sh` for CI | ✅ |

**Score: 10/12 fully aligned, 2 partial.**

## Gaps

| Factor | Gap | Mitigation |
|:--|:--|:--|
| 8 (Scale) | Single-agent by design; subagent only for task decomposition | Adequate for current scale |
| 11 (Logs) | session_tracker exists but immature (Phase XI) | Active development |

*Created: Phase XIV (2026-05-14). Source: HumanLayer/ai-boost 12-factor-agents.*
