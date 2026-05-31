"""ADR-002 / ENGINE-P3W-01: unified memory write routing (capsules + persistent).

Path A: HTML capsules under ``$MIMIR_AETHER_HOME/memory/capsules/``.
Path B: ``persistent.json`` via ADR-001 ``persistent_store`` (single writer).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from mimir_constants import get_mimir_home
from agent import persistent_store


def get_capsules_dir() -> Path:
    return get_mimir_home() / "memory" / "capsules"


def get_persistent_path() -> Path:
    return persistent_store.get_persistent_path()


def load_persistent() -> dict:
    return persistent_store.load()


def write_persistent_mutator(
    mutator: Callable[[dict], None],
    path: Optional[Path] = None,
) -> None:
    persistent_store.read_modify_write(mutator, path=path)


def save_persistent_merged(
    memory_data: dict,
    merge_fn: Callable[[dict, dict], dict],
    path: Optional[Path] = None,
) -> bool:
    return persistent_store.save_merged(memory_data, merge_fn, path)


def write_capsule_html(*, filepath: Path, html: str) -> None:
    """Publish one capsule HTML file (path A)."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(html, encoding="utf-8")
