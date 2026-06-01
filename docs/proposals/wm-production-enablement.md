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
| 5 | 预测器升级为 **LLM 调用** | 新变量 `MIMIR_WM_LLM_PREDICTOR` | 🔴 高 | 步骤 4 |

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

### 步骤 5: LLM 预测器（高风险，提案级）

**需要新开发**：
- 用 LLM 调用替代规则匹配，输出结构化的 `Prediction`。
- 成本控制：只在 `intent != "chat"` 时调用。
- 新 env flag `MIMIR_WM_LLM_PREDICTOR`，**默认关**。

**不做**：详见前一方案 §6/§7 的明确不做清单。

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
