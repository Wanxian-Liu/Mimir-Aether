# IQ-34 验证

## 1. 全量 tier0

```bash
cd ~/src/MimirAether && ./run_ralph_tier0.sh 2>&1 | tee /tmp/iq34-tier0.log
tail -5 /tmp/iq34-tier0.log
```

**期望**：PASS ≥ 681，IQ-31/32/33 无新增失败。

## 2. 各粒独立验证

| 粒 | 验证命令 | 期望 |
|----|---------|------|
| IQ-31 | `grep 'from .world_model_spike' agent/agent_loop.py` | import 存在 |
| IQ-31 | `grep 'wm_prediction' agent/agent_loop.py` | 调用存在 |
| IQ-32 | `grep 'confidence < 0.5' agent/intent_predictor.py` | 分支存在 |
| IQ-32 | `python3 -m pytest tests/agent/test_intent_predictor.py -v` | 4 PASS |
| IQ-33 | `python3 -m pytest tests/agent/test_iq33_non_redundant_nudges.py -v` | 4 PASS |

## 3. Cursor 退回 Cursor

Cursor 合完后，本机刘哥 shell 重启 gateway 使之生效。
