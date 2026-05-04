# 独立学习：Agent 主循环与工具调用链

| 字段 | 值 |
|------|-----|
| 日期 | 2026-05-04 |
| 里程碑 | C（阶段 3） |
| 对照矩阵 | [hermes_mimir_behavior_matrix.md](../hermes_mimir_behavior_matrix.md) **H04、H05、H06、H19** |
| pytest 映射 | [ralph_parity_testmap.md](../ralph_parity_testmap.md)（Agent / G2 / G3） |

---

## 1. 范围与非目标

**范围**

- Mimir 侧：**`agent/core_loop.py`** 中 **`MimirAetherAgent`** 的对话主路径、工具调度、与 **Tier-1 E2E**（桩 LLM）的对照语义。
- Hermes 侧：以矩阵 **H19** 为锚 — `HermesAgentLoop` + `MockServer`（上游 `tests/run_agent/test_agent_loop.py`），**HERMES_REF** 见行为矩阵 §0。

**非目标**

- 不展开真模型长链（OpenRouter）；真链对齐仍以 Hermes `test_agent_loop_tool_calling.py` 为单独验收面。
- 不重构 `core_loop.py` 体量；本报告仅析构与建议。

---

## 2. Mimir 关键代码路径

| 层次 | 路径 | 说明 |
|------|------|------|
| 主循环入口 | `agent/core_loop.py` | `MimirAetherAgent.run_conversation`（异步）；集成 prompt、LLM 端口、工具执行、预算/恢复 |
| 类型与消息 | `agent/types.py` | `Message`、`ToolCall`、`ToolResult` 等 |
| 桩级 E2E | `agent/test_tier1_e2e_agent.py` | Gate3：**H19** 证据列指向此处 |
| 工具/错误分支 | `agent/test_agent_loop.py`、`agent/test_agent_loop_edge.py` | **H04、H05** |

**数据流（ASCII）**

```
User messages → run_conversation → LLM port → (optional) tool_calls
      → tool dispatch → ToolResult → append to conversation → next turn / stop
```

---

## 3. 与 Hermes（矩阵）对齐结论

- **H04 / H05**：Mimir 用 **`agent/test_agent_loop*.py`** 覆盖未知工具、JSON 错、max_turns 等；与矩阵 **OK** 一致。
- **H06**：多工具单轮顺序与 `role=tool` 回写 — 矩阵已注 Hermes `environments/agent_loop.py` 串行语义；Mimir 侧以 **`test_multi_tool_in_single_turn`** 等为证据。
- **H19**：矩阵明确 **DIFF**：Mimir 走 **`MimirAetherAgent.run_conversation`**，Hermes 直接测 **`HermesAgentLoop.run`**；**桩级语义** 以本仓库 Gate3 为准。

---

## 4. 差距与改进建议（≥2）

1. **文档交叉链**：在 `core_loop` 模块 docstring 或 `docs/m5_kernel_replaceability_slice.md` 近邻增加「主循环 ↔ H19」一句链到本报告或矩阵，降低新人绕路成本。
2. **真模型回归可选目标**：若产品需要 Hermes 真链 parity，单独列 **GAP** 任务：对齐 `test_agent_loop_tool_calling.py` 的用例子集到 Mimir（或 nightly），避免与 tier0 无网门禁混谈。

---

## 5. 拟迁移项（本轮）

- 已由 **`docs/phase_c_studies/README.md`** + **`hermes_mimir_behavior_matrix.md`** §4 增补链到本目录（见同批 commit）。

---

## 6. 复盘（C5）

- **学到什么**：主循环真源在 **`core_loop.py`**；**H19** 的「桩 OK、入口 DIFF」是刻意分工，不是遗漏。
- **下一步**：若改工具并发策略，必须先改矩阵 **H06** 行再改代码。
- **风险**：`core_loop.py` 体量大，局部改易牵预算/恢复/SessionDB；改前跑满 **`./run_ralph_tier0.sh`**。
