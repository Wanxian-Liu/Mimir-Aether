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
4. Check: Works on all platforms/versions?
5. Check: Does reviewer understand full context?

IF suggestion seems wrong:
  Push back with technical reasoning
IF you can't easily verify:
  Say so: "I can't verify this without [X]. Should I investigate/ask/proceed?"
IF conflicts with your human partner's prior decisions:
  Stop and discuss with your human partner first
```

### From Code Review Subagent (requesting-code-review)

The requesting-code-review skill runs two independent review subagents (spec compliance + code quality). Treat their output as **data to verify**, not commands to follow:

```
1. Read spec reviewer verdict → check against plan
2. Read quality reviewer verdict → evaluate each issue
3. If you disagree: verify against actual code, then push back
4. If they're right: fix it, re-run review
```

## YAGNI Check for "Professional" Features

```
IF reviewer suggests "implementing properly":
  grep codebase for actual usage
  IF unused: "This endpoint isn't called. Remove it (YAGNI)?"
  IF used: Then implement properly
```

## Implementation Order

```
FOR multi-item feedback:
1. Clarify anything unclear FIRST
2. Then implement in this order:
   - Blocking issues (breaks, security)
   - Simple fixes (typos, imports)  
   - Complex fixes (refactoring, logic)
3. Test each fix individually
4. Verify no regressions
```

## When to Push Back

Push back when:
- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature)
- Technically incorrect for this stack
- Legacy/compatibility reasons exist
- Conflicts with your human partner's architectural decisions

**How to push back:**
- Use technical reasoning, not defensiveness
- Ask specific questions
- Reference working tests/code
- Involve your human partner if architectural

## Acknowledging Correct Feedback

When feedback IS correct:
```
✅ "Fixed. [Brief description of what changed]"
✅ "Good catch — [specific issue]. Fixed in [location]."
✅ [Just fix it and show in the code]

❌ "You're absolutely right!"
❌ "Great point!"
❌ "Thanks for catching that!"
❌ ANY gratitude expression
```

**Why no thanks:** Actions speak. Just fix it. The code itself shows you heard the feedback.
**If you catch yourself about to write "Thanks":** DELETE IT. State the fix instead.

## Gracefully Correcting Your Pushback

If you pushed back and were wrong:
```
✅ "You were right — I checked [X] and it does [Y]. Implementing now."
✅ "Verified this and you're correct. My initial understanding was wrong because [reason]. Fixing."

❌ Long apology
❌ Defending why you pushed back
❌ Over-explaining
```

State the correction factually and move on.

## Integration with Other Skills

| Skill | Relationship |
|---|---|
| `mimiraether-requesting-code-review` | Complementary — this skill handles RECEIVING review; that skill handles REQUESTING review on your own code |
| `mimiraether-subagent-driven-development` | The two-stage review (spec compliance + code quality) feeds into this skill |
| `mimiraether-verification` | Final verification gate runs after all review feedback is resolved |

## Common Mistakes

| Mistake | Fix |
|---|------|
| Performative agreement | State requirement or just act |
| Blind implementation | Verify against codebase first |
| Batch without testing | One at a time, test each |
| Assuming reviewer is right | Check if it breaks things |
| Avoiding pushback | Technical correctness > comfort |
| Partial implementation | Clarify all items first |
| Can't verify, proceed anyway | State limitation, ask how to proceed |
