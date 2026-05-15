"""CLI path helpers — Mimir home vs legacy OpenClaw layout.

Canonical runtime resolution lives in :mod:`mimir_constants` / :mod:`mimiraether_constants`.
This module is the narrow façade for ``mimir_cli`` user-facing strings and migration defaults.
"""

from __future__ import annotations

from pathlib import Path


def get_cli_project_home() -> Path:
    """Return resolved MimirAether home (``MIMIR_AETHER_HOME`` when set)."""
    from mimiraether_constants import get_mimiraether_home

    return get_mimiraether_home()


def display_cli_project_home() -> str:
    """Human-readable home path (abbreviates the user's home directory as ``~``)."""
    from mimir_constants import display_mimir_home

    return display_mimir_home()


def openclaw_migration_source_default() -> Path:
    """Default OpenClaw data directory for ``claw migrate`` / setup detection."""
    return Path.home() / ".openclaw"


def openclaw_style_project_root_for_user(home: Path) -> Path:
    """Historical clone path ``<home>/.openclaw/projects/MimirAether`` (sudo remapping, docs only).

    Not the default runtime data root for unset ``MIMIR_AETHER_HOME``; see
    ``docs/path-contract.md`` §历史路径与豁免目录.
    """
    return home / ".openclaw" / "projects" / "MimirAether"
