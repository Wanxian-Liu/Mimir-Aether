# Hermes ↔ MimirAether 行为对照表（草案）

本文把 **「相对 Hermes 1:1」** 从口号落成 **可勾选清单**：每一行是一条**可验证行为**，便于你在合并大块 Hermes 更新或做独立演进时，只动表上相关行。

- **契约总纲**：`docs/ralph_parity_contract_v1.md`  
- **pytest 映射（M1）**：`docs/ralph_parity_testmap.md`  
- **用例矩阵（Tier-0）**：`docs/ralph_tier0_case_matrix.md`

---

## 0. 上游锚点（必填）

| 字段 | 值 |
|------|-----|
| **HERMES_REF** | `bcdd720741f4988b66877f2bfe6a8ef930640a0d`（`git describe`: `v2026.4.30-146-gbcdd72074`） |
| **Hermes 远程** | `git@github.com:Wanxian-Liu/hermes-agent.git`（`upstream`: `NousResearch/hermes-agent`） |
| **本机快照路径** | `/home/rayliu/.openclaw/projects/hermes-agent`（用于本地 `git show`/读源码；换机器请 `git fetch` 后 checkout 上表 SHA） |
| **对照日期** | 2026-05-01 |
| **备注** | 更新 Hermes 时：先改 **HERMES_REF**，再对本表做 diff，不要无表合并。 |

**一键对齐到本 REF（示例）**

```bash
git -C /path/to/hermes-agent fetch origin
git -C /path/to/hermes-agent checkout bcdd720741f4988b66877f2bfe6a8ef930640a0d
```

---

## 1. 表头说明

| 列 | 含义 |
|----|------|
| **ID** | 稳定编号，讨论/PR 可引用。 |
| **域** | CLI / Agent / Turn / Sandbox / Registry / Delegate / Security。 |
| **行为摘要** | 一句话，偏「用户/集成方可感知」。 |
| **Hermes（REF）** | 在 **HERMES_REF** 下**预期**行为（可链到 Hermes 文档/issue；此处先写摘要）。 |
| **MimirAether** | 当前实现结论：**OK** / **DIFF** / **TBD**（未核）。 |
| **证据** | Gate2/G3 用例路径或脚本；无则写 **GAP**。 |
| **差异说明** | **OK** 留空；**DIFF** 写原因与是否永久；**TBD** 写下一步核对方式。 |

---

## 2. 首批行为行（可直接在 PR 里增删）

> **HERMES_REF** 已锁定；下列 **Hermes（REF）** 列中，H06/H15/H19 已在 `bcdd72074…` 上做过**源码级**核对（非全仓库逐文件审计）。

