# IQ-EVO-31 / Gate A3 — search-first 违例审计

**Date:** 2026-05-26  
**方法：** `scripts/search_first_audit.py` · 最近 JSONL 中「应回忆」类 user 句 → 检查下一 user 前是否 `session_search`  
**数据源：** `$MIMIR_AETHER_HOME/data/sessions/*.jsonl`（`state.db` 当前无行，以 JSONL 为准）

## 汇总

| 指标 | 值 |
|------|-----|
| 候选句（全库） | 317 |
| **抽样** | **10** |
| 合规（先 search 或明确引用搜索结果） | **2** |
| 违例 | **8** |
| **违例率** | **80%** |

> 说明：许多「之前/继续」句实为**当前窗口**上下文或 persistent 记忆，非跨会话回忆；prompt 要求偏严时仍计违例。Wave 6 目标是**降低**该比例，非一夜归零。

## 抽样表（10 条）

| # | 会话文件 | 用户句（摘要） | 先 search? | 证据 |
|---|----------|----------------|:----------:|------|
| 1 | `20260526_185834_2165a33b.jsonl` | 我们之前聊的没有记忆了对吧 | N | 用 persistent 解释，未调工具 |
| 2 | 同上 | 找昨天世界模型相关工作/论文 | N | 未在 JSONL 见 tool 记录 |
| 3 | 同上 | 论文启发 + 自研世界模型想法 | **Y** | turn 内 session_search |
| 4 | `20260526_171857_b84a2d2e.jsonl` | 我们之前聊的没有记忆了对吧 | N | 同上 |
| 5 | `20260526_100850_2ac778be.jsonl` | 继续入库并检查 | N | 任务型，非跨会话 |
| 6 | 同上 | 上次是多久前 | N | 未 search |
| 7 | 同上 | wiki 能解决这件事么 | N | 未 search |
| 8 | 同上 | 查根因（TRUNCATE） | N | 用工具链非 session_search |
| 9 | 同上 | **查历史，和世界模型相关的论文** | **Y** | IQ-EVO-02 验收句；回复含搜索结果 |
| 10 | 同上 | Backlog 还能做什么 / 科研世界模型 | N | 未 search |

机器可读：`iqevo-31-search-first-audit.json`
