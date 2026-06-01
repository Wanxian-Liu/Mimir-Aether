# WM-B5：LLM 世界模型预测器 — 裁定保持现状（不实现）

> **状态**：**DEFERRED / 永久搁置除非新 ADR**  
> **裁定**：刘哥 **2026-05-19**（与 Cursor 分析一致）  
> **真源**：本文 + [`wm-production-enablement.md`](../proposals/wm-production-enablement.md) 步骤 5  
> **误开防护**：**禁止**新增 `MIMIR_WM_LLM_PREDICTOR`、**禁止**新建 `agent/llm_predictor.py` 接 turn0，除非刘哥书面撤销本文并更新 `iq17-liu-decisions.md` WM-Q5

---

## 1. 一句话裁定

**不做 WM-B5。** 保持 **规则** `world_model_spike`（步骤 4 · `MIMIR_WM_PREDICTOR`）+ 现有 VoE/意图/nudge 链；**不**在 turn0 再叠一次「用 LLM 猜意图」的 WM 专用 API。

---

## 2. 这不是刘哥原先想做的功能（常见混淆）

| 刘哥 / bridge 方向（ISSUES #16 · [`MIMIR_ISSUES.md`](../MIMIR_ISSUES.md)） | WM-B5 实际是什么 |
|--------------------------------------------------------|------------------|
| 并行工具、事件驱动、steer/followUp、会话分支、分层规划、**多模型按任务路由** | 在 **主 LLM 之前** 再调 **一次 LLM**，输出 `Prediction` 结构体 |
| 「Mimir 自己变强」，与飞书无关 | WM 研发线里的 **步骤 5 升级**，和 pi-agent **能力清单不对齐** |
| 工程上对应 **§13 MW-02/03、IQ-41** 等 | 对应 backlog 里 ~200 行 **`llm_predictor`**，易与 **IQ-31 已合的规则接线** 混为一谈 |

**IQ-31/32/33/34（`a0dc323`）= 规则预测器接 `agent_loop` + intent 低置信 fallback + 契约测 —— 这是 B4，不是 B5。**  
Mimir 说「手稿躺了 3 天」时，若 `main` 已含 `a0dc323`，应走 **MW-00 验收 + 开 `MIMIR_WM_PREDICTOR=1`**，而不是实现 B5。

---

## 3. 分析：为何边际意义不大

### 3.1 问题已被更便宜的路径覆盖

| 需求 | 已有实现 | B5 能多加什么 |
|------|----------|---------------|
| 猜用户要查历史 | `intent_predictor` + 规则 WM `_RECALL_HINT` + `search_first_guard` | 多一次 LLM，输出不稳定 |
| 猜要用哪些工具 | `skill_scenario_router`、tool schemas、preemptive `session_search` | 与 guard/nudge **叠层**风险 |
| 任务复杂→强模型 | `smart_model_routing` / provider 路由（方向 #6） | B5 不解决路由，只多一段 prompt |
| 会话后会学习 | VoE B1～B3、`AUTO_EVOLVE`、`post_close_analysis` | B5 不参与学习闭环 |
| 元认知 / 先 skill_view | SELF 链、BRAIN-11、`MIMIR_SKILL_ROUTE_NUDGE` | 不同机制；B5 不替代 |

在 **IQ 5.2→5.5** 路径上，文档与实测更缺的是：**先搜再答执行率**、**并行工具**、**周期 nudge**（§13 MW），不是「再一个 LLM 读心」。

### 3.2 成本与可观测性

- **每会话 turn0 +1 次 LLM**：延迟、token、失败模式（超时/坏 JSON）均高于规则版。
- **行为不可复现**：tier0 难锁飞书体验；回归要靠 rubric/人工，和 Parity 主线不对齐。
- **三层「意图」并存**：`intent_predictor`（常开）+ 规则 WM（可选）+ 若再开 LLM WM → prompt 噪声 ↑，而不是 IQ ↑。

### 3.3 规则 WM（B4）足够作为「建议层」

