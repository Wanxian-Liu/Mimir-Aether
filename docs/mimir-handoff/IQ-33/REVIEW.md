# IQ-33 复核要点

1. **纯测试**：不改一行生产代码。IQ-33 是**契约测**，暴露"可能重复"的风险，由 IQ-34 合入时决定是否修复
2. **Placeholder 是故意的**：Cursor 实现时需要根据实际模块接口填充真实断言。如果发现实现需要改生产代码，应在 IQ-34 或单独 PR 解决
3. **与现有测试的关系**：不影响 `test_world_model_spike.py`（6 个已有测试）、不影响 `test_intent_predictor.py`（IQ-32 新增的 4 个）

## 已知不做

- 本粒不改 `core_loop.py` / `agent_loop.py` / `intent_predictor.py` / `world_model_spike.py`
- 去重逻辑（如有需要）视测试结果在 IQ-34 决定
