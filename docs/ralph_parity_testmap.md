# Parity Contract v1 → 测试映射（M1）

本文将 `docs/ralph_parity_contract_v1.md` **§2 行为面**与 **§1 模块**映射到具体 pytest 用例。  
约定：`文件路径::函数名`；路径相对于仓库根目录。

**图例**

| 标记 | 含义 |
|------|------|
| **G2** | 纳入 `./run_ralph_tier0.sh` 的 Gate2 |
| **G3** | 纳入同一脚本的 Gate3（Tier-1） |
| **ext** | 仓库已有，建议定期跑；**未**进默认 Gate2（见 §5） |
| **GAP** | 契约或矩阵已提及，**尚无**对应用例（待补或显式暂缓） |

---

## 1. 按契约 §2「必须一致的行为面」映射

| 行为面 | 对应用例（G2 / G3 / ext） | 说明 |
|--------|---------------------------|------|
| **输入语义**（同类输入 → 同类分支：工具 / 错误 / 终止） | G2: `agent/test_agent_loop.py::test_basic_conversation`, `test_single_tool_call`, `test_unknown_tool`, `test_tool_execution_error`, `test_api_call_failure`, `test_max_turns`; `agent/test_agent_loop_edge.py::test_multi_tool_in_single_turn`, `test_json_parse_error`, `test_no_handler_registered`, `test_max_turns_enforced`, `test_no_tools_agent`, `test_batch_register`; G3: `agent/test_tier1_e2e_agent.py::test_tier1_plain_assistant_reply`, `test_tier1_tool_call_then_final_reply` | 覆盖无工具、单/多工具、未知工具、执行失败、API 失败、预算截断；Tier-1 覆盖 `core_loop.run_conversation` 主路径。**Hermes 桩级等价**：`hermes-agent/tests/run_agent/test_agent_loop.py::TestHermesAgentLoop`（见 `docs/hermes_mimir_behavior_matrix.md` **H19**） |
| **输出语义**（文案可不同，含义一致） | 与上列相同；断言侧重最终 role=assistant 内容或 tool 消息结构 | 未单独拆测试文件；依赖各用例内的 assert |
| **错误语义**（未知工具、JSON 错误、无 handler 等） | G2: `test_unknown_tool`, `test_json_parse_error`, `test_no_handler_registered`, `test_tool_execution_error`, `test_api_call_failure`; `agent/test_agent_loop_edge.py::test_malformed_tool_call_empty_name_is_unknown_tool`; `agent/test_delegate_subagent_semantics.py`（未知 agent → FAILED；缺失 / 非 PENDING `task_id`）；`agent/test_cli_arg_boundaries.py`（含 **`-q` 与显式子命令并存 → 报错退出**、`version` 后 REMAINDER 中含 `-q` 不崩）；`agent/test_write_file_arg_repair.py`（`write_file` 字符串参数修复） | — |
| **轮次语义**（`max_turns` / 预算耗尽） | G2: `test_max_turns`, `test_max_turns_enforced`, `agent/test_turn_loop_budget.py`（跳过 `chat`；耗尽 turn 字段/`current_turn`/history/stats；连续耗尽多 turn；`reset` 后可正常对话） | `agent_loop` 与 `turn_loop` 两条线均有覆盖 |
| **工具语义**（顺序、次数、结果回写） | G2: `test_single_tool_call`, `test_multi_tool_in_single_turn`, `test_batch_register`, `agent/test_agent_loop_edge.py::test_tool_call_missing_id_synthesized_matches_tool_message`; G3: `test_tier1_tool_call_then_final_reply`（`_execute_tools` 桩） | Hermes 严格顺序对齐若需加强，可再加对比用例 |
| **安全语义**（注入、秘钥、HOME 等） | G2: `agent/test_code_execution_tool_env.py`（HOME/profile、`secret` 名剥离、registry/config passthrough、组合「只放行一条 KEY」）；G2: `agent/test_security_fencer_and_paths.py`（fencer 红act、敏感路径、`@file` 阻断、`allowed_root` 逃逸）；ext: `agent/test_integration.py::test_memory_fencer`, `test_fencer_used_in_run_conversation` | — |

---

## 2. 按契约 §1「对齐范围（首批）」映射

