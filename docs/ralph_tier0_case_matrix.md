# Ralph Tier-0 Case Matrix（Hermes 1:1 学习基线）

本矩阵用于“先对齐行为，再谈进化”。

## A. 已落地自动化用例（当前）

来源：`agent/test_agent_loop.py`、`agent/test_agent_loop_edge.py`。  
完整 Gate2 文件列表与契约映射见 `docs/ralph_parity_testmap.md`。

1. 基本对话（无工具调用）
2. 单工具调用
3. 未知工具调用
4. 工具执行异常
5. API 调用失败
6. `max_turns` 限制
7. `SimpleAgentLoop` 同步包装
8. `SimpleAgentLoop + 工具`
9. reasoning 提取
10. 单轮多工具调用
11. JSON 参数解析错误
12. 已注册但无处理器
13. tool_call 缺失 id
14. malformed tool_call
15. reasoning 变体提取
16. 批量 `register_tools`
17. `tool_call` 缺失 `id`（合成 id 与 tool 消息一致）
18. 畸形 `tool_call`（空工具名 → 未知工具错误）

## A2. CLI 参数边界（`test_cli_arg_boundaries.py`）

1. `version` 退出码 0  
2. `profiles rename` 缺新名称  
3. `profiles export` 缺输出路径  
4. `profiles create` 缺名称  
5. `profiles delete` 缺名称  
6. `profiles import` 缺归档路径  
7. `config set` 缺 value  
8. `config get` 缺 key  
9. `models --set` 缺模型 ID  
10. `models --set --refresh`（不把 `--refresh` 当模型 ID）  
11. `-q` 与末尾 `version` 并存 → 退出码 1，提示不能同时使用单次任务与子命令  
12. `version -q …`（`-q` 落在 REMAINDER）→ 仍正常打印版本，不崩溃  

## A3. `write_file` 参数修复（`test_write_file_arg_repair.py`）

1. 合法 JSON 字符串  
2. 非 JSON 前缀 + `"path"`/`"content"` 正则抽取  
3. `path|content` 管道格式（含空 content）  
4. 双重转义引号修复  
5. 不可解析输入 → `None`  

## A4. 安全回归（`test_security_fencer_and_paths.py`）

1. MemoryFencer 指令注入红act  
2. 无害用户语可正常包裹  
3. `_is_sensitive_path`（`.ssh` / `.aws` vs 临时文件）  
4. `_read_file_safe` 拒绝 `.ssh` 形态路径  
5. `_resolve_path` + `allowed_root` 阻止 `..` 逃逸  
6. `preprocess_context_references` 对 `~/.ssh/config` 类 `@file` 置 `blocked`  

## A5. `execute_code` 子进程环境（`test_code_execution_tool_env.py`）

