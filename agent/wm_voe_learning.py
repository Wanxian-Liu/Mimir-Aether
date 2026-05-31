"""WM Phase0/1.1: VoE surprise → JSONL audit + learned recall index.

Phase0: append-only JSONL under ``data/wm_phase0/`` (WB-B02).
Phase1.1: structured index under ``data/wm_phase11/`` (WM-P11-01).

Default off via ``MIMIR_WM_VOE_LEARNING``; write failures log warning only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from mimir_constants import get_mimir_home

logger = logging.getLogger(__name__)

_SURPRISE_LABEL_RE = re.compile(r"SURPRISE_DETECTED:\s*(.+?)\s*—")


def is_wm_voe_learning_enabled() -> bool:
    return os.environ.get("MIMIR_WM_VOE_LEARNING", "0").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def is_wm_voe_replan_ctx_enabled() -> bool:
    return os.environ.get("MIMIR_WM_VOE_REPLAN_CTX", "0").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def is_wm_voe_recall_enabled() -> bool:
    return os.environ.get("MIMIR_WM_VOE_RECALL", "0").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def default_surprise_events_path() -> Path:
    return get_mimir_home() / "data" / "wm_phase0" / "surprise_events.jsonl"


def default_learned_surprises_path() -> Path:
    return get_mimir_home() / "data" / "wm_phase11" / "learned_surprises.json"


def normalize_pair(expected: str, actual: str) -> str:
    exp = (expected or "").strip().lower()
    act = (actual or "").strip().lower()
    return f"{exp}|{act}"


def surprise_label_from_guard_message(guard_message: str) -> str:
    match = _SURPRISE_LABEL_RE.search(guard_message or "")
    if match:
        return match.group(1).strip()
    return "unknown"


def _empty_learned_index() -> dict[str, Any]:
    return {"schema_version": 1, "entries": {}}


def _load_learned_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_learned_index()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
            return _empty_learned_index()
        data.setdefault("schema_version", 1)
        return data
    except Exception as exc:
        logger.warning("WM VoE learned index load failed: %s", exc)
        return _empty_learned_index()


def _learning_hint(expected: str, actual: str, surprise_label: str) -> str:
    return (
        f"Prior VoE ({surprise_label}): expected '{expected}' "
        f"but got '{actual}'; do not repeat same assumption."
    )


def format_wm_learning_context(
    expected: str,
    actual: str,
    surprise_label: str,
) -> str:
    """Replan-facing VoE learning summary (WM-P11-02)."""
    return _learning_hint(expected, actual, surprise_label)


_pending_wm_learning_context: str = ""


def set_pending_wm_learning_context(text: str) -> None:
    """Queue VoE learning text for the next model call (WM-P11-OPS)."""
    global _pending_wm_learning_context
    _pending_wm_learning_context = (text or "").strip()


def pop_wm_learning_context_block_for_prompt() -> str:
    """Consume pending VoE context once; empty when replan ctx env is off."""
    global _pending_wm_learning_context
    if not is_wm_voe_replan_ctx_enabled():
        _pending_wm_learning_context = ""
        return ""
    block = _pending_wm_learning_context
    _pending_wm_learning_context = ""
    if not block:
        return ""
    return f"<wm-voe-learning>\n{block}\n</wm-voe-learning>"


def reset_pending_wm_learning_context_for_test() -> None:
    """Test helper."""
    global _pending_wm_learning_context
    _pending_wm_learning_context = ""


def lookup_learned_surprise(
    expected: str,
    actual: str,
    path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    target = path or default_learned_surprises_path()
    key = normalize_pair(expected, actual)
    entry = _load_learned_index(target).get("entries", {}).get(key)
    if not entry:
        return None
    return dict(entry)


def record_surprise_learning(
    expected: str,
    actual: str,
    surprise_label: str,
    path: Optional[Path] = None,
) -> None:
    """Upsert one learned VoE pair into the recall index. No-op when learning disabled."""
    if not is_wm_voe_learning_enabled():
        return

    target = path or default_learned_surprises_path()
    key = normalize_pair(expected, actual)
    now = time.time()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        index = _load_learned_index(target)
        entries = index.setdefault("entries", {})
        existing = entries.get(key)
        if existing:
            existing["last_seen"] = now
            existing["hit_count"] = int(existing.get("hit_count", 1)) + 1
        else:
            entries[key] = {
                "expected": expected,
                "actual": actual,
                "surprise_label": surprise_label,
                "first_seen": now,
                "last_seen": now,
                "hit_count": 1,
                "learning_hint": _learning_hint(expected, actual, surprise_label),
            }
        target.write_text(
            json.dumps(index, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("WM VoE learned index record failed: %s", exc)


def append_surprise_event(
    expected: str,
    actual: str,
    surprise_label: str,
    context_snapshot: dict,
    guard_message: str,
    path: Optional[Path] = None,
    learned_path: Optional[Path] = None,
) -> None:
    """Append one VoE surprise event. No-op when learning is disabled."""
    if not is_wm_voe_learning_enabled():
        return

    target = path or default_surprise_events_path()
    event = {
        "schema_version": 1,
        "event_type": "voe_surprise",
        "timestamp": time.time(),
        "expected": expected,
        "actual": actual,
        "surprise_label": surprise_label,
        "context_snapshot": dict(context_snapshot or {}),
        "guard_message": guard_message,
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("WM VoE learning append failed: %s", exc)
        return

    record_surprise_learning(
        expected,
        actual,
        surprise_label,
        path=learned_path,
    )
