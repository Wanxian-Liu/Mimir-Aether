# PI-L02: 工具执行与 State 序列化 — MimirAether 对照

> 只读学习，不复制 TS 文件、不修改 Mimir 代码。

## 源

- pi-agent: `agent-loop.ts`（`executeToolCalls` / `executeToolCallsSequential` / `executeToolCallsParallel`），`types.ts`（`AgentTool` / `AgentToolResult` / `ToolExecutionMode`）
- MimirAether: `execution_pipeline.py`，`execution_recorder.py`，`core_loop.py`

## 5 条异同

### 相同

1. **tool 调用 → 结果注入 → 再调 LLM 的核心循环**：两方都实现相同的基础 loop。pi `runLoop()` 的 `hasMoreToolCalls` flag 与 Mimir core_loop 的 `iteration < max_iterations` 等价。
2. **before/after 钩子**：pi 有 `beforeToolCall`（可 block 工具执行）+ `afterToolCall`（可修改结果），Mimir 有 `execution_pipeline.record_tool_call()` 带 `success` / `error_message` 参数 + `post_analysis` 后处理。
3. **错误传播**：两方都将工具错误编码为结构化 tool result（非抛出异常），LLM 在下轮看到 error 自行决定后续。
4. **终止信号传播**：pi 的 `terminate` flag（`shouldTerminateToolBatch`: all tools must set terminate=true）；Mimir 无等效 batch 终止，但单工具后续即下一轮。

### 不同

1. **并行 vs 串行**：pi 原生支持 `ToolExecutionMode`（`parallel` / `sequential`），并行模式下工具同时执行，仅 finalize 按 source order。Mimir 强制串行——一次一个 tool call，无并发执行机制。
2. **实时事件投递**：pi 工具执行全程 emit `tool_execution_start / tool_execution_update / tool_execution_end` 事件，UI 可实时追踪。Mimir 无此类事件——结果写入 JSONL SoT 是 session 结束后的离线过程。
3. **State 序列化**：pi 的状态全在 `AgentContext.messages` 内存数组中，无持久化 SoT 概念（由外部调用方自行持久化）。Mimir 有完整 `ExecutionRecorder` 写 JSONL（ADR-005 SoT），包括 `ToolCallRecord`（step, tool_name, arguments, result_summary, success, error, duration_ms）+ `AgentActionRecord` + `AnalysisRecord`。
4. **工具参数准备/校验**：pi 有 `prepareToolCallArguments`（tool.prepareArguments 钩子）+ `validateToolArguments`（typebox schema 校验），两层 pipeline。Mimir 依赖 Hermes 的 `validate_tool_args.py` 做基础校验，无 `prepareArguments` 变换层。
5. **afterToolCall 结果合并 vs 后分析**：pi 的 `afterToolCall` 是原地合并——直接替换 `result.content` / `details` / `isError`，影响下一轮 LLM。Mimir 的 `post_analysis` 是离线分析——不修改本轮工具结果，只产出 `evolution` / `quality` 分析记录供下个 session 引用。

## 可借鉴（Mimir 落点）

1. **并行工具执行**：多个独立工具（如 `read_file` + `web_search`）可并发，显著降低迭代延迟。需考虑 `tool_execution_mode` env 开关，默认串行保持稳定。
2. **工具执行事件流**：飞书卡片可实时显示「工具 X 正在执行…」→「工具 X 完成」状态，通过 Gateway 推送而非离线 JSONL。
3. **`prepareArguments` 钩子**：在工具注册时声明参数变换函数（如自动展开路径、注入默认参数），减少 LLM 产生的格式错误。

## 明确不做

1. **Typebox schema 校验**：Python 无 typebox，可移植性差。现有 `validate_tool_args.py` 足矣。
2. **`afterToolCall` 结果替换**：Mimir 的进化分析（post_analysis + skill_evolution）在 session 闭合后进行，减少 tool execution 阶段的干扰。
3. **`shouldTerminateToolBatch` 逻辑**：当前 Mimir 的单工具/单循环模型不需要 batch 终止判断。
