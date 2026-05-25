"""
IEVO-01 / D5-1: forbid pseudo-evolution markers in production evolution paths.

See docs/MIMIR_EV_L_INDUSTRIAL_LEARNING.md §12 (pseudo-evolution red line).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_FORBIDDEN_SUMMARY_PATTERNS = (
    re.compile(r"simulated\s*:\s*true", re.I),
    re.compile(r"simulated\s*=\s*true", re.I),
    re.compile(r"""['"]simulated['"]\s*:\s*true""", re.I),
)

_RUNTIME_SCAN_DIRS = ("agent", "gateway", "tools", "mimir_cli", "scripts")
_RUNTIME_EXCLUDE_PARTS = frozenset({"hermes_cli", "tests", "test_"})
_RUNTIME_ALLOWLIST = frozenset(
    {
        # patch apply simulation — not M6 pseudo-evolution
        "tools/patch_parser.py",
    }
)

_RUNTIME_BAD_LINE = re.compile(
    r"simulated\s*:\s*true|['\"]simulated['\"]\s*:\s*true",
    re.I,
)


def assert_evolution_summary_allowed(summary: str) -> None:
    """Raise ValueError if summary would mark a pseudo-evolution row (D5-1)."""
    text = (summary or "").strip()
    if not text:
        return
    for pat in _FORBIDDEN_SUMMARY_PATTERNS:
        if pat.search(text):
            raise ValueError(
                "M6 evolution summary must not contain simulated:true (D5-1 / IEVO-01). "
                "Run ./run_ralph_tier0.sh and append a row with the real exit_code."
            )


def scan_runtime_trees_for_simulated_evolution_markers(
    root: Path | None = None,
) -> list[str]:
    """Return violation lines like rel/path:lineno: snippet."""
    base = root or ROOT
    violations: list[str] = []
    for dirname in _RUNTIME_SCAN_DIRS:
        tree = base / dirname
        if not tree.is_dir():
            continue
        for path in tree.rglob("*.py"):
            if _RUNTIME_EXCLUDE_PARTS.intersection(path.parts):
                continue
            if any(part.startswith("test_") for part in path.parts):
                continue
            rel = path.relative_to(base).as_posix()
            if rel in _RUNTIME_ALLOWLIST:
                continue
            for i, line in enumerate(
                path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
            ):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "IEVO-01" in line or "D5-1" in line:
                    continue
                if _RUNTIME_BAD_LINE.search(line):
                    violations.append(f"{rel}:{i}: {stripped[:120]}")
    return violations
