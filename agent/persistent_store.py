"""Single-writer access to ``data/persistent.json`` (ADR-001 / IND-05)."""

from __future__ import annotations

import datetime
import json
import logging
import threading
import time
from pathlib import Path
from typing import Callable

from mimir_constants import get_mimir_data_dir

logger = logging.getLogger(__name__)

_REQUIRED_TOP_KEYS = frozenset({"version", "memory", "progress"})

_DEFAULT_MEMORY = {
    "key_decisions": [],
    "learned_patterns": [],
    "active_projects": [],
    "user_preferences": {},
    "skills_used": [],
}

_DEFAULT_PROGRESS = {
    "current_objective": None,
    "completed_milestones": [],
    "pending_tasks": [],
}

_write_lock = threading.Lock()


def _fill_missing_defaults(data: dict, source: str = "") -> set:
    """Auto-fill missing required top-level keys with sensible defaults.

    Returns the set of keys that were filled (empty = nothing was missing).
    """
    filled: set = set()
    if "version" not in data:
        data["version"] = "1.4"
        filled.add("version")
    if "memory" not in data or not isinstance(data.get("memory"), dict):
        data["memory"] = dict(_DEFAULT_MEMORY)
        filled.add("memory")
    if "progress" not in data or not isinstance(data.get("progress"), dict):
        data["progress"] = dict(_DEFAULT_PROGRESS)
        filled.add("progress")
    if filled and source:
        logger.info(
            "persistent.json auto-filled missing keys from %s: %s",
            source,
            sorted(filled),
        )
    return filled


def get_persistent_path() -> Path:
    return get_mimir_data_dir() / "persistent.json"


def _load_unlocked(path: Path | None = None) -> dict:
    """Load with validation; raises RuntimeError if unreadable (never returns {})."""
    target = path or get_persistent_path()

    for attempt in (1, 2):
        try:
            if target.exists():
                raw = target.read_text(encoding="utf-8")
                data = json.loads(raw)
                missing = _REQUIRED_TOP_KEYS - data.keys()
                if missing:
                    logger.warning(
                        "persistent.json missing critical keys: %s (attempt %d)",
                        missing,
                        attempt,
                    )
                    if attempt == 1:
                        time.sleep(0.1)
                        continue
                    # Auto-fill instead of crashing — transient missing keys
                    # are normal during hot-reload / concurrent mutation.
                    _fill_missing_defaults(data, source="disk-load")
                return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Failed to read persistent.json (attempt %d): %s", attempt, e
            )
            if attempt == 1:
                time.sleep(0.1)
                continue
        except ValueError:
            # _fill_missing_defaults already logged; continue
            if attempt == 1:
                time.sleep(0.1)
                continue

    bak_path = target.with_suffix(".json.bak")
    if bak_path.exists():
        try:
            data = json.loads(bak_path.read_text(encoding="utf-8"))
            missing = _REQUIRED_TOP_KEYS - data.keys()
            if not missing:
                logger.warning(
                    "persistent.json 不可读，已从 .bak 恢复 (%d 键)", len(data)
                )
                _write_atomic(bak_path.read_text(encoding="utf-8"), target)
                return data
            logger.error(".bak 备份也损坏，缺失: %s", missing)
        except Exception as e:
            logger.error("Failed to read .bak backup: %s", e)

    raise RuntimeError(
        "persistent.json 不可读且无可用备份——拒绝以空状态覆写磁盘。"
        "请检查 data/persistent.json 文件完整性。"
    )


def _write_atomic(raw: str, path: Path | None = None) -> None:
    target = path or get_persistent_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(raw, encoding="utf-8")
    tmp.replace(target)


def _save_unlocked(data: dict, path: Path | None = None) -> None:
    # Auto-fill missing required keys with defaults instead of rejecting.
    # IND-05 protection was too strict: transient missing keys during hot-reload
    # or concurrent mutation are normal — rejecting them silently drops memory.
    filled = _fill_missing_defaults(data, source="pre-save")
    if filled:
        logger.info(
            "persistent.json save: auto-filled %s before write", sorted(filled)
        )

    target = path or get_persistent_path()
    if target.exists():
        try:
            bak = target.with_suffix(".json.bak")
            bak.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError as e:
            logger.warning("Failed to create .bak backup: %s", e)

    raw = json.dumps(data, ensure_ascii=False, indent=2)
    _write_atomic(raw, target)


# ── ByteRover AKL fields (importance / maturity / last_access / decay_factor) ──


def _init_akl_fields(entry: dict) -> dict:
    """Initialize ByteRover AKL fields for a knowledge entry (kd or lp)."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    entry.setdefault("importance", 50)
    entry.setdefault("maturity", "draft")
    entry.setdefault("last_access", now)
    entry.setdefault("decay_factor", 0.95)
    return entry


def _update_akl_last_access(entry: dict) -> dict:
    """Update last_access timestamp; decay applied during distillation."""
    entry["last_access"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return entry


def load(path: Path | None = None) -> dict:
    with _write_lock:
        return _load_unlocked(path)


def save(data: dict, path: Path | None = None) -> None:
    with _write_lock:
        _save_unlocked(data, path)


def read_modify_write(mutator: Callable[[dict], None], path: Path | None = None) -> None:
    """Atomic read-modify-write under the global persistent lock."""
    with _write_lock:
        data = _load_unlocked(path) if (path or get_persistent_path()).exists() else {}
        if not data:
            raise RuntimeError("persistent.json missing; cannot read_modify_write")
        mutator(data)
        _save_unlocked(data, path)


def save_merged(
    memory_state: dict,
    merge: Callable[[dict, dict], dict],
    path: Path | None = None,
) -> bool:
    """Load disk snapshot, merge with ``memory_state``, save (CrossSessionMemory)."""
    target = path or get_persistent_path()
    try:
        with _write_lock:
            if target.exists():
                disk = _load_unlocked(target)
            else:
                disk = {}
            merged = merge(disk, memory_state)
            _save_unlocked(merged, target)
        return True
    except (RuntimeError, ValueError, OSError, IOError) as e:
        logger.warning("persistent save_merged failed: %s", e)
        return False
