# Hermes Core-Loop 学习分析报告

## 1. Hermes 核心设计分析

### 1.1 ToolError 数据结构
```python
@dataclass
class ToolError:
    turn: int                  # 哪个轮次出错
    tool_name: str             # 工具名
    arguments: str             # 参数（截断）
    error: str                 # 错误信息
    tool_result: str           # 返回给模型的原始结果
```
**设计意图**: 收集所有工具执行错误，不中断流程，但记录完整上下文用于调试。

### 1.2 AgentResult 数据结构
```python
@dataclass
class AgentResult:
    messages: List[Dict]       # 完整对话历史
    managed_state: Optional   # 服务端状态
    turns_used: int = 0       # LLM调用次数
    finished_naturally: bool   # 是否自然结束
    reasoning_per_turn: List  # 每轮推理内容
    tool_errors: List[ToolError]  # 工具错误列表
```
**设计意图**: 返回完整执行元数据，便于分析、调试和续传。

### 1.3 reasoning_per_turn 提取机制
```python
def _extract_reasoning_from_message(message) -> Optional[str]:
    # 多provider兼容:
    # 1. message.reasoning_content
    # 2. message.reasoning
    # 3. message.reasoning_details[].text (OpenRouter)
```
**设计意图**: 统一提取各provider的reasoning字段，不依赖特定格式。

### 1.4 tool_executor 线程池
```python
_tool_executor = concurrent.futures.ThreadPoolExecutor(max_workers=128)

# 用于: asyncio.run()内部使用的工具后端不会死锁
loop.run_in_executor(_tool_executor, lambda: handle_function_call(...))
```
**设计意图**: 为Modal/Docker/Daytona等内部用asyncio.run()的后端提供干净的事件循环，防止死锁。

### 1.5 其他关键设计
- **Fallback parser**: `<tool_call>` 原始标签解析
- **Tool name validation**: 执行前验证工具名在白名单中
- **Turn budget enforcement**: 每轮调用后强制执行预算检查
- **resize_tool_pool()**: 运行时动态调整线程池大小

---

## 2. MimirAether 当前状态对比

### 优势
- ✅ TurnManager 多轮对话管理
- ✅ Checkpoint/recovery 断点续传
- ✅ MemoryFencer prompt注入防护
- ✅ ContextCompressor 上下文压缩
- ✅ Tool deduplication 去重
- ✅ Tool repair 工具名修复
- ✅ Plugin hooks 插件系统
- ✅ IterationBudget + refund 迭代预算

### 劣势
- ❌ **无ToolError收集**: 错误只日志，不返回给调用方
- ❌ **无reasoning_per_turn**: reasoning被去除但不追踪
- ❌ **无AgentResult**: 返回简单字符串，丢失元数据
- ❌ **无线程池**: asyncio直接执行，某些后端可能死锁
- ❌ **无工具名白名单验证**: 任意注册工具都能执行
- ❌ **无原始标签解析**: 不处理`<tool_call>`格式

---

## 3. 进化计划

### Phase 1: 添加ToolError机制 (高优先级)
- 在 `core_loop.py` 添加 `ToolError` dataclass
- 修改 `_execute_single_tool` 收集错误
- 添加 `tool_errors` 列表到结果

### Phase 2: 添加AgentResult dataclass (高优先级)
- 创建 `ExecutionMetadata` 或修改返回结构
- 包含 turns_used, finished_naturally, tool_errors

### Phase 3: 添加reasoning_per_turn (中优先级)
- 提取reasoning内容（多provider格式）
- 每轮记录到列表

### Phase 4: 添加线程池支持 (低优先级)
- 为 `asyncio.run()` 类型后端添加线程池
- 仅在必要时使用

---

## 4. 实施记录

| 日期 | 阶段 | 改动 | 验证结果 |
|------|------|------|----------|
| 2026-04-24 | Phase 1 | 添加ToolError dataclass | ✅ |
| 2026-04-24 | Phase 2 | 添加ExecutionMetadata | ✅ |
| 2026-04-24 | Phase 3 | 添加reasoning_per_turn | ✅ |
