"""Short-lived cache for idempotent read-only tool calls (bridge §6.21 tool_guardrails intent)."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, Optional, Tuple

_CACHE: Dict[str, Tuple[float, str]] = {}
_MAX_ENTRIES = 64
_DEFAULT_TTL_SEC = 300

_READ_ONLY_TOOLS = frozenset(
    {
        "read_file",
        "search_files",
        "session_search",
        "skill_view",
        "skills_list",
        "list_capsules",
        "get_capsule_by_id",
        "get_env",
        "clarify",
        "grep",
        "glob",
        "mimir_ops",
    }
)


def _enabled() -> bool:
    return os.environ.get("MIMIR_TOOL_CALL_CACHE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _ttl_sec() -> int:
    raw = os.environ.get("MIMIR_TOOL_CALL_CACHE_TTL_SEC", str(_DEFAULT_TTL_SEC)).strip()
    try:
        return max(30, int(raw))
    except ValueError:
        return _DEFAULT_TTL_SEC


def should_cache_tool(tool_name: str) -> bool:
    return _enabled() and (tool_name or "") in _READ_ONLY_TOOLS


def _cache_key(tool_name: str, arguments: Any) -> str:
    if isinstance(arguments, str):
        args_blob = arguments
    else:
        try:
            args_blob = json.dumps(arguments or {}, sort_keys=True, ensure_ascii=False)
        except TypeError:
            args_blob = str(arguments)
    digest = hashlib.sha256(f"{tool_name}\0{args_blob}".encode()).hexdigest()[:32]
    return f"{tool_name}:{digest}"


def get_cached(tool_name: str, arguments: Any) -> Optional[str]:
    if not should_cache_tool(tool_name):
        return None
    key = _cache_key(tool_name, arguments)
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, content = entry
    if time.time() - ts > _ttl_sec():
        _CACHE.pop(key, None)
        return None
    return content


def set_cached(tool_name: str, arguments: Any, content: str) -> None:
    if not should_cache_tool(tool_name) or not content:
        return
    if content.startswith("Error:"):
        return
    key = _cache_key(tool_name, arguments)
    if len(_CACHE) >= _MAX_ENTRIES:
        oldest = min(_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _CACHE.pop(oldest, None)
    _CACHE[key] = (time.time(), content)
