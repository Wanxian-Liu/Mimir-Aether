# MW-03: 工具调度平台解耦薄层

> **日期**：2026-06-02 · **状态**：已实现

## 问题

`agent_loop.py` 和 `parallel_dispatcher.py` 中的工具调度需要 `session_id` 和运行时上下文。此前这些信息通过 `self.task_id` 字符串 + gateway 特定导入传入，存在平台耦合隐患。

## 方案

新建 `agent/tool_dispatch_context.py`，提供纯数据类 `ToolDispatchContext`：

```python
@dataclass(frozen=True)
class ToolDispatchContext:
    session_id: str
    channel: str = "cli"        # 'cli' | 'feishu' | 'api'
    workspace_root: str = ...   # always absolute path
```

### 与 IQ-41 并行工具的关系

- **MW-02（parallel_dispatcher）** 现在接收 `task_id` 字符串 → 后续可改为接收 `ToolDispatchContext`（将 `session_id` 作为 task_id 传入）
- 并行分类逻辑不影响平台解耦：`is_read_only()` 不依赖 channel
- 如果未来不同 channel 需要不同只读白名单，可以在 `ToolDispatchContext` 上暴露方法

### 未来演进

当前 `agent_loop.py` 和 `parallel_dispatcher.py` 仍直接使用字符串 `task_id`。后续 grain 可以：
1. 在 `MimirAgentLoop.__init__` 增加 `context: ToolDispatchContext` 参数
2. `parallel_dispatcher.dispatch_all` 接收 `ToolDispatchContext` 替代 `task_id: str`
3. 记录 `channel` 到工具执行日志

**非 P1。不做。**
