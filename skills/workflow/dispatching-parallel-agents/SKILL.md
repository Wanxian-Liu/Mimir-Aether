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
- **Clear goal:** Make these tests pass / Find X patterns
- **Constraints:** Don't change other code / Don't search outside scope
- **Expected output:** Summary of what you found and changed

### 3. Dispatch in Parallel

Issue ALL `delegate_task` calls in the same response — they run concurrently.

```python
# All three run in parallel
delegate_task(
    goal="Fix agent-tool-abort.test.ts failures",
    context="3 failures...",
    toolsets=["terminal", "file"]
)
delegate_task(
    goal="Fix batch-completion-behavior.test.ts failures", 
    context="2 failures...",
    toolsets=["terminal", "file"]
)
delegate_task(
    goal="Fix tool-approval-race-conditions.test.ts failures",
    context="1 failure...",
    toolsets=["terminal", "file"]
)
```

> Multiple `delegate_task` calls in one response = parallel execution. One per response = sequential.

### 4. Review and Integrate

- Read each summary
- Verify fixes don't conflict
- Run full test suite
- Integrate all changes

## Subagent Prompt Structure

Good subagent prompts are:

1. **Focused** — One clear problem domain
2. **Self-contained** — All context needed to understand the problem
3. **Specific about output** — What should the subagent return?

### Debugging Prompt Template

```python
delegate_task(
    goal=f"Fix the {N} failing tests in {file_path}",
    context=f"""
Test failures:
{error_messages}

Your task:
1. Read the test file and understand what each test verifies
2. Identify root cause
3. Fix by addressing the real issue
4. Run the tests to verify

Do NOT just work around symptoms — find the real issue.

Return: Summary of what you found and what you fixed.
""",
    toolsets=["terminal", "file"]
)
```

### Research Prompt Template

```python
delegate_task(
    goal=f"Research {topic} and extract actionable findings",
    context=f"""
Scope: {scope_description}
Focus areas: {focus_list}

Your task:
1. Search for {sources}
2. Read and understand the material
3. Extract patterns, code examples, and key insights
4. Map findings to our architecture

Return: Structured findings with specific code examples.
""",
    toolsets=["web", "file"]
)
```

## Common Mistakes

| ❌ Too Broad | ✅ Specific |
|---|---|
| "Fix all the tests" | "Fix agent-tool-abort.test.ts" |
| "Fix the race condition" | Paste error messages and test names |
| No constraints | "Do NOT change production code" |
| Vague output: "Fix it" | "Return summary of root cause and changes" |

## Integration with Other Skills

| Skill | Relationship |
|---|---|
| `mimiraether-delegate-subagent` | Provides the underlying `delegate_task` infrastructure |
| `mimiraether-subagent-driven-development` | Sequential subagent-dispatch per task — use this when tasks have dependencies |
| `mimiraether-verification` | Final verification after all parallel subagents complete |

## When NOT to Use

- **Related work:** Fixing one might fix others — investigate together first
- **Need full context:** Understanding requires seeing entire system
- **Exploratory debugging:** You don't know what's broken yet
- **Shared state:** Subagents would interfere (editing same files, using same resources)
- **Sequential dependencies:** Task B requires Task A's output

## Pitfalls

- **Dead subagents** — a subagent that can't proceed (blocked question = deadlock). Set `max_iterations` reasonably (default 50, lower for simple tasks)
- **Conflicting fixes** — two subagents editing the same file = merge hell always. Verify domains are truly independent before dispatching
- **Context omission** — subagent has NO memory of your conversation. Every piece of context must be in the prompt. The most common failure is assuming the subagent "knows" something from earlier in the session
- **Hiding behind subagents** — don't delegate a task you could do in 2 tools yourself. Subagents incur cost (context, tokens, latency). Use them for genuine parallel work, not routine tool calls
