---
name: mimiraether-plan-mode
description: Plan mode for MimirAether — analyze context, create actionable implementation plans, and prepare for execution without acting. Inspired by Hermes Agent's plan skill.
version: 1.0.0
author: MimirAether (learned from Hermes Agent)
license: MIT
metadata:
  hermes:
    tags: [planning, implementation, workflow, strategy]
    related_skills: [systematic-debugging, test-driven-development, subagent-driven-development, mimiraether-tool-triggers]
    learned_from: hermes-agent/plan
auto_load: false
---

# MimirAether Plan Mode

## Overview

Plan mode is a structured approach for creating detailed implementation plans before execution. When activated, the agent analyzes requirements, breaks down tasks, identifies dependencies, and produces a concrete markdown plan.

**Core principle:** Think twice, plan once, execute once.

## When to Use

Use when:
- User requests a plan instead of implementation
- Complex multi-step task requires systematic breakdown
- Implementation involves multiple components or teams
- Uncertainty exists about approach or requirements
- User wants to review and approve before action

**Plan mode is NOT execution mode.** You are analyzing and planning only.

## The Process

### Phase 1: Context Analysis

Before writing any plan:

1. **Understand the Goal**
   - What is the end state?
   - What problem does this solve?
   - Who will use/consume the result?

2. **Assess Current State**
   - Existing codebase, infrastructure?
   - Constraints (time, budget, technology)?
   - Team skills and availability?

3. **Identify Assumptions**
   - List all assumptions explicitly
   - Flag uncertain items for user clarification
   - Note any "will assume X unless told otherwise" items

### Phase 2: Task Breakdown

Break down the work into **executable chunks** (15-30 min each):

```
Too vague:  "Implement user authentication"
Right size: "Add email/password login to Flask app"
            "Add JWT token generation middleware"
            "Create registration endpoint with validation"
            "Add password reset flow with email"
            "Write integration tests for auth flow"
```

**Chunking criteria:**
- Each chunk should be independently verifiable
- Chunks that touch the same files should be sequential
- Independent chunks can be parallelized
- Each chunk has a clear "done" state

### Phase 3: Dependency Mapping

For each chunk:

```
[Chunk 1] ──┬──> [Chunk 3]
            └──> [Chunk 4]
[Chunk 2] ─────────────> [Chunk 4]
                         └──> [Chunk 5]
```

**Dependency types:**
- **Hard dependency**: Must complete before Y can start
- **Soft dependency**: Y can start, but benefits from X completing first
- **Parallel**: X and Y can run concurrently

### Phase 4: Risk Identification

For each chunk, identify:

| Risk | Impact | Mitigation |
|------|--------|------------|
| External API dependency | API down | Mock/stub, retry logic |
| New technology unfamiliar | Delay | Spikes, POC first |
| Cross-team coordination | Blocker | Early communication |

### Phase 5: Plan Document

Save the plan to `.mimir/plans/YYYY-MM-DD_HHMMSS_<slug>.md`

```markdown
# Implementation Plan: [Title]

## Goal
[One sentence: what are we building?]

## Current State
[What exists today]

## Assumptions
1. [Assumption 1]
2. [Assumption 2]

## Task Breakdown

### Task 1: [Name] (~15 min)
**Owner:** [Who]
**Description:** [What]
**Files to change:**
- `src/xxx.py` (add)
- `tests/test_xxx.py` (add)
**Verification:** `pytest tests/ -k test_xxx`
**Dependencies:** None
**Risks:** [Any]

### Task 2: [Name] (~20 min)
...

## Dependency Graph
[ASCII diagram or list]

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| ... | ... | ... |

## Verification Plan
- [ ] Unit tests pass
- [ ] Integration tests pass  
- [ ] Manual smoke test

## Open Questions
- [ ] Question 1 (needs answer before Task 3)
- [ ] Question 2
```

## Interaction Patterns

### When Request is Clear
Write the plan directly. No need to ask.

### When Request is Vague
Ask one clarifying question. Examples:
- "What format should the output be?"
- "Should this integrate with existing X or create new?"
- "What's the priority if we have to cut scope?"

### When Request is Complex
Follow the full 5-phase process. Don't skip phases.

## Execution Readiness Check

Before completing plan mode, verify:

- [ ] All tasks are independently actionable
- [ ] All dependencies are explicit
- [ ] All assumptions are stated
- [ ] Verification criteria are measurable
- [ ] Open questions are flagged

## Switching to Execution

Plan mode ends when:
1. User approves the plan → Execute
2. User asks for changes → Revise plan
3. User cancels → Close plan

To transition to execution, use `subagent-driven-development` skill or execute tasks sequentially with `test-driven-development`.

## Example

**User:** "I need to add caching to our API"

**Plan mode output:**

```
# Implementation Plan: API Response Caching

## Goal
Add Redis-based response caching to reduce database load for frequently-accessed endpoints.

## Current State
- Flask API, no caching layer
- PostgreSQL database
- No Redis infrastructure

## Assumptions
1. Redis will be available (ops team can provision)
2. Cache TTL of 5 minutes is appropriate
3. Cache invalidation on write is acceptable

## Task Breakdown

### Task 1: Infrastructure Setup (~20 min)
- Add redis-py to requirements.txt
- Create config.py cache settings
- Add Redis connection helper
- Verify: redis-cli ping succeeds

### Task 2: Cache Decorator (~25 min)
- Create `utils/cache.py` with @cache decorator
- Handle hit/miss/lock/expiry
- Write unit tests (TDD)
- Verify: pytest tests/test_cache.py -v

### Task 3: Apply to Endpoints (~30 min)
- Apply decorator to GET /users
- Apply decorator to GET /products
- Skip POST/PUT (write-through)
- Verify: cache hits increase

### Task 4: Integration Tests (~20 min)
- Add cache tests to integration suite
- Test invalidation
- Verify: pytest tests/integration/ -v

## Open Questions
- [ ] What Redis instance to use? (Dev/Prod?)
- [ ] Should we cache errors too?

## Next Steps
User approves → Task 1 → Task 2 → ...
```

---

**Remember:** A good plan is specific, actionable, and verifiable. If you can't write the verification step, you can't know when you're done.
