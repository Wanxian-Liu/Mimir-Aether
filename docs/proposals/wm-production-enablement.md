# 世界模型生产启用提案

> **问题**：WM Phase 0 + Phase 1.1 代码已合、单测通过（tier0 665）、closeout 有文档，但全部 `MIMIR_WM_*` env 默认 0，**生产行为与 spike 前完全一致**。  "都研发了为什么不用。"
>
> **目标**：分步安全启用，每步有回滚能力。

---

## 步骤总览

| 步骤 | 什么 | `MIMIR_*` 变量 | 风险 | 依赖 |
|:----:|------|:-------------:|:----:|:----:|
| 1 | `degeneration_guard` 的 surprise → **JSONL + learned_surprises 写入** | `MIMIR_WM_VOE_LEARNING=1` | 🟢 低 | — |
| 2 | 同场景第二次 **不 surprise**（recall） | `MIMIR_WM_VOE_RECALL=1` | 🟢 低 | 步骤 1 |
| 3 | surprise 时 **学习上下文注入 replan** | `MIMIR_WM_VOE_REPLAN_CTX=1` | 🟡 中 | 步骤 1 |
| 4 | 预测器 **接 agent_loop**（规则级→intent/skill_router） | `MIMIR_WM_PREDICTOR=1` | 🟡 中 | 步骤 1~3 |
| 5 | 预测器升级为 **LLM 调用** | ~~`MIMIR_WM_LLM_PREDICTOR`~~ **不实现** | 🔴 | **搁置** — 见下文 |

> **步骤 5 裁定（2026-05-19）**：**保持现状，不做。** 全文 [`docs/phase0/wm-b5-llm-predictor-deferred.md`](../phase0/wm-b5-llm-predictor-deferred.md)。非刘哥原先要的 pi-agent 能力；IQ 边际低；勿与步骤 4（规则 · IQ-31）混淆。

---

## 步骤详情

### 步骤 1: VoE 学习启用（低风险）

**现状**：`degeneration_guard.run_checks` 已接 `expected_vs_actual` hook；`MIMIR_WM_VOE_LEARNING=1` 时触发 `record_surprise_event` → 写 `surprise_events.jsonl` + `learned_surprises.json`。

**启用**：`~/.mimiraether/.env` 加一行 `MIMIR_WM_VOE_LEARNING=1`

**验证**：
```bash
grep 'SURPRISE_DETECTED' ~/.mimiraether/logs/agent.log | tail -3
ls -la ~/.mimiraether/data/wm_phase0/surprise_events.jsonl
```

**风险**：写入失败只 `logger.warning`，不阻塞 replan。磁盘写可忽略（JSONL append 仅当 surprise 触发）。

**回滚**：删除 env 行 → gateway 重启。

---

### 步骤 2: VoE Recall 启用（低风险）

**依赖**：步骤 1 已开（需要 `learned_surprises.json` 有数据才能 recall）

**启用**：`MIMIR_WM_VOE_RECALL=1`

**行为**：`lookup_learned_surprise(expected, actual)` 命中 → 返回 `CLEAN`，**不** append JSONL，**不**触发 `SURPRISE_DETECTED`。

**验证**：同一 session 内复现相同 `(expected, actual)` pair 两次 → 第一次 surprise，第二次 CLEAN（log 行含 `recall_clean`）。

**风险**：false positive 抑制 = 可能错过真正意外。但 recall 是**精确匹配 `(expected, actual)` 字符串对**，误命中概率低。

---

### 步骤 3: Replan 学习上下文（中风险）

**依赖**：步骤 1（需要 learning 事件有内容）

**启用**：`MIMIR_WM_VOE_REPLAN_CTX=1`

**行为**：surprise 时 `report.details["wm_learning_context"]` = 学习事件摘要。replan 函数可读此字段带额外上下文重规划。

**风险**：replan 上下文可能让 prompt 变长、引入噪声。需观察 token 增量与 replan 质量。

**验证**：触发 surprise 后，replan 调用 log 含 `wm_learning_context` 字段。

---

### 步骤 4: 预测器接 agent_loop（中风险）

**现状**：`world_model_spike.predict(context_snapshot)` 返回 `Prediction(next_context_needs, applicable_skills, expected_outcome)`。**未被任何 caller 调用**——纯单元测试覆盖。

**需要改动**：在 `prompt_builder.py` 或 `agent_loop.py` 首轮调用 `predict()`，将 `next_context_needs` 注入 system prompt / cross-session 上下文。

**最小改动方案**（~20 行）：

```python
# 在 agent_loop.py 或 prompt_builder.py
from agent.world_model_spike import predict, is_wm_predictor_enabled

if is_wm_predictor_enabled():
    prediction = predict(context_snapshot)
    if prediction.next_context_needs:
        context["wm_prediction"] = prediction
```

**风险**：规则预测器可能误判 intent（如 recall 关键词误触发）。低风险因为注入的是**建议而非强制**。

**验证**：log 出现 `wm_prediction: {intent, next_context_needs, applicable_skills}`。

---

### 步骤 5: LLM 预测器 — **不实现（WM-B5 · 已裁定）**

> **真源**：[`docs/phase0/wm-b5-llm-predictor-deferred.md`](../phase0/wm-b5-llm-predictor-deferred.md)  
> **刘哥（2026-05-19）**：这不是之前想做的功能；若无特别大意义则保持现状。

**原提案（仅供考古，勿实现）**：

- 用 LLM 调用替代/增强规则 `world_model_spike.predict()`，输出结构化 `Prediction`。
- 新 env `MIMIR_WM_LLM_PREDICTOR`（**禁止添加**）。

**为何不做（摘要）**：

1. **目标错位**：刘哥要的是并行工具、事件驱动、steer、多模型路由等（ISSUES #16 / §13 MW），不是 turn0 再多一次「LLM 读心」。
2. **与 IQ-31 混淆**：步骤 4 / `a0dc323` 已是**规则**接线；「合 handoff」≠ B5。
3. **边际低**：已有 `intent_predictor`（规则）、`search_first_guard`、`skill_scenario_router`、VoE B1～B3；再叠 LLM WM 易 **nudge 打架**、难复现、tier0 锁不住行为。
4. **成本/延迟**：每会话多一次 API；应先观察 `MIMIR_WM_PREDICTOR=1`（规则）≥7 天再议任何升级。
5. **优先替代**：§13 **MW-02** 并行工具、**MW-04** 周期 nudge、VoE 步骤 1～3、开规则预测器 env。

**误开后果**：token↑、首包变慢、与现有意图层重复、难归因退化。

**若未来重启**：须撤销 deferred 文档 + `iq17-liu-decisions` WM-Q5 + 成本上限 + 与 `intent_predictor` 的 cascade 契约。

---

## 推荐顺序

```
本周（步骤 1 + 2）→ 观察 3 天 → 下周（步骤 3）→ 观察 → 步骤 4（需最小代码改动）
                                     ↘ 步骤 5 待拍板
```

步骤 1 和 2 是**纯 env 开关，零代码改动**，随时可开可关。

---

## 决策问题（刘哥）

| # | 问题 | 选项 |
|:-:|------|------|
| Q1 | 是否先开步骤 1（VoE 学习）？ | 🫸 开 / 暂缓 |
| Q2 | 如果步骤 1 稳定 3 天，是否自动进行步骤 2？ | 自动 / 每步问我 |
| Q3 | 步骤 4（预测器接线）需要 ~20 行代码改动，是否批准？ | 批准 / 先只开 env 开关 |
