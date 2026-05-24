# P2-LONG-INDEP Night 1 — IND-01～03 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Prerequisites (run once):** superpowers:using-git-worktrees · superpowers:verification-before-completion · superpowers:finishing-a-development-branch

**Goal:** Close Wave D items **IND-01**, **IND-02**, **IND-03** (Hermes path independence — D7 partial), docs + tests + tier0 green, one PR to `main`.

**Architecture:** Document legacy env aliases in ADR-003 (supersedes scattered notes); add tier0 grep/advisory for bare `HERMES_HOME` defaults in runtime trees; introduce `MIMIR_SESSION_DB` with read-fallback from `OPENCLAW_SESSION_DB` in one resolver used by session search.

**Tech Stack:** Python 3.12, pytest, `mimir_constants`, `run_ralph_tier0.sh`, docs/adr

**Out of scope tonight (STOP — do not start):** IND-04, IND-05 (P3-0 single-writer — needs design review), IND-06 (刘哥 sign-off), gateway restart unless tier0 requires it.

---

## Task 0: Worktree + branch

**Files:** (none)

- [ ] **Step 1:** Announce `using-git-worktrees` skill
- [ ] **Step 2:** Create worktree

```bash
cd ~/src/MimirAether
git pull origin main
mkdir -p .worktrees
git worktree add .worktrees/p2-long-indep-night1 -b feat/p2-long-indep-night1
cd .worktrees/p2-long-indep-night1
git submodule update --init mimicore
```

- [ ] **Step 3:** Verify clean baseline

```bash
./run_ralph_tier0.sh
```

Expected: **267+2 PASS**, advisory `.openclaw` ≤ threshold

---

## Task 1: ADR-003 legacy env alias table (IND-01)

**Files:**
- Create: `docs/adr/003-runtime-env-aliases.md`
- Modify: `docs/OPENCLAW_ENV_LEGACY.md` (link to ADR-003 as canonical)
- Modify: `docs/path-contract.md` (one line under runtime home → ADR-003)
- Modify: `docs/MIMIR_EXEC_BACKLOG.md` (IND-01 → `[x]`)

- [ ] **Step 1:** Inventory env vars

```bash
rg -n 'os\.environ\.get|os\.getenv|getenv\(' mimir_constants.py agent/ gateway/ tools/ mimir_cli/ \
  --glob '*.py' --glob '!**/hermes_cli/**' | rg -i 'MIMIR_|HERMES_|OPENCLAW_|MIMIRAETHER_' | head -80
```

- [ ] **Step 2:** Write ADR-003 with tables:

Required sections:
1. **Status:** Accepted (2026-05-25)
2. **Canonical:** `MIMIR_AETHER_HOME` → resolution order matches `mimir_constants.get_mimir_home()` (`MIMIR_AETHER_HOME` > `MIMIRAETHER_HOME` > `HERMES_HOME` > `~/.mimiraether`)
3. **Legacy read aliases** (read-only fallback, sunset TBD 2026-Q3):
   - `HERMES_HOME` — systemd / old deploys
   - `MIMIRAETHER_HOME` — rename era
   - `OPENCLAW_SESSION_DB` → see IND-03
   - `OPENCLAW_GATEWAY_LOCK_DIR` — see existing `gateway/status.py`
4. **Forbidden in new code:** using `HERMES_HOME` or `Path.home()/".openclaw"` as **sole default** without `get_mimir_home()` (IND-02 enforces)
5. **Sunset policy:** new features MUST NOT add new `OPENCLAW_*` readers; existing readers get comment `# legacy: ADR-003`

- [ ] **Step 3:** Cross-link from `OPENCLAW_ENV_LEGACY.md` and `path-contract.md`

- [ ] **Step 4:** Mark IND-01 done in backlog + append `docs/evolution_log.md` row (docs-only ok if no code yet)

- [ ] **Step 5:** Commit

```bash
git add docs/adr/003-runtime-env-aliases.md docs/OPENCLAW_ENV_LEGACY.md docs/path-contract.md docs/MIMIR_EXEC_BACKLOG.md docs/evolution_log.md
git commit -m "docs(IND-01): ADR-003 runtime env legacy alias table"
```

