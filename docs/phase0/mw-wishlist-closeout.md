# MW 心愿单全线收官（2026-06-02）

## 任务对照表

| ID | 需求 | 产出 | 证据 |
|:--:|------|:----|:----:|
| **MW-00** | 验收 IQ-31/32/33/34 真源（勿重复） | ✅ 验收文档 | `docs/phase0/mw-00-iq31-34-verify.md` |
| **MW-01** | search_first_guard 接线审计 | ✅ 已接（3文件6点） | 42 tests PASS |
| **MW-02** | 并行只读工具分发（IQ-41） | ✅ `parallel_dispatcher.py` + agent_loop 接线 | 11 tests · tier0 692/4 |
| **MW-03** | 工具调度平台无关薄层 | ✅ `ToolDispatchContext` dataclass | 7 tests · tier0 692/4 |
| **MW-04** | 周期对话 nudge（IQ-40） | ✅ `MIMIR_NUDGE_INTERVAL` turn loop | 9 tests · tier0 692/4 |
| **MW-05** | IC 顾问空建议修复 | ✅ 目录过滤修复 + 宽搜索 + 非空 suggestion | 7 tests · tier0 692/4 |

## 终值

- tier0: **692/4**（4 个预先失败的 cross_session L2/L3，无新退化）
- 总新增测试: **34 tests**（MW-00～05）
- 总改动: **6 文件改动、2 新模块、5 新测试文件**

## 刘哥待办

1. （可选）env `MIMIR_PARALLEL_TOOLS=1` + gateway 重启 → 启用并行工具
2. （可选）env `MIMIR_WM_PREDICTOR=1` + gateway 重启 → 启用 WM 预测
3. （可选）env `MIMIR_NUDGE_INTERVAL=N`（默认 3，`0`=关）+ 重启
