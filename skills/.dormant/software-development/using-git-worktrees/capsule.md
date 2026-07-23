# [DORMANT] using-git-worktrees

**沉寂时间**: 2026-07-23T06:18:46.749979+00:00
**原始分类**: software-development
**描述**: Use when starting implementation work — ensures work happens in an isolated git worktree workspace. Detects existing isolation first, then uses native tools or git worktree fallback. Never start implementation on main/master without isolation.
**触发阈值**: 60天未触碰

---

## 技能要点

# Using Git Worktrees

## Overview
**Purpose:** Ensure work happens in an isolated workspace. Prefer native worktree tools; fall back to manual git worktrees only when no native tool is available.

**Core Principle:** "Detect existing isolation first. Then use native tools. Then fall back to git. Never fight the harness."

**Announce at start:** "I'm using the using-git-worktrees skill to set up an isolated workspace."

---

## Step 0: Detect Existing Isolation

**Before creating anything, check if already in an isolated workspace:**

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
```

**Submodule guard:** `GIT_DIR != GIT_COMMON` is also true inside git submodules. Verify you're not in a submodule:

```bash
git rev-parse --show-superproject-working-tree 2>/dev/null
```

### Decision Matrix:
| Condition | Action |
|-----------|--------|
| `GIT_DIR != GIT_COMMON` (not submodule) | Already in linked worktree → Skip to Step 3. Report branch state. |
| `GIT_DIR == GIT_COMMON` (or submodule) | Normal repo → Ask for consent to create worktree. If declined, work in place. |

**Report format:**
- On a branch: "Already in isolated workspace at `<path>` on branch `<branch>`."
- Detached HEAD: "Already in isolated workspace at `<path>` (detached HEAD, externally managed). Branch creation needed at finish time."

---

## Step 1: Create Isolated Workspace

### 1a. Native Worktree Tools (Preferred)
- Look for tools named `EnterWorktree`, `WorktreeCreate`, `/worktree` command, or `--worktree` flag.
- **If available:** Use it and skip to Step 3.
- **Critical:** "Using `git worktree add` when you have a native tool creates phantom state your harness can't see or manage."

### 1b. Git Worktree Fallback (Only if no native tool)

#### Directory Selection Priority:
1. **Explicit user preference** (from instructions) → Use without asking
2. **Existing pr

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("using-git-worktrees")` 即可自动唤醒。
