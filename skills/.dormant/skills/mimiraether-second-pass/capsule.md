# [DORMANT] mimiraether-second-pass

**沉寂时间**: 2026-11-22T02:34:55.356804+00:00
**原始分类**: skills
**描述**: When proposing a solution, discard the first idea and re-examine from fundamentals. The first pass is often lazy (copy, rename, inline); the second pass produces genuinely self-designed solutions.

**触发阈值**: 60天未触碰

---

## 技能要点

# Second-Pass Thinking

## The Pattern (Observed)

Our first proposal is typically the **lazy path**:
- "Delete the ABC and inline" (方案 A — doesn't fix the root cause)
- "Rename the class" (方案 B — cosmetic only)
- "Copy the file" (fuzzy_match — pure copy, no adaptation)

After re-examination from first principles, the second pass yields genuinely better designs:
- 方案 D: Redesign the interface from scratch around MimirAether's actual needs

## When to Trigger

1. **Proposing any architecture change** — ask "is this my first idea? If so, think again."
2. **User says "重新思考" / "再想想" / "出个方案"**
3. **After learning from another codebase** — first instinct is often to copy. Re-examine.
4. **When the solution feels too easy** — if it's a 5-line change, it's probably lazy.

## Method

### Step 1: Dump the First Idea
Write down the first proposal quickly. Don't polish it.

### Step 2: Ask the Fundamental Questions
- What problem are we actually solving?
- What are the real constraints? (DeepSeek-only, one engine, task-oriented)
- What does the OTHER codebase assume that we don't?
- If we started from scratch with zero knowledge of the other codebase, what would we build?

### Step 3: Compare Assumptions
Make a table:
| Assumption | Other Codebase | MimirAether |
|------------|---------------|-------------|
| ...        | ...           | ...         |

This reveals which designs are portable and which are foreign.

### Step 4: Design from First Principles
Build the solution from MimirAether's constraints upward, not from the other codebase downward.

### Step 5: Compare and Present
Show a comparison table (first idea vs second idea vs other options) with clear criteria:
- Does it delete the copied code?
- Is the interface self-designed?
- Is the design philosophy independent?
- How traceable to the original?

## Anti-Patterns

- ❌ "They have X, so we should have X too"
- ❌ "Just rename and it's ours"
- ❌ "Copy the file, we'll integrate later" (never happens)
- ❌ Presenting onl

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-second-pass")` 即可自动唤醒。
