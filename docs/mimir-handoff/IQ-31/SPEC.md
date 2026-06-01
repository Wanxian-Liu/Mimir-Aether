# IQ-31 技术规格

## 改动：agent/agent_loop.py ~20 行

### 1. 在文件顶部 imports 加一行

```python
from .world_model_spike import predict as wm_predict, is_wm_predictor_enabled
```

### 2. 在 agent_loop.py 找到 cross-session/SystemPrompt 组装处

搜索 `_build_system_prompt` 或 `_build_cross_session_context`（或 `build_messages` 方法内首次构造 system message 的位置）。  
如果没有独立函数，选择 `run_conversation` 方法中首轮 LLM 调用**之前**、nudge message 组装**之后**的位置注入。

### 3. 注入预测（~10 行）

```python
# === WM Predictor: 规则级意图建议（env 门控，默认关） ===
if is_wm_predictor_enabled():
    context_snapshot = {
        "user_message": user_text_this_turn or "",
        "intent": intent or "",
        "objective": objective or "",
    }
    prediction = wm_predict(context_snapshot)
    if prediction.next_context_needs:
        cross_session_context.setdefault("wm_prediction", prediction)
        logger.debug("wm_prediction: %s", prediction)
```

### 4. 在 cross-session context 渲染时带上 `wm_prediction`

如果 cross-session context 已经有 key-value 渲染（例如 `cross_section_context` → `<cross-session-context>` block），增加：

```python
if hasattr(cross_session_context, "wm_prediction"):
    lines.append(
        f"WM prediction: intent={prediction.intent}, "
        f"needs={prediction.next_context_needs}"
    )
```

**注意**：`Prediction` 是 frozen dataclass，没有 `intent` 字段——需要从 predict 返回值中提取。建议：

```python
if prediction.next_context_needs:
    ctx_text = (
        f"<wm-prediction>\n"
        f"  expected_outcome: {prediction.expected_outcome}\n"
        f"  next_context_needs: {', '.join(prediction.next_context_needs)}\n"
        f"</wm-prediction>"
    )
    context_lines.append(ctx_text)
```

## 设计原则

1. **环境门控**：`MIMIR_WM_PREDICTOR=1` 才生效，默认**关**
2. **建议非强制**：即使 `next_context_needs` 非空，也不阻止 agent 做其他事
3. **空安全**：任何异常 → logger.warning + silent skip，不阻塞 conversation
4. **最小改动**：不重构现有结构，不引入新依赖

## 不改的文件

| 文件 | 原因 |
|------|------|
| `agent/world_model_spike.py` | 已有 119 行，功能完整，不改 |
| `tests/` | 已有单测 6 个，不改 |
| `agent/prompt_builder.py` | 不改 — 在 agent_loop 层注入，不影响 prompt_builder 逻辑 |
