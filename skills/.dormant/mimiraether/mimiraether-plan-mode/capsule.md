# [DORMANT] mimiraether-plan-mode

**沉寂时间**: 2026-07-12T04:37:29.543491+00:00
**原始分类**: mimiraether
**描述**: Plan mode for MimirAether — analyze context, create actionable implementation plans, and prepare for execution without acting. Inspired by Hermes Agent's plan skill.
**触发阈值**: 60天未触碰

---

## 技能要点

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

**If task has phases** (from `mimiraether-strategic-planner`): load `data/active_task.json`, break down tasks WITHIN each phase, maintaining phase dependencies.

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

### Phas

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-plan-mode")` 即可自动唤醒。
