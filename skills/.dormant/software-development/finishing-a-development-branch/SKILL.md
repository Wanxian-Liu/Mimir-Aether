---
name: finishing-a-development-branch
description: Use after all implementation tasks are done — verify tests, detect environment, present 4 structured options (merge/PR/keep/discard), execute choice, clean up workspace. Never merge with failing tests.
version: 1.0.0
---

# Finishing a Development Branch

**Core Principle:** Verify tests → Detect environment → Present options → Execute choice → Clean up.

**Announce at start:** "I'm using the finishing-a-development-branch skill to complete this work."

---

## The Process (6 Steps)

### Step 1: Verify Tests
```bash
npm test / cargo test / pytest / go test ./...
```
- **If tests fail:** Stop. Show failures. "Cannot proceed with merge/PR until tests pass."
- **If tests pass:** Continue to Step 2.

### Step 2: Detect Environment
```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
```

| State | Menu | Cleanup |
|-------|------|---------|
| `GIT_DIR == GIT_COMMON` (normal repo) | Standard 4 options | No worktree to clean up |
| `GIT_DIR != GIT_COMMON`, named branch | Standard 4 options | Provenance-based (see Step 6) |
| `GIT_DIR != GIT_COMMON`, detached HEAD | Reduced 3 options (no merge) | No cleanup (externally managed) |

### Step 3: Determine Base Branch
```bash
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null
```
Or ask: "This branch split from main — is that correct?"

### Step 4: Present Options

**Normal repo / named-branch worktree (exactly 4 options):**
```
Implementation complete. What would you like to do?
1. Merge back to <base> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work
Which option?
```

**Detached HEAD (exactly 3 options):**
```
Implementation complete. You're on a detached HEAD (externally managed workspace).
1. Push as new branch and create a Pull Request
2. Keep as-is (I'll handle it later)
3. Discard this work
Which option?
```

> **Don't add explanation** — keep options concise.

### Step 5: Execute Choice

#### Option 1: Merge Locally
```bash
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"
git checkout <base>
git pull
git merge <feature-branch>
# Verify tests on merged result
# Only after merge succeeds: cleanup worktree (Step 6), then delete branch
git branch -d <feature-branch>
```

#### Option 2: Push and Create PR
```bash
git push -u origin <feature-branch>
gh pr create --title "<title>" --body "..." 
```
**Do NOT clean up worktree** — user needs it alive to iterate on PR feedback.

#### Option 3: Keep As-Is
Report: "Keeping branch <name>. Worktree preserved at <path>."
**Don't cleanup worktree.**

#### Option 4: Discard
**Confirm first:**
```
This will permanently delete:
- Branch <name>
- All commits: <commit-list>
- Worktree at <path>

Type 'discard' to confirm.
```
Wait for exact confirmation. If confirmed: Cleanup worktree (Step 6), then force-delete branch `git branch -D <feature-branch>`.

### Step 6: Cleanup Workspace
**Only runs for Options 1 and 4.** Options 2 and 3 always preserve the worktree.

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
WORKTREE_PATH=$(git rev-parse --show-toplevel)
```

- **If `GIT_DIR == GIT_COMMON`:** Normal repo, no worktree to clean up. Done.
- **If worktree path is under `.worktrees/`, `worktrees/`, or `~/.config/superpowers/worktrees/`:** Superpowers created this worktree — we own cleanup.
  ```bash
  MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
  cd "$MAIN_ROOT"
  git worktree remove "$WORKTREE_PATH"
  git worktree prune  # Self-healing: clean up any stale registrations
  ```
- **Otherwise:** The host environment (harness) owns this workspace. Do NOT remove it.

---

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge locally | yes | - | - | yes |
| 2. Create PR | - | yes | yes | - |
| 3. Keep as-is | - | - | yes | - |
| 4. Discard | - | - | - | yes (force) |

---

## Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| Skipping test verification | Merge broken code, create failing PR | Always verify tests before offering options |
| Open-ended questions | "What should I do next?" is ambiguous | Present exactly 4 structured options (or 3 for detached HEAD) |
| Cleaning up worktree for Option 2 | Remove worktree user needs for PR iteration | Only cleanup for Options 1 and 4 |
| Deleting branch before removing worktree | `git branch -d` fails because worktree still references the branch | Merge first, remove worktree, then delete branch |
| Running `git worktree remove` from inside the worktree | Command fails silently | Always `cd` to main repo root before `git worktree remove` |
| Cleaning up harness-owned worktrees | Removing worktree the harness created causes phantom state | Only clean up worktrees under `.worktrees/`, `worktrees/`, or `~/.config/superpowers/worktrees/` |
| No confirmation for discard | Accidentally delete work | Require typed "discard" confirmation |

## Red Flags

**Never:**
- Proceed with failing tests
- Merge without verifying tests on result
- Delete work without confirmation
- Force-push without explicit request
- Remove a worktree before confirming merge success
- Clean up worktrees you didn't create (provenance check)
- Run `git worktree remove` from inside the worktree

**Always:**
- Verify tests before offering options
- Detect environment before presenting menu
- Present exactly 4 options (or 3 for detached HEAD)
- Get typed confirmation for Option 4
- Clean up worktree for Options 1 & 4 only
- `cd` to main repo root before worktree removal
- Run `git worktree prune` after removal