---
name: using-git-worktrees
description: Use when starting implementation work — ensures work happens in an isolated git worktree workspace. Detects existing isolation first, then uses native tools or git worktree fallback. Never start implementation on main/master without isolation.
version: 1.0.0
---

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
2. **Existing project-local directory:** `.worktrees/` (preferred) or `worktrees/`
3. **Existing global directory:** `~/.config/superpowers/worktrees/<project>/`
4. **Default:** `.worktrees/` at project root

#### Safety Verification (project-local only):
```bash
git check-ignore -q .worktrees 2>/dev/null || git check-ignore -q worktrees 2>/dev/null
```
- **If NOT ignored:** Add to `.gitignore`, commit the change, then proceed.
- **Why critical:** "Prevents accidentally committing worktree contents to repository."
- Global directories need no verification.

#### Create the Worktree:
```bash
project=$(basename "$(git rev-parse --show-toplevel)")
# For project-local: path="$LOCATION/$BRANCH_NAME"
# For global: path="~/.config/superpowers/worktrees/$project/$BRANCH_NAME"
git worktree add "$path" -b "$BRANCH_NAME"
cd "$path"
```

**Sandbox fallback:** If `git worktree add` fails with permission error → Tell user sandbox blocked creation, work in current directory, run setup and baseline tests in place.

---

## Step 3: Project Setup

Auto-detect and run appropriate setup:

```bash
# Node.js
if [ -f package.json ]; then npm install; fi
# Rust
if [ -f Cargo.toml ]; then cargo build; fi
# Python
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then poetry install; fi
# Go
if [ -f go.mod ]; then go mod download; fi
```

---

## Step 4: Verify Clean Baseline

Run tests:
```bash
npm test / cargo test / pytest / go test ./...
```

**If tests fail:** Report failures, ask whether to proceed or investigate.
**If tests pass:** Report ready.

### Report Format:
```
Worktree ready at <path>
Tests passing (<count> tests, 0 failures)
Ready to implement <feature>
```

---

## Quick Reference Table

| Situation | Action |
|-----------|--------|
| Already in linked worktree | Skip creation (Step 0) |
| In a submodule | Treat as normal repo (Step 0 guard) |
| Native worktree tool available | Use it (Step 1a) |
| No native tool | Git worktree fallback (Step 1b) |
| `.worktrees/` exists | Use it (verify ignored) |
| `worktrees/` exists | Use it (verify ignored) |
| Both exist | Use `.worktrees/` |
| Neither exists | Check instruction file, then default `.worktrees/` |
| Global path exists | Use it (backward compat) |
| Directory not ignored | Add to .gitignore + commit |
| Permission error on create | Sandbox fallback, work in place |
| Tests fail during baseline | Report failures + ask |
| No package.json/Cargo.toml | Skip dependency install |

---

## Common Mistakes

1. **Fighting the harness** - Using `git worktree add` when platform already provides isolation. Fix: Step 0 detects existing isolation; Step 1a defers to native tools.

2. **Skipping detection** - Creating nested worktree inside existing one. Fix: Always run Step 0 first.

3. **Skipping ignore verification** - Worktree contents get tracked, pollute git status. Fix: Always use `git check-ignore` before creating project-local worktree.

4. **Assuming directory is worktree-ready** - Creating in non-existent parent. Fix: Check and create parent directory if needed.

5. **Not declaring branch name** - Creates confusion. Fix: Include branch name in worktree path.