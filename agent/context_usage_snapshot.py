"""Persist last-known LLM context token usage for ops tools (AUTO-04)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from mimir_constants import get_mimir_home


def _snapshot_path() -> Path:
    path = Path(get_mimir_home()) / "data" / "ops" / "last_context_usage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_context_usage_snapshot(
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    context_length: int = 0,
    threshold_tokens: int = 0,
    message_count: int = 0,
    session_key: str = "",
    session_id: str = "",
    model: str = "",
) -> None:
    """Write latest usage for mimir_ops /health-style reads (best-effort)."""
    payload: Dict[str, Any] = {
        "timestamp": time.time(),
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "total_tokens": int(total_tokens or 0),
        "context_length": int(context_length or 0),
        "threshold_tokens": int(threshold_tokens or 0),
        "message_count": int(message_count or 0),
        "session_key": (session_key or os.environ.get("HERMES_SESSION_KEY", "")).strip(),
        "session_id": (session_id or "").strip(),
        "model": (model or "").strip(),
    }
    try:
        _snapshot_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def read_context_usage_snapshot() -> Optional[Dict[str, Any]]:
    path = _snapshot_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None
