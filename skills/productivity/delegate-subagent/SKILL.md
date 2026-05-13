---
name: "delegate-subagent"
description: "委托任务给AI子代理并收集结果。管理从任务创建到委托再到结果聚合的完整生命周期。**执行层**：提供子代理基础设施（Task创建/持久化/多代理类型/并行执行）。编排层见 subagent-driven-development。"
version: "1.1.0"
category: "productivity"
tags:
  - delegation
  - subagent
  - 任务委托
  - 子代理
  - 并行
  - execution-layer
metadata:
  related_skills: [subagent-driven-development]
---
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
manager.delegate_task(task.id, agent_type="claude-code")

# Delegate to Codex
manager.delegate_task(task.id, agent_type="codex")

# Delegate to Hermes Agent
manager.delegate_task(task.id, agent_type="hermes-agent")

# Delegate to OpenCode
manager.delegate_task(task.id, agent_type="opencode")

# With custom config
manager.delegate_task(task.id, "claude-code", agent_config={
    "timeout": 600,  # 10 minute timeout
    "cwd": "/path/to/project"
})
```

### Branching (Fork) Tasks

Create parallel branches for exploring different approaches:

```python
# Branch from existing task
branch = manager.branch_task(
    source_id="abc123",
    branch_label="try_approach_b",
    modify_description="Explore alternative authentication method"
)
print(f"Branch created: {branch.id}")

# List branches of a task
branches = manager.list_branches("abc123")
for b in branches:
    print(f"[{b.id}] {b.branch_label} - {b.status.value}")

# Branch with different agent
branch2 = manager.branch_task(
    source_id="abc123",
    agent_type="codex",  # Different agent for this branch
    branch_label="codex_approach"
)
```

### Parallel Execution

```python
# Create multiple tasks for parallel execution
tasks = [
    manager.create_task("Implement user authentication"),
    manager.create_task("Implement password reset"),
    manager.create_task("Add OAuth2 support")
]

# Delegate all in parallel
for task in tasks:
    manager.delegate_task(task.id, "claude-code")

# Wait for all to complete
manager.wait_for_tasks([t.id for t in tasks], timeout=600)

# Collect all results
results = manager.collect_results()
```

### Collecting Results

```python
# Collect all completed results
results = manager.collect_results()
for tid, data in results.items():
    print(f"Task: {data['description']}")
    print(f"Result: {data['result']}")

# Collect specific tasks
results = manager.collect_results(task_ids=["abc123", "def456"])

# Aggregate into summary report
summary = manager.aggregate_results()
print(summary)

# Aggregate with branch comparison
comparison = manager.aggregate_with_branches()
print(comparison)
```

### Task Management

```python
# Cancel a pending/running task
manager.cancel_task(task.id)

# Clear completed/failed/cancelled tasks
cleared = manager.clear_completed()
print(f"Cleared {cleared} tasks")

# Clear specific tasks
manager.clear_tasks(task_ids=["abc123", "def456"])
```

## CLI Interface

```bash
# Create a task
python delegate_subagent.py create "Fix the login bug"

# List tasks (with optional status filter)
python delegate_subagent.py list
python delegate_subagent.py list --status pending
python delegate_subagent.py list --branch feature-auth

# Show task details
python delegate_subagent.py show abc123

# Delegate a task
python delegate_subagent.py delegate abc123 --agent claude-code
python delegate_subagent.py delegate abc123 --agent hermes --timeout 600

# Branch a task (create parallel fork)
python delegate_subagent.py branch abc123 --label "try_alternative"
python delegate_subagent.py branch abc123 --agent codex --label "codex_approach"

# List branches of a task
python delegate_subagent.py branches abc123

# Collect results
python delegate_subagent.py collect
python delegate_subagent.py collect --tasks abc123 def456

# Aggregate results into summary
python delegate_subagent.py aggregate

# Aggregate with branch comparison
python delegate_subagent.py aggregate --compare abc123

# Cancel a task
python delegate_subagent.py cancel abc123

# Clear completed tasks
python delegate_subagent.py clear