| 模块 | 对应用例 | 缺口（GAP） |
|------|----------|-------------|
| `cli.py` | G2: `agent/test_cli_arg_boundaries.py`（`version`；`profiles` / `config` / `models` 缺参；**`-q` 与显式子命令同时出现 → 退出码 1 + 说明**；**`version -q x` → REMAINDER，不崩**） | 非法类型等仍可选补充 |
| `agent/core_loop.py` | G3: `agent/test_tier1_e2e_agent.py`（全文）；G2: `agent/test_write_file_arg_repair.py`（`_parse_write_file_arguments_string`）；ext: `agent/test_integration.py::test_fencer_used_in_run_conversation`, `test_compressor_used_in_run_conversation`, `test_insights_recorded_during_conversation`, `test_agent_initialization` | `execute_code` 字符串修复可另增单测 |
| `agent/turn_loop.py` | G2: `agent/test_turn_loop_budget.py`（见 §2「轮次语义」） | 与真实 `MimirAetherAgent`+预算实现联调可另增 ext |
| `agent/skill_funcs.py` | G2: `agent/test_skill_funcs.py`（schema、`skill_view`/`skills_list`/`skill_manage` 桩与错误路径） | 与真实 `skills/` 目录的集成可另增 ext 用例 |
| `agent/delegate_subagent.py` | G2: `agent/test_delegate_subagent_semantics.py`（未知 agent → FAILED；缺失 task_id → False；非 PENDING 再 delegate → False；mock 成功路径 → COMPLETED + result） | 与真实 CLI 子进程集成可另增 ext |
| `agent/tool_registry.py` | G2: `agent/test_tool_registry_concurrency.py::test_tool_registry_concurrent_register_and_get`; G2: `agent/test_tool_registry_api.py`（list/enable/disable、search/stats、**禁用后 `get`/search 不可见**、**enable 恢复**、**unregister 清空**）；**ext**：`scripts/diff_tool_names_hermes_mimir.py`（`tools/registry` 名集合 vs Hermes `get_tool_definitions`） | 与 Hermes **toolset 管道**的差异见 `docs/hermes_mimir_behavior_matrix.md` **H15** |
| `tools/code_execution_tool.py` | G2: `agent/test_code_execution_tool_env.py`（本地子进程 env / `PYTHONPATH`）；G2: `agent/test_code_execution_remote_mock.py`（远程 mock：**无 python3** 早退；**最小成功** 无 RPC；**exit 124/130**；**畸形 `req_*` JSON**；**file RPC**（沙箱工具单测 + **同脚本 `web_search`+`read_file`**；除 **`write_file`** native 覆盖）与 **`max_tool_calls`**）；G2: `agent/test_code_execution_tool_schema.py::test_execute_code_schema_mentions_only_enabled_tools`, `test_execute_code_schema_contains_import_examples` | 远程完整 RPC/ ship 文件路径可另增 mock 或 ext；远程不复制本地 `PYTHONPATH` 拼接语义已文档化 |

---

## 3. Tier-0 矩阵与本文档

`docs/ralph_tier0_case_matrix.md` **§A 已落地**条目，多数对应 §1 表中 G2 的 `test_agent_loop*`；矩阵 **§B 待补齐**项若在实现前无测试，在本文档 **§4** 登记为 GAP。

---

## 4. 显式 GAP 登记（待补或暂缓）

以下项在矩阵或历史讨论中出现，**当前无专门用例**或覆盖间接；补测前请在契约或矩阵标注优先级。

| 主题 | 建议用例名（占位） | 备注 |
|------|-------------------|------|
| CLI（非法类型等） | `test_cli_*` | `models --set`、`-q` 与子命令互斥已覆盖 |

暂缓某条时，请在表中增加「暂缓 + 原因 + 目标日期」，并在 `ralph_parity_contract_v1.md` 或 Issue 中留痕。

---

## 5. 未纳入默认 Gate2 的扩展用例（ext）

下列测试**已通过**本地 pytest，建议开发者在改相关模块时执行；亦可后续并入 `run_ralph_tier0.sh`。

- `agent/test_integration.py`（`core_loop` 与压缩/insights/fencer 集成）
- 根目录其它 `test_*.py`（如 `test_fix_*`）按需手工跑，**不**列入本 Parity 映射，避免与 Ralph 门禁混淆。

---

## 6. 维护规则（M1 完成判据）

1. 契约 §2 每条行为面在本文档 §1 中**至少有一行**对应用例，或指向 §4 GAP 并说明暂缓。  
2. 新增 P0 行为：**先**加或更新本表，**再**合并实现。  
3. `./run_ralph_tier0.sh` 中 Gate2 列表应与 §2 中 **G2** 用例文件一致（见 `run_ralph_tier0.sh`）。

---

## 7. 相关文档

- `docs/hermes_mimir_behavior_matrix.md` — Hermes **HERMES_REF** 与行为行对照（草案，可随 ref 更新）  
- `scripts/diff_tool_names_hermes_mimir.py` — Hermes vs Mimir **工具名集合** diff（子进程隔离，见矩阵 **§5**）  
- `docs/ralph_parity_contract_v1.md` — 契约正文  
- `docs/ralph_tiers.md` — Gate1–3 说明  
- `docs/ralph_tier0_case_matrix.md` — 用例矩阵  
- `docs/ralph_roadmap_milestones.md` — M0–M6 里程碑  
