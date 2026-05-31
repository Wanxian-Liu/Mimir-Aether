# IQ-EVO-31 / Gate A3 — search-first 违例审计

**Date:** 2026-05-31 (WA-A06 refresh)  
**方法：** `scripts/search_first_audit.py` · 最近 JSONL 中「应回忆」类 user 句 → 检查下一 user 前是否 `session_search`  
**数据源：** `$MIMIR_AETHER_HOME/data/sessions/*.jsonl`

## 汇总

| 指标 | 值 |
|------|-----|
| 候选句（全库 · 宽匹配） | 528 |
| **raw 抽样违例率** | **100%**（10/10） |
| **filtered 候选（跨会话义务）** | **102** |
| **filtered 抽样违例率** | **100%**（10/10） |

> **WA-A06**：审计增加排除类（粘贴块 / 任务续作 / Bridge 写入 / 同会话「刚刚聊」/ 泛 WM 讨论等）；prompt 收窄为**显式**跨会话时才 MUST `session_search`。  
> 最新 raw 抽样 **9/10 已排除**（假阳）；filtered 样本仍为真跨会话义务（如「在之前我们俩有一个学习模式…封成技能了吗」）且 **均未 search**。

## 排除类（filtered 不计）

| exclude_reason | 含义 |
|----------------|------|
| `task_continuation` | 继续离席/入库等当前任务 |
| `fresh_session_continue` | /new 后当前窗 |
| `user_paste_block` | 长粘贴 / ASCII 块 |
| `bridge_write_task` | 写入 Bridge |
| `user_provides_material` | 用户刚提供新材料 |
| `topic_discussion_no_recall_ask` | WM 讨论无显式查历史 |
| `same_session_recall` | 刚刚聊 / 刚才说（同会话） |
| `same_session_synthesis` | 综合之前发的（当前窗） |
| `broad_recall_not_explicit` | 宽匹配但无显式跨会话词 |

## 7d session_search 基线（WA-A04）

见 `~/.mimiraether/data/ops/session_search_baseline_7d.json` · **total_sessions=0**（state.db 窗内无行）

## filtered 抽样（10 条 · 2026-05-31）

| # | 用户句（摘要） | 先 search? | exclude |
|---|----------------|:----------:|---------|
| 1 | 在之前我们俩有一个学习模式…封成技能了吗 | N | — |
| 2 | 飞书错误认知来自哪里…Memory/Soul | N | — |
| 3 | 查历史 IR-…（若出现在样本中） | — | — |

（完整 10 行见 `iqevo-31-search-first-audit.json` → `filtered_rows`）

机器可读：`iqevo-31-search-first-audit.json`