# Wait for tasks to complete
python delegate_subagent.py wait abc123 def456 --timeout 300
```

## Branch Commands (Hermes-style)

Hermes uses `/branch` or `/fork` for session branching. The delegate-subagent module mirrors this pattern:

| Command | Description |
|---------|-------------|
| `branch <task_id>` | Create branch from task |
| `fork <task_id>` | Alias for branch |
| `branches <task_id>` | List branches of task |
| `branch-diff <id1> <id2>` | Compare branch results |

### Branch Workflow

```bash
# 1. Create original task
python delegate_subagent.py create "Build recommendation engine"

# 2. Delegate to one agent
python delegate_subagent.py delegate abc123 --agent claude-code

# 3. While running, branch to try different approach
python delegate_subagent.py branch abc123 --label "collaborative_filtering"

# 4. Delegate branch to different agent
python delegate_subagent.py delegate def456 --agent codex

# 5. Compare results when both complete
python delegate_subagent.py aggregate --compare abc123
```

## Result Format

```python
{
    "abc123": {
        "description": "Refactor auth module",
        "agent_type": "claude-code",
        "result": {
            "returncode": 0,
            "stdout": "Changes made...",
            "stderr": ""
        },
        "completed_at": "2026-04-23T10:30:00",
        "branch_label": None
    },
    "def456": {
        "description": "Refactor auth module (branch: collaborative_filtering)",
        "agent_type": "codex",
        "parent_id": "abc123",
        "branch_label": "collaborative_filtering",
        "result": {
            "returncode": 0,
            "stdout": "Alternative approach implemented...",
            "stderr": ""
        },
        "completed_at": "2026-04-23T10:32:00"
    }
}
```

## Branch Aggregation Output

```python
{
    "source_task": "abc123",
    "branches": [
        {
            "id": "abc123",
            "agent": "claude-code",
            "branch_label": None,
            "result": "Approach A: Matrix factorization",
            "metrics": {"time": 45, "quality_score": 0.85}
        },
        {
            "id": "def456",
            "agent": "codex",
            "branch_label": "collaborative_filtering",
            "result": "Approach B: User-based CF",
            "metrics": {"time": 38, "quality_score": 0.78}
        }
    ],
    "recommendation": "Approach A (higher quality score)"
}
```

## Hermes Delegation Configuration

```yaml
# ~/.openclaw/projects/MimirAether/config.yaml
delegation:
  model: anthropic/claude-sonnet-4
  provider: anthropic
  max_iterations: 50
  reasoning_effort: medium
```

## Notes

- Task state persists between runs in `~/.mimiraether/tasks/state.json`
- Agent CLIs must be available in PATH (claude, codex, hermes, opencode)
- Default timeout is 300 seconds (5 minutes)
- Failed tasks capture stderr in the error field
- Use `clear_completed()` to clean up old tasks
- Branches inherit parent task context but can modify description
- Different agents can be assigned to different branches
- Use `--compare` flag to get branch comparison in aggregation

## Implementation Classes

```python
@dataclass
class Task:
    id: str
    description: str
    status: TaskStatus
    agent_type: Optional[str]
    branch_label: Optional[str]
    parent_id: Optional[str]
    result: Optional[dict]
    error: Optional[str]
    created_at: str
    completed_at: Optional[str]

class SubagentManager:
    def __init__(self, tasks_dir: str = "~/.mimiraether/tasks")
    
    # Task CRUD
    def create_task(self, description: str) -> Task
    def get_task(self, task_id: str) -> Optional[Task]
    def list_tasks(self, status: TaskStatus = None, branch: str = None) -> List[Task]
    def delete_task(self, task_id: str) -> bool
    
    # Delegation
    def delegate_task(self, task_id: str, agent_type: str = "claude-code", 
                     agent_config: dict = None) -> bool
    def cancel_task(self, task_id: str) -> bool
    def wait_for_tasks(self, task_ids: List[str], timeout: int = 300) -> Dict
    
    # Branching
    def branch_task(self, source_id: str, branch_label: str,
                   agent_type: str = None, modify_description: str = None) -> Task
    def list_branches(self, task_id: str) -> List[Task]
    
    # Results
    def collect_results(self, task_ids: List[str] = None) -> Dict
    def aggregate_results(self, task_ids: List[str] = None) -> Dict
    def aggregate_with_branches(self, source_id: str) -> Dict
    
    # Cleanup
    def clear_completed(self) -> int
    def clear_tasks(self, task_ids: List[str]) -> int
```
