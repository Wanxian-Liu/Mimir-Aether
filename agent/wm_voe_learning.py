"""WM Phase0: VoE surprise → JSONL learning events (WB-B02).

Append-only audit trail under ``$MIMIR_AETHER_HOME/data/wm_phase0/``.
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


def default_surprise_events_path() -> Path:
    return get_mimir_home() / "data" / "wm_phase0" / "surprise_events.jsonl"


def surprise_label_from_guard_message(guard_message: str) -> str:
    match = _SURPRISE_LABEL_RE.search(guard_message or "")
    if match:
        return match.group(1).strip()
    return "unknown"


def append_surprise_event(
    expected: str,
    actual: str,
    surprise_label: str,
    context_snapshot: dict,
    guard_message: str,
    path: Optional[Path] = None,
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
