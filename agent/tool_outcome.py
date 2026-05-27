"""Infer tool call success from dispatcher return strings (IQ-EVO-48)."""

from __future__ import annotations

import json
from typing import Tuple


def infer_tool_success(tool_result: str) -> Tuple[bool, str]:
    """Return (success, error_message) from a tool dispatcher result string.

    Rules (minimal):
    - Parseable JSON object with non-empty top-level ``error`` → failure.
    - Top-level ``success`` is false → failure.
    - Non-JSON or JSON without those signals → success (preserve legacy behavior).
    """
    if not tool_result:
        return True, ""
    text = tool_result.strip()
    if not text.startswith("{"):
        return True, ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return True, ""
    if not isinstance(data, dict):
        return True, ""

    err = data.get("error")
    if err is not None and str(err).strip():
        return False, str(err).strip()[:500]

    if data.get("success") is False:
        msg = data.get("message") or data.get("detail") or "success=false"
        return False, str(msg)[:500]

    return True, ""


__all__ = ["infer_tool_success"]