---

## Task 2: Bare HERMES_HOME grep gate (IND-02)

**Files:**
- Create: `tests/contract/test_runtime_path_independence_ind02.py`
- Modify: `run_ralph_tier0.sh` (add pytest path if not already picked up)
- Modify: `docs/MIMIR_EXEC_BACKLOG.md` (IND-02 → `[x]`)

**Design:** Fail tier0 if **new** bare defaults appear in runtime trees. Allowlist documented legacy files from `path-contract.md` §5.

- [ ] **Step 1: Write failing test**

Create `tests/contract/test_runtime_path_independence_ind02.py`:

```python
"""IND-02: runtime trees must not use bare HERMES_HOME as default home root."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = ("agent", "gateway", "tools", "mimir_cli")
EXCLUDE_PARTS = frozenset({"hermes_cli", "tests"})

# Files explicitly listed in path-contract.md §5 (historical / migration only)
ALLOWLIST = frozenset(
    {
        "mimir_cli/paths.py",
        "tools/environments/file_sync.py",
        "tools/credential_files.py",
        "mimir_cli/gateway.py",
    }
)

# Match os.getenv("HERMES_HOME") or os.environ.get("HERMES_HOME") used as primary default
# without MIMIR_AETHER_HOME in same function — heuristic: line contains HERMES_HOME assignment to expanduser/default
BAD_LINE = re.compile(
    r'getenv\s*\(\s*["\']HERMES_HOME["\']|environ\.get\s*\(\s*["\']HERMES_HOME["\']'
)


def _iter_py_files():
    for dirname in SCAN_DIRS:
        base = ROOT / dirname
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if EXCLUDE_PARTS.intersection(path.parts):
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel in ALLOWLIST:
                continue
            yield rel, path


def test_no_bare_hermes_home_getenv_in_runtime_trees():
    violations: list[str] = []
    for rel, path in _iter_py_files():
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "legacy" in line.lower() or "ADR-003" in line:
                continue
            if BAD_LINE.search(line) and "get_mimir_home" not in line:
                violations.append(f"{rel}:{i}: {stripped[:120]}")
    assert not violations, "bare HERMES_HOME getenv (use get_mimir_home):\n" + "\n".join(violations[:30])
```

- [ ] **Step 2:** Run test — expect PASS or fix violations

```bash
pytest tests/contract/test_runtime_path_independence_ind02.py -v
```

If violations: refactor each site to `get_mimir_home()` or add `# legacy: ADR-003` + allowlist entry with PR justification.

- [ ] **Step 3:** Full tier0

```bash
./run_ralph_tier0.sh
```

- [ ] **Step 4:** Commit + backlog + evolution_log

```bash
git commit -am "test(IND-02): contract gate bare HERMES_HOME in runtime trees"
```

---

## Task 3: MIMIR_SESSION_DB alias (IND-03)

**Files:**
- Modify: `mimir_constants.py` — add `get_mimir_session_search_db_path() -> Path`
- Modify: `tools/session_search_tool.py` — use resolver
- Modify: `tests/gateway/test_session_search_incremental.py` — test both env names
- Create: `tests/contract/test_mimir_session_db_ind03.py`
- Modify: `docs/path-contract.md`, `docs/phase0/memory-retrieval-baseline.md`
- Modify: `docs/MIMIR_EXEC_BACKLOG.md` (IND-03 → `[x]`)

- [ ] **Step 1: Write failing test**

`tests/contract/test_mimir_session_db_ind03.py`:

