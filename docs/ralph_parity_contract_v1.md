# MimirAether Parity Contract v1（Ralph）

目标：以**行为一致**为标准，对齐本地 Hermes 的核心能力；禁止复制源码。

里程碑与完成判据（M0–M6）：见 `docs/ralph_roadmap_milestones.md`。

## 1. 对齐范围（首批）

- `cli.py`
- `agent/core_loop.py`
- `agent/turn_loop.py`
- `agent/skill_funcs.py`
- `agent/delegate_subagent.py`
- `agent/tool_registry.py`
- `tools/code_execution_tool.py`

## 2. 必须一致的行为面

行为面 ↔ 具体 pytest 用例：**`docs/ralph_parity_testmap.md`**（M1 映射表）。

- **输入语义**：同类输入触发同类行为（工具调用、错误分支、终止分支）。
- **输出语义**：返回结果可不同文案，但业务含义一致。
- **错误语义**：错误类别、触发条件、恢复路径一致（如未知工具、参数 JSON 错误、handler 缺失）。
- **轮次语义**：`max_turns`/预算耗尽时行为一致。
- **工具语义**：工具调用顺序、次数、工具结果回写方式一致。
- **安全语义**：路径注入、环境变量泄露、HOME 覆盖等风险受控。

## 3. 允许差异（可接受）

- 文案风格差异（中文/英文提示不同）。
- 日志字段命名差异（不影响行为）。
- 非关键元数据差异（时间戳、trace id、本地路径前缀）。

## 4. 不允许差异（阻断）

- 功能缺失（同场景 Hermes 成功而 MimirAether 无对应行为）。
- 关键错误分支失效（未知工具、JSON 参数错误、无 handler）。
- 回归导致既有通过用例失败。
- 新增外部隐式依赖（默认依赖 `hermes-agent` 路径等）。

## 5. Ralph 验收门

统一脚本：`./run_ralph_tier0.sh`（说明见 `docs/ralph_tiers.md`）。

- **Gate1（语法/导入）**：目标组件 `py_compile` 与 import 全通过。
- **Gate2（Parity-Tier0）**：`agent/test_agent_loop.py` 等 parity 用例全通过（见脚本列表）。
- **Gate3（Tier-1 E2E）**：`agent/test_tier1_e2e_agent.py` 全通过（`run_conversation` + 桩 LLM，无网络）。
- **稳定性（人工/CI 可选）**：连续 3 轮完整脚本无错误。

## 6. 执行纪律

- 小步迭代：每轮只修一个根因簇。
- 手术式改动：仅修改与失败直接相关代码。
- 先验证再推进：每轮必须给出“问题-原因-修复-验证”。
