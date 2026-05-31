# Wave A · IQ 5.5 closeout（2026-06-01）

> **拍板**：IQ-RUBRIC-55 ✅ · **出口**：rubric ≥5.5 **或** documented exception  
> **结论（Path A 结案）**：**维持 4.9** + **exception 续期** · **工程链已闭合** · A06.1 后飞书复测 **2 PASS + 1 部分**（Q2 行为改善，**仍不达 5.5**）

## 工程粒完成度

| ID | 状态 | 要点 |
|----|:----:|------|
| WA-A00～A06 | [x] | 基线 · eval · tool_quality · search 基线/审计 · prompt+audit 加固 |
| WA-A06.1 | [x] | 跨会话 **search-first 工具守卫**（`search_first_guard.py` · tier0 +9 tests） |
| WA-A07 | [x] | intent 接线证据 → [`wave-a-intent-nudge-evidence.md`](./wave-a-intent-nudge-evidence.md) |
| WA-A08 | [x] | memory nudge 已在 MimirAgentLoop；`.env` interval=10；生产 log 行 |
| WA-A09 | [x] | 探针 **00:07** 0P/1部分 · **A06.1 复测** ①② PASS ③部分 → [`iqevo-30`](./iqevo-30-feishu-smoke-evidence.md) |
| WA-A10 | [x] | `post_analysis evolution` log：**46** 行 applied=1 · ok=1 **24** · ok=0 **22**（~52%） |
| WA-A11 | [x] | rubric **4.9** 复评 → 本 closeout |
| WA-A12 | [x] | 本文档 |

## §1.5 终态

| # | 状态 |
|---|------|
| Q1 | **4.9** + exception（未达 5.5） |
| Q2 | **部分** — 离线 eval 优 · A06.1 后飞书 **2P+1部分**（① `94ab78b` ② `7f9b3e3b` ③ `cc8c544a` 行为 search-first、③ 召回未接上 ensure_single_gateway） |
| Q3 | **PASS** — evolution_eval 周常 155907Z |
| Q4 | **PASS** — tool_quality_weekly 已跑 |
| Q5 | **待验证** — feedback JSONL 仍缺 |
| Q6–Q7 | **PASS** |

## 未达 5.5 的原因（诚实 · 2026-06-01 Path A）

1. **#1 学习能力**：进化链 log ~52% ok；`memory` discover 仍报组件不可用（② 靠 add 落盘）。  
2. **#8 意图 + 召回**：guard 改善 **先搜再答**（①② PASS）；③ **索引/会话内容**未命中「单实例」线程，非再堆 guard 能解。  
3. **审计基线**：`session_search_baseline_7d` total=0（state.db）；历史 JSONL 义务句违例率仍高 — 抬分靠周常 eval + 索引/Q5，非 Wave A 工程粒。

## A06.1 飞书复测摘要（PR #39 · `1121d63`）

| # | 结果 | trajectory |
|---|:----:|------------|
| ① Wave A 结论 | **PASS** | `94ab78b400af988f` · step1=`session_search` |
| ② search-first 偏好 | **PASS** | `7f9b3e3b5469e892` · memory→session_search→memory add |
| ③ gateway 单实例续作 | **部分** | `cc8c544aef6815d8` · 3×session_search · 未引用 `ensure_single_gateway.sh` |

## 建议后续（非 Wave A 范围）

- **Q5**（优先）：对齐 `MIMIR_FEEDBACK_COLLECTOR` 与 gateway `.env`  
- **③ 内容（可选）**：补可检索 OPS 会话后再单点复测，**不**开 A06.x guard PR  
- **Wave B**：WM Phase0 spike（`world-model-evolution-plan.md`）· **禁止** 与 Horizon C / IQ guard 混 PR  
- **5.5 战役**：另立项（进化 ok 率 · memory · session 索引 · 意图 ML）— 见 `MIMIR_EXEC_BACKLOG.md` §20，**非** Wave A 续作

## 证据索引

- [`wave-a-behavior-report-20260531.md`](./wave-a-behavior-report-20260531.md)
- [`wave-a-execution-plan.md`](./wave-a-execution-plan.md)
- [`iq-scoring-rubric.md`](./iq-scoring-rubric.md)
- [`iqevo-31-search-first-audit.md`](./iqevo-31-search-first-audit.md)
- [`iqevo-30`](./iqevo-30-feishu-smoke-evidence.md) §「WA-A09 ①②③ 复测 · A06.1 后」
- Bridge §4 · **WA-A06.1** 行（`docs/MIMIR_LIU_CURSOR_BRIDGE.md`）