1. 存在 profile 目录时 `HOME` 指向 profile home；不存在时不强行覆盖  
2. 父进程 secret 型 / 非白名单变量名不进入子环境；`PATH` 仍保留  
3. `register_env_passthrough` 可放行名称含 `API_KEY` 的变量  
4. `terminal.env_passthrough`（`config.yaml`）同上  
5. 仅放行一条 `API_KEY` 时，其它 `*_API_KEY` 仍不可见  
6. 本地子进程：`PYTHONPATH` 首段为仓库根（可 `import tools`）；父环境 `PYTHONPATH` 追加在后（POSIX；Windows 跳过）  
7. 远程 mock：`command -v python3` 失败路径 → `status=error`，且不再发起后续 `env.execute`（POSIX；Windows 跳过）  
8. 远程 mock：python3 / mkdir / ship / 跑 `script.py` / `rm -rf` 成功，`status=success`，RPC 轮询仅 `ls` 空结果  
9. 远程 mock：子进程真实写 `req_*` / 等 `res_*`，轮询线程 `cat` → `handle_function_call`（桩）→ 写回；`tool_calls_made==1`  
10. 远程 mock：连续两次 `web_search`，`tool_calls_made==2`，`rm -f` 正确删掉 `req_*`（避免重复派发）  
11. 远程 mock：`max_tool_calls=1` 时第二次 RPC 返回 limit 错误，`handle_function_call` 仅一次  
12. 远程 mock：`python3 script.py` 返回码 **124** → `status=timeout`，`error` 含配置中的 `timeout` 秒数  
13. 远程 mock：返回码 **130** → `status=interrupted`，`output` 追加说明文案  
14. 远程 mock：预置非法 `req_000000` → 轮询 `rm` 后仅合法 `web_search` 进 `handle_function_call`  
15. 远程 mock：**`read_file`**（非 web）一轮 file RPC，`enabled_tools` 仅含 `read_file`  
16. 远程 mock：**`terminal`** 一轮 file RPC，`enabled_tools` 仅含 `terminal`  
17. 远程 mock：**`web_extract`** 一轮 file RPC  
18. 远程 mock：**`patch`**（`mode=replace`）一轮 file RPC  
19. 远程 mock：**`search_files`** 一轮 file RPC（多参数）  
20. 远程 mock：同脚本 **`web_search` + `read_file`**，`tool_calls_made==2`  
21. 远程 mock：同脚本 **`web_search` + `read_file` + `web_extract`**（三工具），`tool_calls_made==3`  

## A6. `delegate_subagent`（`test_delegate_subagent_semantics.py`）

1. 未知 agent 命令 → 任务 `FAILED`，错误含 `not found in PATH`  
2. 不存在的 `task_id` → `delegate_task` 返回 `False`  
3. 已完成任务再次 `delegate` → `False`，状态与结果不变  
4. Mock `_execute_agent` 成功 → `COMPLETED`，`assigned_agent` / `result` / `agent_config` 传递正确  
5. **真实子进程**（`test_delegate_subagent_integration.py`，POSIX）：可执行 stub → `COMPLETED`，`returncode==0`，stdout 含任务描述与标记  
6. **真实子进程超时**（同上）：`sleep` stub + `timeout=1` → `FAILED`，`error` 含 `timed out`  

## A7a. `tool_registry` 状态（`test_tool_registry_api.py` 补充）

1. `disable` 后 `get` 为 `None`  
2. `search` 不命中已禁用项  
3. `enable` 后 `get` 与 `search` 恢复  
4. `unregister` 后库中无该工具（`list_all(enabled_only=False)` 为空）  

## A7. `turn_loop` 预算（`test_turn_loop_budget.py`）

1. `remaining<=0` 时不调用 `chat`，返回上限提示  
2. 耗尽 turn：`assistant_message` 为空、`error` 与 `status` 一致、`current_turn`/history/stats 一致  
3. 连续两次用户消息在预算仍为 0 时各生成一条 `MAX_ITERATIONS` turn  
4. `TurnManager.reset` 清空 turns 后，提高 `remaining` 可再走 `COMPLETED` 路径  
5. 真实 `MimirAetherAgent` 联调（stub LLM）：两轮正常回复后，`turn.iterations` 随预算累计为 `1 -> 2`  
6. 真实 `MimirAetherAgent` 联调（stub LLM）：第三轮在预算耗尽前置检查处生成 `MAX_ITERATIONS` turn  

## B. 待补齐（下一批 Tier-0）

优先级 P0（建议先补）：

- CLI 非法类型、互斥 flag 显式报错（`profiles`/`config`/`models`、`-q` 调度见 A2）
- `code_execution_tool` 远程 **`patch`+`terminal` 组合**、`write_file` native 与 RPC 文档化（§20 双工具；**§21 三工具 `web_search`+`read_file`+`web_extract`**；单工具 §15–19）
- `tool_registry` 并发注册/查询一致性（启用/禁用/注销语义见 A7a）

## C. 每日结果记录（建议）

- Parity 通过率（Tier-0）
- 新增失败数
- 回归失败数
- 连续无错误轮次

建议目标：连续 3 轮无错误后，才允许进入下一模块替换。
