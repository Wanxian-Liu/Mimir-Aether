# PI-L01: pi-agent Agent Loop — MimirAether 对照

> 只读学习，不复制 TS 文件、不修改 Mimir 代码。

## 源

- pi-agent: `~/.openclaw/projects/pi-agent/packages/agent/src/{agent.ts, agent-loop.ts}`
- MimirAether: `~/src/MimirAether/agent/{core_loop.py, execution_pipeline.py}`

## 5 条异同

### 相同

1. **LLM ↔ tool 交替循环**：两方都是「call LLM → 解析 tool calls → 执行 → 注入结果 → 再 call LLM」模式。pi `runLoop()` 内层 while 与 Mimir `core_loop` `while iteration < max_iterations` 等价。
2. **Turn 生命周期事件**：pi 有 `agent_start/turn_start/message_start/turn_end/agent_end` 事件订阅体系；Mimir 有 `post_close_analysis` 和 `session_tracker` 做执行后闭合。顺序一致。
3. **上下文变换（transformContext）**：pi 的 `transformContext` 钩子在每次 LLM 调用前处理消息修剪/注入，对应 Mimir 的 `prompt_builder._build_cross_session_context`（persistent → cross-session 注入）。
4. **工具质量与成功判别**：pi 的 `beforeToolCall/afterToolCall` 钩子可拦截/修改工具执行，Mimir 的 `execution_pipeline.record_tool_call()` 也提供前后处理面（包含 `success`、`error_message` 参数）。
5. **Abort 信号**：pi 通过 `AbortSignal` 传播取消请求；Mimir 有 `core_loop._stop_event` 和 `CanceledException` 做迭代中止。

### 不同

1. **事件驱动 vs 状态机**：pi 是基于 `EventStream` 的事件推送架构——所有 emit 立即广播给 listener，前端 UI 通过 subscribe 实时响应。Mimir 是同步的 turn 循环，完成后一次性写分析/进化结果，无实时事件投递。
2. **消息队列（steer/followUp）**：pi 有双队列机制——`steer()` 在当前 turn 后注入消息，`followUp()` 在 agent 将停止时注入。Mimir 无此概念；所有新输入都是用户发起的，agent 不支持运行时注入外部消息。
3. **类型系统边界**：pi 有 `AgentMessage`（应用层）→ `convertToLlm()` → `Message`（LLM 层）两层转换，支持自定义 app-specific message type + declaration merging。Mimir 使用单一 `Message` 类直通 LLM。
4. **工具执行策略**：pi 支持 `ToolExecutionMode`（`parallel`/`sequential`/`non-interleaved`），并行或串行执行多个 tool call。Mimir 固定串行——一次 `_execute_tool_call` 一个 tool，循环直到无 tool call。
5. **后执行分析管道**：Mimir 有完整的 `execution_pipeline` → `post_analysis` → `skill_evolution` 流水线（SoT JSONL + LLM 分析 + 技能修改）。pi 没有对应的后处理——agent 的结束信号就是 `agent_end`，不触发离线分析。

## 可借鉴（Mimir 落点）

1. **事件订阅模式**：Mimir 的 `core_loop` 目前无实时事件广播。如果未来需要飞书实时流式 UI（tool 开始/完成事件推送到卡片），可引入 emit/event sink 模式。
2. **双队列注入**：`steer()` 适合需要 agent 在运行时接收外部指令的场景（如网关注入系统消息），可考虑作为 `prompt_builder` 扩展钩子。
3. **两层消息转换**：`AgentMessage → convertToLlm → Message` 分离了内部状态与 LLM 序列化格式。Mimir 如果未来需要支持不同的 LLM provider（非 OpenAI 格式），可借鉴此中间转换层。

## 明确不做

1. **声明合并/TypeScript 类型体操**：无关，Python 无此能力。
2. **EventStream API 复制**：当前同步 turn loop 适用于生产环境，复杂度/维护成本高于收益。
3. **`afterToolCall` 钩子自治进化**：Mimir 已有 `execution_pipeline.record_tool_call()` + `post_analysis` 专注进化，不重载 tool execution 阶段。
