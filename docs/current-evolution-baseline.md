# Current Evolution Baseline

**Generated:** 2026-07-19
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
| Skills deployed | 26 |
| persistent.json size | ~50KB |
| MEMORY.md size | 6,204 B / 97 lines |
| USER.md size | 3,719 B / 22 entries |
| behavioral_constraints | 8 |
| Cross-session intent prediction | ✅ WM enabled (`MIMIR_WM_PREDICTOR=1`) |
| Distillation success | ✅ (59→20, sentinel working) |

## Next Evaulation: after 5 more sessions or when a major gap is closed

(whichever comes first)

## Closed Gaps Since Baseline

| Domain | Previous State | Current State |
|:-------|:--------------|:--------------|
| **Distillation** | 16 rounds of 0% success — claimed success without disk verification | ✅ 100% stable — sentinel mechanism prevents cache overwrite, verified by `read_file` before reporting |
| **Memory compaction** | No auto-compaction — MEMORY.md could bloat to 99% capacity | ✅ `_maybe_compact()` auto-triggers at 80% capacity, dedup + truncate long entries |
| **Write protection** | No `.bak` before write — test data overwrote production MEMORY.md | ✅ `_backup_before_write()` runs on every `save_to_disk()` |
| **Verification discipline** | "I think it worked" — no disk read before reporting | ✅ Anti-Rationalization Table in verification skill — 8 excuses pre-rebutted |
| **Behavioral constraints** | 3 rules | ✅ 8 rules — added JSON-read-structure-first, >3 retries→fail, SkillOpt rejection buffer, over-verification detection, verify-before-report guard |
| **Self-evolution** | No failure clustering — `analyze_gaps()` only monitored CPU/memory | ✅ 4 failure types: key_not_injected / os_replace_skipped / path_not_found / verification_skipped |
| **Verify-before-report guard** | Guard script existed only as a claim — no file on disk, metadata `{}` | ✅ `verify_before_report_guard.py` (70 lines) created at `scripts/`, metadata injected with 8 fields to `persistent.json` |

## 3/6 Open Gaps (unchanged)

These metrics from the original baseline remain open — no progress made since July 15:

1. ❌ **Vector memory** — still file-only `persistent.json`, no Weaviate/Chroma
2. ❌ **RL training run** — env configured, never executed
3. ❌ **test_all pass rate** — no `test_all.sh` exists
