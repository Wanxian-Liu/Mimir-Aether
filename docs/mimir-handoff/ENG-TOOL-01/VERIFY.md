# ENG-TOOL-01: 验证

## tier0

```
./run_ralph_tier0.sh
```

末行：

```
4 failed, 677 passed
```

4 项失败均为预存（L2/L3 跨会话检索测试），与本次改动无关。

## 专项测试

```
python3 -m pytest tests/agent/test_tool_event_emitter.py -v
```

```
tests/agent/test_tool_event_emitter.py::test_emit_with_env_off PASSED
tests/agent/test_tool_event_emitter.py::test_emit_env_on PASSED
tests/agent/test_tool_event_emitter.py::test_emit_env_on_error PASSED
tests/agent/test_tool_event_emitter.py::test_subscriber_exception_does_not_break_others PASSED
tests/agent/test_tool_event_emitter.py::test_emit_empty_arguments PASSED

5 passed in 0.04s
```

## 手动验证

```python
# 在 agent 内启用
import os
os.environ["MIMIR_TOOL_EVENTS"] = "1"

from agent.tool_event_emitter import subscribe
events = []
subscribe(events.append)
# 执行一个包含工具调用的任务后检查 events 列表
```

## 回归

`git diff --stat`:
```
agent/agent_loop.py              | 23 +++++++++++++++++++++++
agent/tool_event_emitter.py       | 83 ++++++++++++++++++++++++++++++++++++++++++
tests/agent/test_tool_event_emitter.py | 94 ++++++++++++++++++++++++++++++++++++++++++++++++
```
