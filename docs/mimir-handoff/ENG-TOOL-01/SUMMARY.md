# ENG-TOOL-01: 工具执行事件流

## 做了什么

为 MimirAether 添加了轻量工具执行事件发射机制（PI-L06 #2），使 Gateway 平台（飞书、Telegram 等）可订阅实时工具状态更新。

### 设计

- **新文件** `agent/tool_event_emitter.py` — 模块级单例，`subscribe(callback)` 注册回调，`emit_tool_execution_start/end` 广播事件
- **Env 守卫** `MIMIR_TOOL_EVENTS=1` — 默认关闭，不影响现有行为
- **钩子** `agent/agent_loop.py` — 工具 dispatch 前发射 start、成功/异常分支发射 end
- **事件结构**：`{type, tool_name, arguments, session_id, timestamp}`（start）/ `{type, tool_name, success, duration_ms, session_id, error, timestamp}`（end）
- 监听器异常 **不会** 传播——每个 subscriber 独立 try/except

### 使用（Gateway 侧）

```python
from agent.tool_event_emitter import subscribe

def on_tool_event(event: dict):
    if event["type"] == "tool_execution_start":
        # 飞书: 发卡片 "🔧 read_file 执行中..."
    elif event["type"] == "tool_execution_end":
        # 更新卡片 "✅ read_file 完成 (0.5s)"

token = subscribe(on_tool_event)
# 取消: token()
```

### 风险

极低。env guard 默认关闭，不改变任何功能行为。

### 建议 commit message

```
feat(tool_events): add pipeline emit for tool start/end events

- agent/tool_event_emitter.py: subscribe/emit_tool_execution_start/end
- agent/agent_loop.py: hooks around tool dispatch
- tests/agent/test_tool_event_emitter.py: 5 tests
- Env guard: MIMIR_TOOL_EVENTS=1 (default off)
```
