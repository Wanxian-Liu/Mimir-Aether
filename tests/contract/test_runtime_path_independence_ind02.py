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
        for i, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "legacy" in line.lower() or "ADR-003" in line:
                continue
            if BAD_LINE.search(line) and "get_mimir_home" not in line:
                violations.append(f"{rel}:{i}: {stripped[:120]}")
    assert not violations, "bare HERMES_HOME getenv (use get_mimir_home):\n" + "\n".join(
        violations[:30]
    )
