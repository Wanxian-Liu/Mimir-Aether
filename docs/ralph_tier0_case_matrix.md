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

## A3. `write_file` 参数修复（`test_write_file_arg_repair.py`）

1. 合法 JSON 字符串  
2. 非 JSON 前缀 + `"path"`/`"content"` 正则抽取  
3. `path|content` 管道格式（含空 content）  
4. 双重转义引号修复  
5. 不可解析输入 → `None`  

## B. 待补齐（下一批 Tier-0）

优先级 P0（建议先补）：

- CLI 子命令参数边界（空参数、冲突参数、非法参数）
- `delegate_subagent` 的 agent_type 分支边界
- `code_execution_tool` 的环境隔离边界（HOME / PYTHONPATH / secret 过滤）
- `turn_loop` 预算耗尽后的状态一致性
- `tool_registry` 并发注册/查询一致性

## C. 每日结果记录（建议）

- Parity 通过率（Tier-0）
- 新增失败数
- 回归失败数
- 连续无错误轮次

建议目标：连续 3 轮无错误后，才允许进入下一模块替换。