```python
import os
from pathlib import Path

import mimir_constants


def test_mimir_session_db_primary(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENCLAW_SESSION_DB", raising=False)
    monkeypatch.setenv("MIMIR_SESSION_DB", str(tmp_path / "custom.db"))
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    assert mimir_constants.get_mimir_session_search_db_path() == tmp_path / "custom.db"


def test_openclaw_session_db_legacy_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("MIMIR_SESSION_DB", raising=False)
    monkeypatch.setenv("OPENCLAW_SESSION_DB", str(tmp_path / "legacy.db"))
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    assert mimir_constants.get_mimir_session_search_db_path() == tmp_path / "legacy.db"


def test_mimir_session_db_wins_over_openclaw(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_SESSION_DB", str(tmp_path / "new.db"))
    monkeypatch.setenv("OPENCLAW_SESSION_DB", str(tmp_path / "old.db"))
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    assert mimir_constants.get_mimir_session_search_db_path() == tmp_path / "new.db"
```

- [ ] **Step 2:** Run test — expect FAIL

```bash
pytest tests/contract/test_mimir_session_db_ind03.py -v
```

- [ ] **Step 3:** Implement in `mimir_constants.py`

```python
def get_mimir_session_search_db_path() -> Path:
    """Session search SQLite path (IND-03).

    Precedence: MIMIR_SESSION_DB > OPENCLAW_SESSION_DB (legacy) > data/sessions_search.db
    """
    override = os.getenv("MIMIR_SESSION_DB", "").strip()
    if override:
        return Path(override)
    legacy = os.getenv("OPENCLAW_SESSION_DB", "").strip()
    if legacy:
        return Path(legacy)
    return get_mimir_data_dir() / "sessions_search.db"
```

- [ ] **Step 4:** Wire `SessionSearchDB.__init__` to use `get_mimir_session_search_db_path()` when `db_path is None`

- [ ] **Step 5:** Run all related tests + tier0

```bash
pytest tests/contract/test_mimir_session_db_ind03.py tests/gateway/test_session_search_incremental.py -v
./run_ralph_tier0.sh
```

- [ ] **Step 6:** Update docs + backlog + evolution_log; commit

```bash
git commit -am "feat(IND-03): MIMIR_SESSION_DB with OPENCLAW_SESSION_DB legacy read"
```

---

## Task 4: Night 1 checkpoint + PR

**Files:**
- Modify: `docs/MAINLINE_STATUS.md` (Wave D partial; D7 🟡)
- Modify: `docs/MIMIR_LIU_CURSOR_BRIDGE.md` §4 one-line morning report

- [ ] **Step 1:** `verification-before-completion` — paste tier0 tail (267+2 or higher)

- [ ] **Step 2:** `finishing-a-development-branch` — push + PR

```bash
git push -u origin feat/p2-long-indep-night1
gh pr create --title "P2-LONG-INDEP Night 1: IND-01～03 (D7 partial)" --body "$(cat <<'EOF'
## Summary
- ADR-003 legacy env alias table (IND-01)
- Contract test: no bare HERMES_HOME defaults in runtime trees (IND-02)
- MIMIR_SESSION_DB + OPENCLAW_SESSION_DB read fallback (IND-03)

## Test plan
- [x] ./run_ralph_tier0.sh (267+2+new tests)
- [ ] 刘哥 morning: optional `mimir_health_check.sh --quick` (no gateway code touched)

## Next
IND-04 mimicore boundary ADR · IND-05 P3-0 single-writer (separate PR)
EOF
)"
```

- [ ] **Step 3:** If CI green and bridge §1 常备授权 applies → merge to main; else leave PR open with §4 note

---

## Morning report template (paste to bridge §4)

```markdown
| 2026-05-26 | **IND Night1** | **Cursor** | IND-01～03 · PR #N · tier0 XXX+2 · D7 🟡 · 下一粒 IND-04 |
```

---

## Stop conditions (do NOT force through)

| Signal | Action |
|--------|--------|
| tier0 fails 3× same test | Stop; leave WIP branch + bridge note |
| IND-02 allowlist >5 new files | Stop; ask 刘哥 — scope creep |
| Need `persistent.json` writer changes | That's IND-05 — stop |
| Submodule mimicore pointer change | Stop unless intentional |

---

## Self-review checklist

- [ ] ADR-003 covers all env vars found in Task 1 inventory
- [ ] No placeholders in commits
- [ ] `data/persistent.json` not committed
- [ ] evolution_log row appended for agent/gateway/tools touches
