# IQ-32 验证

## 1. 单元测试

```bash
cd ~/src/MimirAether
python3 -m pytest tests/agent/test_intent_predictor.py -v 2>&1
```

**期望**：4 tests PASS

## 2. tier0 回归

```bash
cd ~/src/MimirAether && ./run_ralph_tier0.sh 2>&1 | tail -5
```

**期望**：无新增失败，PASS 数不低于基线（681）

## 3. 行为验证（手动）

```python
# 低置信度场景
from agent.intent_predictor import predict, build_intent_context_block
pred = predict("随便聊聊")
block = build_intent_context_block(pred)
print(block)
# 期望: 不含 "Grounded task:" 或 "Prefer session_search"
# 含: "low-confidence prediction"

# 高置信度场景
pred = predict("修复这个bug")
block = build_intent_context_block(pred)
print(block)
# 期望: 含 "Grounded task: use tools"
```

## 4. 回滚

撤销 SPEC.md 中的改动，恢复 `build_intent_context_block` 到原版。
