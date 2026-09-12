#!/usr/bin/env python3
"""Non-blocking check: can NEXT_SESSION.md be excerpted by newest-dated section?

Companion to ``agent/text_sections.latest_dated_section`` (B1 fix, 2026-09-13).
The excerpt helper picks the section whose heading carries the newest
``YYYY-MM-DD``; when *no* heading is dated it silently falls back to a tail
slice.  This script makes that fallback visible at wrap-up time, so a rewrite
that drops the date from the heading cannot quietly change what gets injected
into the system prompt.

Advisory only -- always exits 0 (same stance as ``check_card_author.py``).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.text_sections import _dated_headings  # noqa: E402

_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def main() -> int:
    from mimir_constants import get_mimir_home

    path = get_mimir_home() / "NEXT_SESSION.md"
    if not path.is_file():
        print(f"[check-next-session] missing: {path}")
        return 0

    text = path.read_text(encoding="utf-8")
    dated = _dated_headings(text)
    if not dated:
        print(
            "[check-next-session] WARN: no heading carries a YYYY-MM-DD date -> "
            "excerpt falls back to a TAIL slice (head-order independent, but "
            "unpinned). Add the date to the top-level heading."
        )
        return 0

    newest = max(h[2] for h in dated)
    print(f"[check-next-session] OK: newest dated section = {newest} ({len(dated)} dated heading(s))")
    undated = [
        line
        for line in text.splitlines()
        if line.startswith("#") and not _DATE_RE.search(line)
    ]
    if undated:
        print(f"[check-next-session] note: {len(undated)} undated heading(s) present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
