"""Skill path guard — block traversal / injection for skill evolution writes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

_SKILL_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")


def is_valid_skill_target(name: str) -> bool:
    """Return True when target is a single safe skill directory name."""
    if not name or not isinstance(name, str):
        return False
    name = name.strip()
    if not name or name in {".", ".."}:
        return False
    if "/" in name or "\\" in name or ".." in name:
        return False
    return bool(_SKILL_NAME_RE.match(name))


def _is_under_base(candidate: Path, base: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def resolve_skill_dir(skills_dir: Path, target: str) -> Optional[Path]:
    """Resolve an existing skill directory under skills_dir, or None if unsafe."""
    if not is_valid_skill_target(target):
        return None
    base = skills_dir.resolve()
    candidate = (base / target).resolve()
    if not _is_under_base(candidate, base):
        return None
    if not candidate.is_dir():
        return None
    return candidate


def resolve_skill_write_dir(skills_dir: Path, target: str) -> Optional[Path]:
    """Resolve a write target under skills_dir (may not exist yet)."""
    if not is_valid_skill_target(target):
        return None
    base = skills_dir.resolve()
    candidate = (base / target).resolve()
    if not _is_under_base(candidate, base):
        return None
    return candidate
