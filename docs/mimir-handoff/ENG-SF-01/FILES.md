# ENG-SF-01: FILES.md

## 改动文件（相对 repo root）

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `agent/agent_loop.py` | **修改** | 添加 preemptive search-first nudge 注入（13 行块）+ 3 个新 import |
| `scripts/search_first_audit.py` | **修改** | 审计内层循环跳过 `[search-first-guard]` 标记消息，避免 nudge 阻断搜索检测 |

## 新增文件

| 文件 | 说明 |
|------|------|
| `docs/mimir-handoff/ENG-SF-01/SUMMARY.md` | 交付包说明 |
| `docs/mimir-handoff/ENG-SF-01/VERIFY.md` | 验证证据 |
| `docs/mimir-handoff/ENG-SF-01/FILES.md` | 本文件 |
| `docs/mimir-handoff/ENG-SF-01/REVIEW.md` | 复核要点 |

## 未改动

- `gateway/`、`tools/`、`tests/`、`mimir_cli/`、`.env`、`data/persistent.json`
- `agent/search_first_guard.py` — 逻辑层未改，只给 agent_loop 加调用点
