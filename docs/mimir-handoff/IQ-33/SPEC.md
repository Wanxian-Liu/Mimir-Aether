# IQ-33 技术规格

## 设计原则

不写"注入去重"的生产代码（那是 IQ-34 的事）。**只写测试**，证明当前逻辑在组合场景下不会过度重复。

## 文件：新文件 `tests/agent/test_iq33_non_redundant_nudges.py`

### 测试 1: preemptive search 已注入时，intent_predictor 不追加 "search first"

```python
def test_preemptive_satisfied_predictor_does_not_duplicate_search_hint():
    """
    模拟 core_loop 中 preemptive search 已注入 session context。
    此时 intent_predictor.predict_and_format("记得上次的bug吗")
    应返回 *不包含* "Prefer session_search" 的 context block。
    （因为 preemptive 层已经做了）
    """
    # 🚧 实现提示：
    # 方案 A：在 core_loop.py 中设标志，predict_and_format 读标志后跳过 search hint
    # 方案 B（推荐）：测试 `build_intent_context_block` 在特定条件下过滤 search 行
    # 本测试只是契约，具体实现 Cursor 决定
    assert True  # placeholder
```

### 测试 2: recall intent + recall 已满足时，不重复 "search sessions first"

```python
def test_recall_satisfied_no_duplicate_recall_hint():
    """
    当 cross-session-context 已包含检索结果时，
    build_intent_context_block(recall_prediction) 不应再含
    "search sessions or MEMORY.md first"。
    """
    assert True  # placeholder
```

### 测试 3: IQ-31 WM predictor 注入 prediction 后，intent_predictor 不覆盖

```python
def test_wm_prediction_and_intent_predictor_coexist():
    """
    agent_loop turn 0 先调用 world_model_spike.predict(...)
    然后 core_loop 调用 intent_predictor.predict_and_format(...)
    
    验证：两者都注入上下文，但 <intent-context> 和 <wm-prediction>
    不合并为同一段，互不覆盖。
    """
    assert True  # placeholder
```

### 测试 4: MIMIR_WM_PREDICTOR=0 时不重复

```python
def test_wm_predictor_off_no_extra_nudge():
    """
    仅 intent_predictor 激活时，输出与无 WM 时完全一致。
    """
    assert True  # placeholder
```

## 对生产代码的影响

| 来源 | 改动 | 行 |
|------|------|:--:|
| `tests/agent/test_iq33_non_redundant_nudges.py` | 新增 | ~+40 |
| 生产代码 | **不改** | 0 |

## 验收标准

```bash
cd ~/src/MimirAether
python3 -m pytest tests/agent/test_iq33_non_redundant_nudges.py -v
# 4 tests PASS (placeholders 通过后，Cursor 需填充真实断言)
```
