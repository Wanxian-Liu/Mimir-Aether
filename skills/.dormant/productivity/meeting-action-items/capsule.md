# [DORMANT] meeting-action-items

**沉寂时间**: 2026-11-22T02:34:58.642418+00:00
**原始分类**: productivity
**描述**: Turn meeting notes into cited decisions, owners, tickets.
**触发阈值**: 60天未触碰

---

## 技能要点

# Meeting Action Items

Convert an existing transcript or notes set into accountable follow-through. `teams-meeting-pipeline` can retrieve Teams artifacts; this skill begins once notes/transcript content is available, from any source.

## When to Use

- "Extract action items from this meeting."
- "What did we decide and who owns what?"
- "Draft the follow-up and create tickets."
- "Reconcile these notes with the existing project board."

Don't use for: retrieving meeting recordings or transcripts (use `teams-meeting-pipeline` or the relevant connector first).

## Procedure

### 1. Establish meeting evidence

Use `read_file` on the provided notes/transcript files. Identify meeting title/date, participants, source files, transcript completeness, and whether speaker/time references exist. Done when missing portions and low-confidence transcription are stated.

### 2. Separate evidence types

Extract into distinct lists:

- decisions actually made
- proposals not decided
- explicit commitments
- questions and blockers
- risks and dependencies
- facts/context

Do not turn brainstorming into decisions. Done when each candidate item has a supporting quote, timestamp, page, or note reference when available.

### 3. Normalize action items

For every commitment record:

| Field | Rule |
|---|---|
| outcome | Concrete result, not a vague topic |
| owner | Explicit named owner; otherwise `unresolved` |
| due date | Explicit date or `unresolved`; never invent one |
| dependency | What must happen first |
| acceptance | Observable completion condition |
| source | Transcript/note reference |

Done when every action has supported fields or visible unresolved values.

### 4. Reconcile existing records

Load the user's tracker connector (`notion`, `github-issues`, or whichever system owns the work). Search for matching open items before creating anything — recurring meetings breed duplicate tickets. Preserve conflicts in owner/date/status for confirmation rather than silently overwr

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("meeting-action-items")` 即可自动唤醒。