`world_model_spike.predict()` 设计为 **建议注入、非强制**（`wm-production-enablement` 步骤 4）。  
误判可关 env、可 log、可测 —— 满足「先要有数据再谈升级」。  
**在 B4 生产数据未验证前上 B5，无法归因「变好」来自 LLM。**

### 3.4 结论（Cursor 建议，刘哥采纳）

| 维度 | 判断 |
|------|------|
| 战略对齐 | ❌ 非 pi-agent/ISSUES#16 能力清单项 |
| IQ 边际 | 🟡 低（&lt;0.1 且难证） |
| 工程风险 | 🔴 中高（成本、叠层、维护） |
| 推荐 | **保持现状**；优先 §13 MW-02/04、VoE 步骤 1～4 观察 |

---

## 4. 保持现状 = 什么开着、什么永远不做

### 4.1 可以做（WM 阶梯，非 B5）

| 步骤 | env | 说明 |
|:----:|-----|------|
| 1 | `MIMIR_WM_VOE_LEARNING=1` | VoE 写 JSONL |
| 2 | `MIMIR_WM_VOE_RECALL=1` | 依赖 1 |
| 3 | `MIMIR_WM_VOE_REPLAN_CTX=1` | 依赖 1 |
| 4 | `MIMIR_WM_PREDICTOR=1` | **规则** `world_model_spike`，已合 IQ-31 |

### 4.2 不做（B5 清单）

- 新建 `agent/llm_predictor.py`（或等价）用 LLM 生成 `Prediction`
- env `MIMIR_WM_LLM_PREDICTOR`（**未定义、勿添加**）
- 用 LLM 输出 **替代** 规则 `predict()` 的默认路径
- 在「都研发了为什么不用」压力下 **跳过步骤 1～4 直接上 B5**

### 4.3 若将来真要「更聪明的 WM」

先满足 **全部**：

1. 步骤 1～4 已开 ≥7 天，且有 log/JSONL 证据  
2. 规则 WM 误判率可接受（或已收紧正则）  
3. 书面 **WM-Q5 撤销本文** + 成本上限（例如仅 `complexity=complex` 且规则 confidence 低）  
4. 与 `intent_predictor` 的 **优先级契约**（二选一或 cascade，禁止双 LLM 意图）

否则继续 **DEFERRED**。

---

## 5. 误开时的典型后果（备忘）

- 首包变慢；日 token 上升且难与主对话拆分计费  
- 与 `search_first` / `skill-route` / `intent_predictor` **重复建议**，飞书仍 0P/部分  
- 出问题时只能关 env，难区分是 WM-LLM 还是主模型退化  
- Mimir/Agent 误以为「P0 = 合 B5」，重复劳动或双轨实现  

---

## 6. 应优先做的（刘哥真正关心的能力）

见 [`MIMIR_WISHLIST_WORKFLOW.md`](../MIMIR_WISHLIST_WORKFLOW.md) §13：

- **MW-02**：并行只读工具（IQ-41）  
- **MW-03**：调度与平台解耦  
- **MW-04**：`MIMIR_NUDGE_INTERVAL`  
- **MW-05**：IC 顾问 fallback  

以及已有 **IntentPredictor 增强 MVP**（规则）、**多模型路由**、**事件驱动**（未立项则进 backlog，**不是 B5**）。

---

## 7. 登记与交叉引用

| 位置 | 更新 |
|------|------|
| [`iq17-liu-decisions.md`](./iq17-liu-decisions.md) | WM-Q5 = **不做** |
| [`iq17-cursor-backlog.md`](../proposals/iq17-cursor-backlog.md) | P1 WM-B5 指向本文 |
| [`MIMIR_IQ17_EXECUTION_PLAN.md`](../MIMIR_IQ17_EXECUTION_PLAN.md) | 「不做」含 B5 |
| [`MIMIR_TASK_QUEUE.md`](../MIMIR_TASK_QUEUE.md) §13 | 不含 B5 |

---

## 8. 修订日志

| 日期 | 摘要 |
|------|------|
| 2026-05-19 | 刘哥：非原先目标功能；Cursor 分析后裁定保持现状，防误开 |
