# [DORMANT] delegate-subagent

**沉寂时间**: 2026-07-14T18:58:41.046150+00:00
**原始分类**: productivity
**描述**: 委托任务给AI子代理并收集结果。管理从任务创建到委托再到结果聚合的完整生命周期。**执行层**：提供子代理基础设施（Task创建/持久化/多代理类型/并行执行）。编排层见 subagent-driven-development。
**触发阈值**: 60天未触碰

---

## 技能要点

# delegate-subagent

Delegate tasks to AI sub-agents and collect their results. Manages task lifecycle from creation through delegation to result aggregation.

> **实现状态**: 规范/参考设计，对应 Python 模块待实现。编排层入口见 `subagent-driven-development`。

**参考实现**: Hermes Agent delegation系统

## 目标模块 (待实现)

**目标路径**: `~/.mimiraether/delegate_subagent.py`

```python
# 目标 API（实现后可用）
from delegate_subagent import SubagentManager, TaskStatus

manager = SubagentManager()  # Uses ~/.mimiraether/tasks/
```

## Core Features

- **Task Creation**: Create tasks with descriptions
- **Agent Delegation**: Support for claude-code, codex, hermes-agent, opencode
- **Result Collection**: Gather outputs from completed tasks
- **Result Aggregation**: Generate summary reports
- **State Persistence**: Tasks saved to `~/.mimiraether/tasks/state.json`
- **Task Branching**: Fork tasks for parallel exploration of different approaches
- **Parallel Execution**: Run multiple sub-agents concurrently

## Task States

| Status | Description |
|--------|-------------|
| PENDING | Created, not yet delegated |
| RUNNING | Agent is executing |
| COMPLETED | Successfully finished |
| FAILED | Agent error occurred |
| CANCELLED | Manually cancelled |
| BRANCHED | Forked into a new branch |

## Usage

### Basic Task Management

```python
from delegate_subagent import SubagentManager, TaskStatus

manager = SubagentManager()

# Create a task
task = manager.create_task("Refactor the authentication module")
print(f"Created: {task.id}")

# List all tasks
for t in manager.list_tasks():
    print(f"[{t.id}] {t.status.value} - {t.description}")

# Filter by status
pending = manager.list_tasks(status=TaskStatus.PENDING)
running = manager.list_tasks(status=TaskStatus.RUNNING)

# Get specific task
task = manager.get_task("abc123")
if task:
    print(f"Status: {task.status.value}")
    print(f"Error: {task.error}")
```

### Delegating to Agents

```python
# Delegate to Claude Code (default)
manager.delegate_task(task.id, agent_type="cla

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("delegate-subagent")` 即可自动唤醒。
