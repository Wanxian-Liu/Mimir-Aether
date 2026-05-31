"""Synthetic session IDs from tier0/contract tests — must not touch production home."""

from __future__ import annotations

from pathlib import Path

# Keep in sync with tests/agent/test_post_close_analysis.py and iq_p3 baseline.
SYNTHETIC_SESSION_PREFIXES = (
    "iq07-",
    "iq40-",
    "fb-sess",
    "iqevo",
    "ne-sess",
    "async-sess",
    "no-evolve",
)

_SYNTHETIC_EXACT = frozenset(
    {
        "iq07-sess",
        "iq40-sess",
        "fb-sess",
        "s",
        "ne-sess",
    }
)


def is_synthetic_session_id(session_id: str) -> bool:
    sid = (session_id or "").strip().lower()
    if not sid:
        return False
    if sid in _SYNTHETIC_EXACT:
        return True
    return any(sid.startswith(p) for p in SYNTHETIC_SESSION_PREFIXES)


def is_default_mimir_home(home: Path | None = None) -> bool:
    from mimir_constants import get_mimir_home

    resolved = (home or get_mimir_home()).expanduser().resolve()
    default = (Path.home() / ".mimiraether").resolve()
    return resolved == default


def evolution_allowed_for_session(session_id: str) -> bool:
    """Block tier0 test sessions from mutating production home or logs."""
    if not is_synthetic_session_id(session_id):
        return True
    return not is_default_mimir_home()
