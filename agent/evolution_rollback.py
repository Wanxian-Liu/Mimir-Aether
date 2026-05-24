"""STAB-05: rollback guardrails for skill self-evolution (FIX/DERIVED/CAPTURED)."""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from tools.skills_guard import format_scan_report, scan_skill, should_allow_install

    _GUARD_AVAILABLE = True
except ImportError:
    _GUARD_AVAILABLE = False


def security_scan_skill_dir(skill_dir: Path) -> Optional[str]:
    """Scan skill after write. Returns error string if install blocked, else None."""
    if not _GUARD_AVAILABLE:
        return None
    try:
        result = scan_skill(skill_dir, source="agent-created")
        allowed, reason = should_allow_install(result)
        if allowed is not True:
            report = format_scan_report(result)
            label = "blocked" if allowed is False else "requires confirmation"
            return f"Security scan {label} this skill ({reason}):\n{report}"
    except Exception as exc:
        logger.warning("Security scan failed for %s: %s", skill_dir, exc, exc_info=True)
    return None


def save_skill_evolution_backup(skill_md: Path, content: str) -> Optional[Path]:
    """Persist pre-evolution SKILL.md under ``$MIMIR_AETHER_HOME/data/evolution_backups/``."""
    if not content:
        return None
    try:
        from mimir_constants import get_mimir_data_dir

        backup_dir = get_mimir_data_dir() / "evolution_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        dest = backup_dir / f"{skill_md.parent.name}-{stamp}.SKILL.md.bak"
        dest.write_text(content, encoding="utf-8")
        return dest
    except OSError as exc:
        logger.warning("Could not save evolution backup for %s: %s", skill_md, exc)
        return None


def write_skill_md_guarded(
    skill_dir: Path,
    skill_md: Path,
    new_content: str,
    *,
    prior_content: str,
) -> Optional[str]:
    """Write SKILL.md, run skills_guard, restore prior content on block."""
    backup_path = save_skill_evolution_backup(skill_md, prior_content)
    skill_md.write_text(new_content, encoding="utf-8")
    scan_error = security_scan_skill_dir(skill_dir)
    if scan_error:
        skill_md.write_text(prior_content, encoding="utf-8")
        msg = "Security scan blocked; rolled back in-place"
        if backup_path is not None:
            msg += f" (backup: {backup_path})"
        return f"{msg}: {scan_error}"
    return None


def remove_skill_directory(skill_dir: Path) -> None:
    """Best-effort cleanup when a new skill dir fails validation."""
    if skill_dir.exists():
        shutil.rmtree(skill_dir, ignore_errors=True)


def create_skill_dir_guarded(skill_dir: Path, skill_md: Path, content: str) -> Optional[str]:
    """Create a new skill directory + SKILL.md; remove dir if scan blocks."""
    created = False
    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        created = True
        skill_md.write_text(content, encoding="utf-8")
        scan_error = security_scan_skill_dir(skill_dir)
        if scan_error:
            remove_skill_directory(skill_dir)
            return f"Security scan blocked; removed new skill dir: {scan_error}"
    except OSError as exc:
        if created:
            remove_skill_directory(skill_dir)
        return f"Skill creation failed: {exc}"
    return None
