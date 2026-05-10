#!/usr/bin/env python3
"""Non-blocking advisory: count ``.openclaw`` literals under agent/gateway/tools.

Excludes vendored ``tools/hermes_cli/``. Exits 0 always. Warns on stderr when the
match count exceeds ``OPENCLAW_STRING_WARN_THRESHOLD`` (default: 60).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("agent", "gateway", "tools")
EXCLUDE_DIR_NAMES = frozenset({"hermes_cli"})
_PATTERN = re.compile(r"\.openclaw")


def _count_matches() -> int:
    total = 0
    for dirname in SCAN_DIRS:
        base = ROOT / dirname
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if EXCLUDE_DIR_NAMES.intersection(path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            total += len(_PATTERN.findall(text))
    return total


def main() -> None:
    threshold = int(os.environ.get("OPENCLAW_STRING_WARN_THRESHOLD", "60"))
    n = _count_matches()
    if n > threshold:
        print(
            f"[warn] .openclaw literals under {list(SCAN_DIRS)} "
            f"(excluding {sorted(EXCLUDE_DIR_NAMES)}): {n} matches "
            f"(threshold {threshold}; adjust OPENCLAW_STRING_WARN_THRESHOLD)",
            file=sys.stderr,
        )
    else:
        print(
            f"[ok] .openclaw literal scan: {n} matches (threshold {threshold})",
            flush=True,
        )


if __name__ == "__main__":
    main()
