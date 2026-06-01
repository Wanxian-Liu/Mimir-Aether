# ENG-PI06-01: FILES.md

## 改动文件（相对 repo root）

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `tests/conftest.py` | **修改** | 追加 FauxLlmProvider 类、MimirHarness dataclass、create_mimir_harness()、harness fixture。保留原有生产日志隔离逻辑 |
| `tests/tools/test_session_search_usage_baseline.py` | **修改** | 追加 2 个 harness 风格测试（`test_baseline_counts_sessions_with_search`、`test_harness_faux_llm_provider`）；原测试改名为 `_original` 后缀保留 |
| `tests/tools/test_mimir_ops_tool.py` | **修改** | 追加 1 个 harness 风格测试（`test_session_reset_pending_roundtrip`）；原测试改名为 `_original` 后缀保留 |

## 新增文件

| 文件 | 说明 |
|------|------|
| `docs/mimir-handoff/ENG-PI06-01/SUMMARY.md` | 交付包说明 |
| `docs/mimir-handoff/ENG-PI06-01/VERIFY.md` | 验证证据 |
| `docs/mimir-handoff/ENG-PI06-01/FILES.md` | 本文件 |
| `docs/mimir-handoff/ENG-PI06-01/REVIEW.md` | 复核要点 |

## 未改动

- `agent/`、`gateway/`、`tools/`、`mimir_cli/` — 本次只改 `tests/`
- `.env`、`data/persistent.json` — 未提交
