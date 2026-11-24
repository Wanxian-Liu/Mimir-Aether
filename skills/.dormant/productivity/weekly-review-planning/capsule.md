# [DORMANT] weekly-review-planning

**沉寂时间**: 2026-11-22T02:34:58.795442+00:00
**原始分类**: productivity
**描述**: Weekly reset: commitments, stalled work, next-week plan.
**触发阈值**: 60天未触碰

---

## 技能要点

# Weekly Review and Planning

Run a bounded weekly reset across the user's chosen systems. This is a concrete recurring task, not a generic productivity methodology — the `weekly-review` Automation Blueprint schedules it as a cron job.

## When to Use

- "Run my weekly review."
- "What did I commit to and what is slipping?"
- "Plan next week from my calendar, tasks, and notes."
- "Find stale projects and waiting items."
- A cron tick fires for a scheduled weekly review.

Don't use for: daily briefs (see the `google-workspace` daily-brief reference) or single-inbox triage (`email-inbox-triage`).

## Procedure

### 1. Set systems and window

Confirm timezone, review period, planning horizon, authoritative task/project store, calendars, inboxes, and allowed writes. Default to recommendations/drafts, not mutations. Done when source-of-truth conflicts have a declared winner.

### 2. Review calendar evidence

Load `google-workspace` or the relevant calendar connector. Inspect the completed week for meetings and commitments, then the next 1-2 weeks for deadlines, travel, preparation, and capacity. Capture follow-ups implied by past events and conflicts ahead. Done when both retrospective and horizon are covered.

### 3. Clear capture inboxes

Review the task inbox, notes (`obsidian`, `notion`), flagged email (`email-inbox-triage` owns thread-level triage), and other declared capture points. Convert each item to next action, project, waiting, scheduled, someday, reference, archive, or delete proposal. Do not mutate until scope is approved. Done when remaining unprocessed items are counted and stated.

### 4. Reconcile active projects

For each project identify desired outcome, next action, owner, deadline, blocker, last meaningful activity, and source link. Flag projects with no next action, missed dates, duplicate records, or contradictory status. Done when every active project is actionable or explicitly paused.

### 5. Review waiting and commitments

Find promises made b

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("weekly-review-planning")` 即可自动唤醒。
