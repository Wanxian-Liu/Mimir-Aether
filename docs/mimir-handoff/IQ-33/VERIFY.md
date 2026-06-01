# IQ-33 验证

## 1. 测试通过

```bash
cd ~/src/MimirAether
python3 -m pytest tests/agent/test_iq33_non_redundant_nudges.py -v
```

**期望**：4 tests PASS（placeholders 或真实断言均可）

## 2. tier0

```bash
./run_ralph_tier0.sh 2>&1 | tail -5
```

**期望**：无新增失败（纯测试文件）

## 3. 手动验证（Liu 可跳过）

```python
from agent.intent_predictor import predict, build_intent_context_block
from agent.world_model_spike import predict as wm_predict

# 同一消息走两个预测器
msg = "修复这个 bug"
ip = predict(msg)
wm = wm_predict({"user_message": msg})
print("intent_predictor:", build_intent_context_block(ip))
print("world_model_spike:", wm)
# 确认两者不互相覆盖或重复
```
