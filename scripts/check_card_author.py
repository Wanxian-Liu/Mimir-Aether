#!/usr/bin/env python3
"""Non-blocking frontmatter attribution check for four-party wiki cards (A2).

Why a script and not a git hook: a card is content. Refusing a commit because
one frontmatter line is spelled differently would block the shared knowledge
base for a cosmetic reason, and the ruling (2026-09-13) is explicitly
non-blocking. So this reports; it never rejects.

Canonical form (agreed in wiki/discussions/README.md section 1):

    author: mimir        # one of: mimir | hermes | openclaw | loki

Measured 2026-09-13 across the 46 top-level discussion cards: 5 carry
``author: mimir``, 1 carries ``by: mimir``, and 40 carry no attribution field at
all. Legacy spellings are reported as ``legacy`` -- fixing them is optional
housekeeping, not a violation.

Usage
    python3 scripts/check_card_author.py [path ...]      # default ~/wiki/discussions
    python3 scripts/check_card_author.py --recursive     # descend into subdirectories
    python3 scripts/check_card_author.py --json
    python3 scripts/check_card_author.py --quiet         # exit code only

The exit code is always 0 unless the checker itself fails to run: the report
carries the findings, the exit code does not gate anything.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ALLOWED_IDS = ("mimir", "hermes", "openclaw", "loki")

_CANONICAL_RE = re.compile(r"^author:\s*(\S+)\s*$")
_LEGACY_RE = re.compile(r"^(?:author|by|agent):\s*(\S+)\s*$")
_FRONTMATTER_BOUNDARY = "---"


def _frontmatter_lines(text: str) -> list[str]:
    """Return the frontmatter block as lines, or [] when there is none."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_BOUNDARY:
        return []
    for idx in range(1, len(lines)):
        if lines[idx].strip() == _FRONTMATTER_BOUNDARY:
            return lines[1:idx]
    return []


def classify(path: Path) -> dict:
    """Classify one card's attribution field. Never raises for bad cards."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:  # an unreadable file is a finding, not a crash
        return {"path": str(path), "status": "unreadable", "detail": str(exc)}

    fm = _frontmatter_lines(text)
    if not fm:
        return {"path": str(path), "status": "no-frontmatter", "detail": ""}

    canonical: str | None = None
    legacy: list[tuple[str, str]] = []
    for line in fm:
        stripped = line.rstrip()
        if not stripped or stripped.startswith("#"):
            continue
        m_canon = _CANONICAL_RE.match(stripped)
        if m_canon:
            canonical = m_canon.group(1)
            continue
        m_legacy = _LEGACY_RE.match(stripped)
        if m_legacy:
            legacy.append((stripped.split(":", 1)[0], m_legacy.group(1)))

    if canonical is None and not legacy:
        return {"path": str(path), "status": "missing", "detail": ""}

    if canonical is None:
        field, value = legacy[0]
        return {"path": str(path), "status": "legacy", "detail": f"{field}: {value}", "value": value}

    if canonical.lower() not in ALLOWED_IDS:
        return {"path": str(path), "status": "unknown-id", "detail": canonical, "value": canonical}

    if canonical != canonical.lower():
        return {"path": str(path), "status": "legacy", "detail": f"author: {canonical}", "value": canonical}

    return {"path": str(path), "status": "ok", "detail": canonical, "value": canonical}


def collect(paths: list[str], recursive: bool = False) -> list[Path]:
    """Resolve the inputs to markdown files.

    Non-recursive by default: the discussion room keeps archives and working
    directories under the same root, and silently folding them into the
    headline number would overstate the gap (measured: 46 top-level cards vs
    340 files recursively).
    """
    found: list[Path] = []
    for raw in paths:
        p = Path(os.path.expanduser(raw))
        if p.is_dir():
            found.extend(sorted(p.rglob("*.md") if recursive else p.glob("*.md")))
        elif p.is_file():
            found.append(p)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="non-blocking wiki card attribution check")
    parser.add_argument("paths", nargs="*", default=["~/wiki/discussions"])
    parser.add_argument("--recursive", action="store_true", help="descend into subdirectories")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--quiet", action="store_true", help="no report, exit code only")
    args = parser.parse_args(argv)

    path_args = args.paths or ["~/wiki/discussions"]
    results = [classify(p) for p in collect(path_args, recursive=args.recursive)]

    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    if args.json:
        print(json.dumps({"counts": counts, "cards": results}, ensure_ascii=False, indent=2))
    elif not args.quiet:
        print(f"cards checked : {len(results)}")
        for status in sorted(counts):
            print(f"  {status:16s} {counts[status]}")
        flagged = [r for r in results if r["status"] != "ok"]
        if flagged:
            print("\nneeds attention (non-blocking):")
            for r in flagged:
                detail = f" -- {r['detail']}" if r.get("detail") else ""
                print(f"  [{r['status']}] {r['path']}{detail}")
        else:
            print("\nall cards carry a canonical author id")

    return 0  # non-blocking by design


if __name__ == "__main__":
    sys.exit(main())
