# [DORMANT] dispatching-parallel-agents

**沉寂时间**: 2026-09-14T03:02:01.371493+00:00
**原始分类**: workflow
**描述**: **Core principle:** Dispatch one subagent per independent problem domain. Let them work concurrently. When facing 2+ independent tasks that can be worked on without shared state or sequential dependen
**触发阈值**: 60天未触碰

---

## 技能要点

# Dispatching Parallel Agents

**Core principle:** Dispatch one subagent per independent problem domain. Let them work concurrently.

When facing 2+ independent tasks that can be worked on without shared state or sequential dependencies, delegate to `delegate_task` subagents with isolated context. Their instructions must be precisely crafted — they should never inherit your session's context or history. You construct exactly what they need, preserving your own context for coordination.

## When to Use

**Use when:**
- 3+ test files failing with different root causes
- Multiple subsystems broken independently
- Research/investigation needed across separate domains
- Each problem can be understood without context from others
- No shared state between investigations

**Don't use when:**
- Failures are related (fix one might fix others)
- Need to understand full system state
- Subagents would interfere with each other (editing same files)
- Exploratory debugging — you don't know what's broken yet

### Decision Flowchart

```
Multiple tasks/failures?
  ├── No → Single agent, sequential work
  └── Yes → Are they independent?
       ├── No (related) → Single agent investigates all
       └── Yes → Can they work in parallel?
            ├── No (shared state) → Sequential subagents
            └── Yes → Parallel dispatch via delegate_task
```

## The Pattern

### 1. Identify Independent Domains

Group work by what's broken or what needs doing. Each domain must be self-contained — no cross-dependencies on files, state, or context.

Good example for multi-debugging:
- File A tests (tool approval flow)
- File B tests (batch completion behavior) 
- File C tests (abort functionality)

Good example for multi-research:
- Agent A surveys arXiv for Self-Harness papers
- Agent B reads Superpowers skill source code
- Agent C extracts relevant patterns from both

### 2. Create Focused Subagent Tasks

Each subagent gets:
- **Specific scope:** One test file, subsystem, or research domain


... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("dispatching-parallel-agents")` 即可自动唤醒。
