# ENG-WF-03: 编造（Fabrication）定义与验收标准

> **真源**：[`MIMIR_ENGINEERING_WORKFLOW.md`](../MIMIR_ENGINEERING_WORKFLOW.md) §4 ENG-WF-03  
> **日期**：2026-06-01 · **关联**：IQ-32（intent fallback）+ IQ-33（非重复 nudge）已合入 `a0dc323`

---

## 定义

**编造（Fabrication）**：Assistant 消息**声称已执行/已完成**某操作，但会话历史中**没有对应的 `role=tool` 消息**作为证据。

### 与「文字推迟」（text-only deferral）的区别

| 行为 | 例子 | 现有 Guard |
|------|------|-----------|
| **文字推迟** | "先看看 Playbook 当前状态。" | `intent_action_guard` ✅ 已拦截（`should_block_text_only_finish`） |
| **编造** | "已用 read_file 核对 §2c，差异如下：…" 但无 tool_call+tool_result | **未拦截** ❌ |

### 检测逻辑

```
用户消息含 grounded 关键词（playbook/对齐/勾选/跑脚本/执行） 
  AND assistant 回复含 "已"/"完成"/"完毕"/"核对" 等完成宣称
  AND 最近 N 条消息中无 role=tool
  → 疑似编造 → 触发重新验证 nudge
```

---

## Acceptance-1: 编造检测函数存在

```python
# tests/agent/test_eng_wf_fabrication_guard.py
def test_detects_fabrication_claim_without_tool_result():
    """Assistant 说「已核对」但没有 tool 消息 → 标记为编造"""
    ...
```

**验证命令**：`pytest tests/agent/test_eng_wf_fabrication_guard.py::test_detects_fabrication_claim_without_tool_result -v`

---

## Acceptance-2: 有 tool_result 时不误报

```python
def test_allows_legitimate_tool_grounded_claim():
    """Assistant 说「已核对」且有对应 role=tool 消息 → 不标记"""
    ...
```

**验证命令**：`pytest tests/agent/test_eng_wf_fabrication_guard.py::test_allows_legitimate_tool_grounded_claim -v`

---

## Acceptance-3: 编造触发 nudge（非重复，对齐 IQ-33）

当编造被检测到时，agent 注入一条 nudge 消息（含 `[fabrication-guard]` 标记），且该 nudge 与 preemptive nudge **不重复**（符合 IQ-33 契约）。

```python
def test_fabrication_nudge_not_redundant_with_preemptive():
    """编造 nudge 标记 ≠ preemptive nudge 标记 → 不重复"""
    ...
```

**验证命令**：`pytest tests/agent/test_eng_wf_fabrication_guard.py::test_fabrication_nudge_not_redundant_with_preemptive -v`

---

## 引用实现

- 现有 guard 函数：`agent/intent_action_guard.py` → `assistant_defers_or_fakes_completion()` 已含部分检测
- IQ-33 不重复契约测：`tests/agent/test_iq33_non_redundant_nudges.py`
- 注入位置：`agent/agent_loop.py` turn 0（与 IQ-31 WM 预测器同位置，nudge message 组装之后、模型调用之前）
