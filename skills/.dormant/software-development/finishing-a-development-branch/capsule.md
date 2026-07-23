# [DORMANT] finishing-a-development-branch

**沉寂时间**: 2026-07-23T06:18:46.734345+00:00
**原始分类**: software-development
**描述**: Use after all implementation tasks are done — verify tests, detect environment, present 4 structured options (merge/PR/keep/discard), execute choice, clean up workspace. Never merge with failing tests.
**触发阈值**: 60天未触碰

---

## 技能要点

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
git

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("finishing-a-development-branch")` 即可自动唤醒。
