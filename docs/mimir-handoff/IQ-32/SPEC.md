# IQ-32 技术规格

## 改动 1: agent/intent_predictor.py

### 修改 `build_intent_context_block`（+5 行）

```python
def build_intent_context_block(prediction: IntentPrediction) -> str:
    lines = [
        "<intent-context>",
        f"intent={prediction.intent} complexity={prediction.complexity} "
        f"confidence={prediction.confidence:.2f}",
    ]
    # ★ 新增: 低置信度 fallback — 只输出基本信息，不强指导
    if prediction.confidence < 0.5:
        lines.append("(low-confidence prediction — treat as suggestion, not directive)")
        lines.append("</intent-context>")
        return "\n".join(lines)

    # 原有高置信度提示（不变）
    if prediction.prefer_session_search:
        lines.append(
            "Prefer session_search (or read_file) before answering from memory alone."
        )
    if prediction.intent in ("code", "debug", "ops"):
        lines.append("Grounded task: use tools in this turn; do not defer with text-only plans.")
    if prediction.intent == "recall":
        lines.append("User likely refers to prior work — search sessions or MEMORY.md first.")
    lines.append("</intent-context>")
    return "\n".join(lines)
```

**变化**：`confidence < 0.5` → 仅输出 `{intent, complexity, confidence}` + 免责声明，不注入偏好、不指定路由。

## 改动 2: tests/agent/test_intent_predictor.py（新文件）

新增文件 `tests/agent/test_intent_predictor.py`，覆盖：

```python
# 1. 高置信度 → 完整 intent-context
def test_high_confidence_full_context():
    pred = IntentPrediction(intent="code", complexity="complex", confidence=0.75,
                            prefer_session_search=True, block_cheap_route=True)
    block = build_intent_context_block(pred)
    assert "Grounded task:" in block
    assert "low-confidence" not in block

# 2. 低置信度 → 精简版
def test_low_confidence_lite_context():
    pred = IntentPrediction(intent="general", complexity="simple", confidence=0.4,
                            prefer_session_search=False, block_cheap_route=False)
    block = build_intent_context_block(pred)
    assert "low-confidence prediction" in block
    assert "Grounded task:" not in block

# 3. predict_and_format 返回正确传递 confidence
def test_predict_and_format_confidence():
    pred, block = predict_and_format("你好")
    assert pred is not None
    assert pred.confidence < 0.5
    assert "low-confidence" in block

# 4. MIMIR_INTENT_PREDICTOR=0 时跳过
def test_predictor_disabled(monkeypatch):
    monkeypatch.setenv("MIMIR_INTENT_PREDICTOR", "0")
    pred, block = predict_and_format("test")
    assert pred is None
    assert block == ""
```

## 不改的文件

| 文件 | 原因 |
|------|------|
| `agent/core_loop.py` | 只消费 `predict_and_format` 返回值，不改逻辑 |
| `agent/agent_loop.py` | 不涉及 |