| ID | 域 | 行为摘要 | Hermes（REF） | MimirAether | 证据 | 差异说明 |
|----|----|----------|---------------|-------------|------|----------|
| H01 | CLI | `-q` 与显式子命令同时出现时失败退出 | 不应静默忽略其一 | **OK** | `agent/test_cli_arg_boundaries.py::test_cli_query_and_explicit_subcommand_rejected` | |
| H02 | CLI | `models --set` 缺模型 ID 或下一 token 为 flag | 明确报错 | **OK** | `test_cli_models_set_*` | |
| H03 | CLI | `profiles` / `config` 缺参边界 | 退出码 1 + 用法提示 | **OK** | `agent/test_cli_arg_boundaries.py` | |
| H04 | Agent | 未知工具 / JSON 错 / 无 handler | 进入约定错误分支 | **OK** | `agent/test_agent_loop.py`, `test_agent_loop_edge.py` | |
| H05 | Agent | `max_turns` / 预算截断 | 停止策略一致 | **OK** | `test_max_turns*`, `test_turn_loop_budget.py` | |
| H06 | Agent | 单轮多工具顺序与回写 | **`assistant_msg.tool_calls` 列表顺序**串行 `for tc in …` 执行；每条结果按序追加 `role=tool`（`environments/agent_loop.py` L328–471） | **OK** | `test_multi_tool_in_single_turn` 等 | 与 Hermes **语义 OK**；具体工具实现/线程池细节另表 |
| H07 | Turn | 预算耗尽 turn 字段与 `current_turn`/stats | 状态自洽 | **OK** | `agent/test_turn_loop_budget.py` | |
| H08 | Sandbox | 本地子进程剥离秘钥型 env；passthrough 不扩散 | 子进程不可见父进程 KEY | **OK** | `agent/test_code_execution_tool_env.py` | |
| H09 | Sandbox | 本地 `PYTHONPATH` 首段为仓库根 | 可 `import tools` | **OK** | `test_execute_code_child_pythonpath_*` | 远程路径 **DIFF**：见 testmap |
| H10 | Sandbox | 远程无 python3 → 结构化错误 | 早退、不跑脚本 | **OK** | `agent/test_code_execution_remote_mock.py` | |
| H11 | Sandbox | 远程 124/130 → timeout/interrupted | 与后端约定一致 | **OK** | `test_execute_remote_script_timeout_exit_124`, `*_interrupt_exit_130` | |
| H12 | Sandbox | 远程畸形 `req_*` 删除后继续 | 不卡死 RPC | **OK** | `test_execute_remote_malformed_req_json_*` | |
| H13 | Sandbox | 远程 file RPC：`SANDBOX_ALLOWED` 各工具单测 + 双工具同脚本 | 工具名/参数到 handler | **OK** | `agent/test_code_execution_remote_mock.py`（多例） | `write_file` 为 **native 覆盖** → **DIFF**（有意） |
| H14 | Sandbox | `max_tool_calls` 截断后续 RPC | 返回 limit 错误 JSON | **OK** | `test_execute_remote_max_tool_calls_*` | |
| H15 | Registry | enable/disable/search/get 语义 | **工具可见性**由 `get_tool_definitions(enabled_toolsets=…)` 等过滤（如 TUI：`tui_gateway/server.py` 使用 `enabled_toolsets`）；无独立 `agent/tool_registry.py` 那种 SQLite 表 | **OK** | `agent/test_tool_registry_api.py`；工具名集合 **`scripts/diff_tool_names_hermes_mimir.py`** | **DIFF**：Hermes = **toolset/definitions 管道**；Mimir = **双轨**（`tools/registry` + `agent/tool_registry` DB）。名级 diff 用脚本；是否合并/删减工具另定 |
| H16 | Delegate | 缺 task / 非 PENDING / 未知 CLI | 明确失败或 False | **OK** | `agent/test_delegate_subagent_semantics.py` | 真子进程 **GAP/ext** |
| H17 | Security | fencer / 敏感路径 / `@file` | 阻断或红act | **OK** | `agent/test_security_fencer_and_paths.py` | ext：`test_integration` |
| H18 | Agent | `write_file` 参数串修复 | 畸形 JSON 可恢复 | **OK** | `agent/test_write_file_arg_repair.py` | |
| H19 | E2E | 主对话 + 工具（桩 LLM，无网） | **`HermesAgentLoop` + `MockServer`**：`tests/run_agent/test_agent_loop.py`（`TestHermesAgentLoop`，如 `test_simple_text_response` / `test_tool_call_then_text`）。**真模型链**（需 `OPENROUTER_API_KEY`）：`tests/run_agent/test_agent_loop_tool_calling.py` | **OK** | `agent/test_tier1_e2e_agent.py`（Gate3） | **DIFF**：Mimir 走 `MimirAetherAgent.run_conversation`；Hermes 直接测 `HermesAgentLoop.run`。桩级语义对齐以前者 pytest 为准；真模型对齐以后者为准 |
| H20 | 运维 | Gate1+2+3 一键绿 | 回归门槛 | **OK** | `./run_ralph_tier0.sh` | CI 绑定 **TBD** |

---

## 3. 维护规则

1. **改 Hermes 或 Mimir 行为**：先更新本表对应行，再合并代码；**证据**列必须有用例或标 **GAP**。  
2. **DIFF**：必须在「差异说明」里写清是 **永久** 还是 **待对齐**，并指向 issue/段落。  
3. **TBD**：必须在 1～2 周内落到 **OK/DIFF/GAP** 之一，避免长期悬空。  
4. 行数增多时：可按 **域** 拆子表，**ID** 仍全局唯一（H21…）。

---

## 4. 与「距离目标」的关系（怎么用这张表）

- **目标 A（有门禁）**：H01–H14、H18–H20 类行尽量 **OK + 证据** → 你们已覆盖大半。  
- **目标 B（可对账 Hermes）**：**HERMES_REF** 已锁；**H19** Hermes 锚点已写入上表；**H15** 用 `scripts/diff_tool_names_hermes_mimir.py` 做名级 diff（退出码 1 表示仍有差集，属预期直至你们刻意对齐工具面）。  
- **目标 C（真环境运转）**：本表外另需 **真网关/真终端/真模型** 的 **ext 清单**（可再建 `docs/mimir_prod_smoke.md`）；不必塞进 Gate2。  

---

## 5. 工具名集合 diff（H15 配套）

在 **MimirAether 仓库根**执行（子进程分别加载两仓，避免 `tools` 包冲突）：

```bash
python scripts/diff_tool_names_hermes_mimir.py \
  --hermes-root /path/to/hermes-agent \
  --mimir-root  /path/to/MimirAether
# 或 JSON：  python scripts/diff_tool_names_hermes_mimir.py ... --json
```

- **退出码 0**：两仓 `get_tool_definitions(quiet_mode=True)`（Hermes）与 `registry.get_all_tool_names()`（Mimir，在 `import model_tools` 之后）工具名集合一致。  
- **退出码 1**：打印仅 Hermes / 仅 Mimir 的名称列表（集合差），便于合并 Hermes 或裁剪 Mimir 时逐项决策。  
- **环境变量**：`HERMES_ROOT`、`MIMIR_ROOT` 可代替 `--hermes-root` / `--mimir-root`。
