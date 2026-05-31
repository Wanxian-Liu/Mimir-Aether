# IQ-IDX-01 · 索引与 Q2 基线（2026-06-01）

> **轨**：IQ 5.5 Phase2 · Track 2a  
> **PR 意图**：`feat/iq-idx-01`（脚本 + gateway 双写修复 + closeout）

## 根因

- Gateway 仅写 JSONL；`state.db` 的 `sessions`/`messages` 长期为空 → [`session_search_usage_baseline.py`](../../tools/session_search_usage_baseline.py) 报 **total_sessions=0**。
- ③ 飞书复测（A06.1）**部分**：`session_search` 有调用但未命中 `ensure_single_gateway.sh` 叙事。

## 交付

| 项 | 状态 | 证据 |
|----|:----:|------|
| 调查 state.db vs JSONL | **PASS** | 54 个 `data/sessions/*.jsonl` vs 回填前 DB 空 |
| [`scripts/backfill_state_db_from_jsonl.py`](../../scripts/backfill_state_db_from_jsonl.py) | **PASS** | 生产回填：54 sessions · 5754 messages |
| [`scripts/seed_ops_gateway_single_instance_anchor.py`](../../scripts/seed_ops_gateway_single_instance_anchor.py) | **PASS** | `ops_gateway_single_instance_anchor.jsonl` |
| [`scripts/backfill_sessions_search.py`](../../scripts/backfill_sessions_search.py) | **PASS** | `sessions_search.db` 54 sessions · 5754 messages |
| Gateway 前向修复 | **PASS** | [`gateway/session.py`](../../gateway/session.py) `ensure_session` before `append_message` |
| 7d 基线 `total_sessions` | **PASS** | **17**（7 日窗）· 输出 `data/ops/session_search_baseline_7d.json` |
| 离线 `session_search` 锚点 | **PASS** | Top hit `ops_gateway_single_instance_anchor` 含 `ensure_single_gateway.sh` |
| tier0 | **PASS** | **674** tests（含 `test_backfill_state_db_from_jsonl`） |

## 飞书 ③ 复测

| 层 | 状态 | 说明 |
|----|:----:|------|
| **索引/检索基础设施** | **PASS** | 锚点 + search DB 可召回脚本名（见上） |
| **生产 DM 行为复测** | **PASS** | 刘哥 2026-06-01 发话「继续昨天 Gateway 单实例那件事」· traj `16e3735611f87e85` · step1 `session_search` 命中 `ops_gateway_single_instance_anchor` · 回复含 `ensure_single_gateway.sh` / 双实例 / nohup 根因 |

会话 JSONL：`~/.mimiraether/data/sessions/20260601_041448_b015fa37.jsonl`（04:14:58 轮）。详见 [`iqevo-30`](./iqevo-30-feishu-smoke-evidence.md) §「IQ-55 Phase2 ③」。

## 复验命令

```bash
export MIMIR_AETHER_HOME=~/.mimiraether
python3 scripts/seed_ops_gateway_single_instance_anchor.py
python3 scripts/backfill_state_db_from_jsonl.py \
  --sessions-dir "$MIMIR_AETHER_HOME/data/sessions" \
  --db "$MIMIR_AETHER_HOME/state.db"
python3 scripts/backfill_sessions_search.py
PYTHONPATH=$REPO_ROOT python3 -c "
from tools.session_search_usage_baseline import write_baseline_json; import json; print(json.dumps(write_baseline_json(), indent=2))
"
```

## 刻意未做

- 改 `SESSION_SEARCH` / `MIMIR_CROSS_SESSION_RAG` 生产默认
- 与 memory / WM / A06.x guard 混 PR
