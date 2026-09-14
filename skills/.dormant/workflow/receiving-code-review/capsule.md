# [DORMANT] receiving-code-review

**沉寂时间**: 2026-09-14T03:02:01.392591+00:00
**原始分类**: workflow
**描述**: **Core principle:** Verify before implementing. Ask before assuming. Technical correctness over social comfort. Code review requires **technical evaluation**, not emotional performance. When receiving
**触发阈值**: 60天未触碰

---

## 技能要点

# Receiving Code Review

**Core principle:** Verify before implementing. Ask before assuming. Technical correctness over social comfort.

Code review requires **technical evaluation**, not emotional performance. When receiving feedback, your job is to determine whether the suggestion is technically correct for THIS codebase, not to make the reviewer feel heard.

## The Response Pattern

```
WHEN receiving code review feedback:
1. READ: Complete feedback without reacting
2. UNDERSTAND: Restate requirement in own words (or ask)
3. VERIFY: Check against codebase reality
4. EVALUATE: Technically sound for THIS codebase?
5. RESPOND: Technical acknowledgment or reasoned pushback
6. IMPLEMENT: One item at a time, test each
```

## Forbidden Responses

**NEVER:**
- "You're absolutely right!" (performative agreement)
- "Great point!" / "Excellent feedback!" (empty praise)
- "Let me implement that now" (before verification)

**INSTEAD:**
- Restate the technical requirement
- Ask clarifying questions
- Push back with technical reasoning if wrong
- Just start working (actions > words)

## Handling Unclear Feedback

```
IF any item is unclear:
STOP - do not implement anything yet
ASK for clarification on unclear items
WHY: Items may be related. Partial understanding = wrong implementation.
```

**Example:**
```
reviewer: "Fix items 1-6"

You understand 1,2,3,6. Unclear on 4,5.
❌ WRONG: Implement 1,2,3,6 now, ask about 4,5 later
✅ RIGHT: "I understand items 1,2,3,6. Need clarification on 4 and 5 before proceeding."
```

## Source-Specific Handling

### From Your Human Partner

- **Trusted** — implement after understanding
- **Still ask** if scope is unclear
- **No performative agreement**
- **Skip to action** or technical acknowledgment

### From External Reviewers (Subagent, CI, or Third Party)

```
BEFORE implementing:
1. Check: Technically correct for THIS codebase?
2. Check: Breaks existing functionality?
3. Check: Reason for current implementation?
4. Check: Works on all pla

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("receiving-code-review")` 即可自动唤醒。
