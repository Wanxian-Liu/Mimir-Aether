# IQ-32 复核要点

1. **阈值选择**：0.5 是经验值。当前 `general` 返回 0.4，`chat` 返回 0.75（因为有正则匹配），所以 0.5 阈值只影响 `general` 和空消息，不影响已识别的 intent。如果后续调优可在代码顶部声明为 `_LOW_CONFIDENCE_THRESHOLD = 0.5`
2. **不破坏现有行为**：高置信度场景输出与原来完全一致（`build_intent_context_block` 只加了 `if confidence < 0.5: return` 前置分支）
3. **测试完整**：4 个测试覆盖高/低/disabled/端到端

## 已知未做

- 不涉及 LLM 分类器（B5 禁止）
- 不修改 `predict()` 的分类逻辑本身
- 不修改 `core_loop.py` 的消费逻辑

## 与 IQ-31 的关系

IQ-31 将 `world_model_spike.predict` 注入 agent loop，IQ-32 增强 `intent_predictor`。两者独立：
- IQ-31 是**外部**世界模型预测（context → intent suggestion）
- IQ-32 是**内部**意图预测器（user_message → intent routing guard）
- 两者都注入 `<intent-context>` / `<wm-prediction>` block，分别由各自 env 门控
