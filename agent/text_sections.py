"""Select the most recent dated section out of a markdown file.

Why this exists (2026-09-13, B1 fix - Liu approved option 2)
------------------------------------------------------------
Two call sites used to slice the **head** of ``<mimir_home>/NEXT_SESSION.md``:

* ``agent/prompt_builder.py::_build_cross_session_context`` - the
  ``<cross-session-context>`` block injected into the system prompt.
* ``agent/cross_session_retrieval.py::_next_session_snippet`` - the L2
  retrieval-query derivation.

Because the file is edited by *prepending/rewriting* rather than by a strict
convention, a stale section could permanently occupy the head.  Real incident:
from 2026-08-21 to 2026-09-12 an obsolete "IQ55-60" block was injected every
turn because it sat in the first 400 characters.

Rather than mandating a writing convention (append-only ordering, or a
``<!-- CURRENT -->`` marker - both add a single point of discipline that a
future session can forget), we pick the section whose heading carries the
**newest** ``YYYY-MM-DD`` date.  That already matches how the file is written,
needs zero migration, and is robust to both "newest at top" and "newest at
bottom" layouts.

Fallback: when no heading carries a date, return the **tail** of the text
(newest content is far more likely to be at the bottom than the top).
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

__all__ = ["latest_dated_section"]

# ``YYYY-MM-DD`` anywhere inside a heading line.
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
# A markdown heading: leading hashes + optional spaces + title.
_HEADING_RE = re.compile(r"(?m)^(#{1,6})[ \t]*(.*)$")


def _date_key(date: str) -> int:
    """``YYYY-MM-DD`` -> comparable int (drops the separators)."""
    return int(date.replace("-", ""))


def _dated_headings(text: str) -> List[Tuple[int, int, str]]:
    """Return ``(start_offset, level, date)`` for each dated heading."""
    found: List[Tuple[int, int, str]] = []
    for match in _HEADING_RE.finditer(text):
        date_match = _DATE_RE.search(match.group(2))
        if date_match:
            found.append((match.start(), len(match.group(1)), date_match.group(0)))
    return found


def _parent_heading_start(text: str, start: int, level: int) -> Optional[int]:
    """Offset of the nearest preceding heading shallower than ``level``."""
    parent: Optional[int] = None
    for match in _HEADING_RE.finditer(text[:start]):
        if len(match.group(1)) < level:
            parent = match.start()
    return parent


def _section_end(text: str, start: int, level: int) -> int:
    """Offset of the next heading at ``level`` or shallower, else ``len(text)``."""
    for match in _HEADING_RE.finditer(text, start + 1):
        if len(match.group(1)) <= level:
            return match.start()
    return len(text)


def latest_dated_section(text: str, max_len: int) -> str:
    """Newest dated section of ``text``, capped at ``max_len`` characters.

    Returns ``""`` for empty input or a non-positive ``max_len``.  Dated dates
    are compared as ``YYYY-MM-DD`` values, which sorts correctly.

    When a dated heading is a *sub*-section, its nearest shallower ancestor
    heading is prepended so the excerpt keeps its context.
    """
    if max_len <= 0 or not text or not text.strip():
        return ""

    headings = _dated_headings(text)
    if not headings:
        # No dated heading: newest content is presumed to sit at the bottom.
        return text.strip()[-max_len:]

    # Newest date wins; tie-break on shallower level, then earliest position
    # (a top-level heading introduces its whole block, sub-sections included).
    newest = min(headings, key=lambda h: (-_date_key(h[2]), h[1], h[0]))
    start, level, _ = newest

    parent = _parent_heading_start(text, start, level)
    if parent is not None:
        start, level = parent, max(1, level - 1)

    section = text[start : _section_end(text, start, level)].strip()
    return section[:max_len]
