# ENG-WF-06: 波次 1 收官

> **真源**：[`MIMIR_ENGINEERING_WORKFLOW.md`](../MIMIR_ENGINEERING_WORKFLOW.md) §4  
> **日期**：2026-06-02 · **Commit**：`d85d232`

---

## 执行概览

| ID | 任务 | Owner | 状态 | 证据 |
|:--:|------|-------|:----:|------|
| **ENG-WF-01** | systemd stop/disable | **刘哥** → Mimir代跑 | ✅ | `systemctl --user status mimiraether` → inactive/disabled · [eng-wf-ops-gateway.md](./eng-wf-ops-gateway.md) |
| **ENG-WF-02** | OPERATIONS §5 单 Owner | Mimir | ✅ | [`OPERATIONS_GATEWAY.md`](../OPERATIONS_GATEWAY.md) §5.1「单 Owner 纪律」· `7776171` |
| **ENG-WF-03** | 编造 spec | Mimir | ✅ | [`eng-wf-fabrication-spec.md`](./eng-wf-fabrication-spec.md) · 3 Acceptance 各带 pytest 验证 · `add63c3` |
| **ENG-WF-04** | 编造契约测 | Mimir | ✅ | [`test_eng_wf_fabrication_guard.py`](../tests/agent/test_eng_wf_fabrication_guard.py) · 3 tests PASS · tier0 684/4 · `14f8a56` |
| **ENG-WF-05** | tool result 优先级 | Mimir | ✅ | [`test_eng_wf_tool_result_priority.py`](../tests/agent/test_eng_wf_tool_result_priority.py) · 2 tests PASS · tier0 684/4 · `d85d232` |

## 编造 Acceptance 绿表

| Acceptance | 状态 | 验证命令 |
|:----------:|:----:|----------|
| **A-1** 无 tool_result 时检测编造 | ✅ | `pytest tests/agent/test_eng_wf_fabrication_guard.py::test_detects_fabrication_claim_without_tool_result -v` |
| **A-2** 有 tool_result 时不误报 | ✅ | `pytest tests/agent/test_eng_wf_fabrication_guard.py::test_allows_legitimate_tool_grounded_claim -v` |
| **A-3** 编造 nudge 不重复 | ✅ | `pytest tests/agent/test_eng_wf_fabrication_guard.py::test_fabrication_nudge_marker_differs_from_preemptive -v` |

## 最终 tier0

```text
4 failed, 684 passed
```
4 个 pre-existing L2/L3 失败，与基线一致。
