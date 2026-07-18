# Current Evolution Baseline

**Generated:** 2026-07-15
**Source:** Disk verification of repo + data

## Six Metrics (from MIMIR_IQ_EVOLUTION_DIRECTION.md §3.2)

| # | Metric | Status | Evidence |
|:-:|:-------|:------:|:---------|
| 1 | **Persistent memory (vector)** | ❌ | `persistent.json` — file only, no Weaviate/Chroma |
| 2 | **Hermes code gaps closed** | ✅ 5+ | dream_memory, context_compressor, memory_fence, sentinel, backup |
| 3 | **Tool API completions added** | ✅ 3+ | backup_before_write, sentinel, maybe_compact |
| 4 | **RL training run** | ❌ | Env configured (`rl_list_environments` shows Hermes track), never ran eval |
| 5 | **Pure agent shell available** | ✅ | `terminal` tool works, gateway PID 33395 active |
| 6 | **test_all pass rate** | ❌ | No `test_all.sh` script exists. Unit tests for memory_tool, dream_memory not tracked |

## Evaulation Run: 2026-07-18

| Metric | Result | Baseline (2026-05-26) | Pass? |
|:-------|:------:|:---------------------:|:-----:|
| like_hit_rate | **1.0** | 1.0 | ✅ |
| fts_hit_rate | **0.5** | 0.5 | ✅ |
| semantic_hit_rate | **1.0** | 1.0 | ✅ |
| 20 queries all hit | **true** | — | ✅ |
| Overall | pass: true | no regression | ✅ |

**Result: no regression from May 26 baseline. All recall metrics flat or even.**

## Additional Diagnostics

| Metric | Value |
|:-------|:-----:|
| Skills deployed | 32 |
| persistent.json size | ~50KB |
| MEMORY.md size | 6,204 B / 97 lines |
| USER.md size | 3,719 B / 22 entries |
| behavioral_constraints | 5 |
| Cross-session intent prediction | ✅ WM enabled (`MIMIR_WM_PREDICTOR=1`) |
| Distillation success | ✅ (59→20, sentinel working) |

## Next Evaulation: after 5 more sessions or when a major gap is closed

(whichever comes first)
