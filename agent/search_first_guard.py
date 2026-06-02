"""WA-A06.1: block tools until session_search for explicit cross-session user turns."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Sequence

_MARKER = "[search-first-guard]"
PREEMPTIVE_MARKER = "[preemptive-search]"
SESSION_SEARCH_TOOL = "session_search"
MAX_SEARCH_FIRST_NUDGES = 5

# Injected user-role messages (nudges / preemptive search) — not real user turns.
_INJECTED_USER_PREFIXES = (
    _MARKER,
    PREEMPTIVE_MARKER,
    "[MIMIR_SKILL_ROUTE_NUDGE]",
    "[MIMIR_MEMORY_NUDGE]",
    "[MIMIR_SKILL_NUDGE]",
    "[intent-action-guard]",
)


def _is_injected_user_message(content: str) -> bool:
    text = (content or "").strip()
    return any(text.startswith(prefix) for prefix in _INJECTED_USER_PREFIXES)

# Keep aligned with scripts/search_first_audit.py (WA-A06 exclusions).
RECALL_RE = re.compile(
    r"(上次|之前|历史|还记得|继续|查一下|查历史|world model|世界模型|IR-|decision|偏好|preference)",
    re.I,
)

EXPLICIT_CROSS_SESSION_RE = re.compile(
    r"(上次|之前(?:聊|说|做|提到|发|的)?|历史(?:决策|记录|对话|会话)|跨会话|"
    r"查(?:一下)?历史|还记得|我们之前|prior\s+(?:session|conversation)|"
    r"earlier\s+decision|IR-\d)",
    re.I,
)


def guard_enabled() -> bool:
    return os.environ.get("MIMIR_SEARCH_FIRST_GUARD", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def exclude_user_message(content: str) -> str:
    """False-positive class name, or '' if in-scope for search-first."""
    text = (content or "").strip()
    if not text:
        return "empty"
    if len(text) > 500 or re.search(r"[┌└│├─┤╭╮╯╰]", text):
        return "user_paste_block"
    if re.search(
        r"(放入\s*Bridge|写入\s*Bridge|bridge\s*§|MIMIR_LIU_CURSOR_BRIDGE)",
        text,
        re.I,
    ):
        return "bridge_write_task"
    if re.search(r"已经\s*new|/new\s*了|新对话.*继续", text, re.I):
        return "fresh_session_continue"
    if re.search(r"(刚刚聊|刚才聊|刚才说|刚才放|刚才的理解|this session)", text, re.I):
        return "same_session_recall"
    if re.match(r"继续(?:离席|入库|执行|推进|做|检查)", text):
        return "task_continuation"
    if re.search(r"(之前(?:所有)?给你发的|深度思考一遍.*之前)", text, re.I):
        return "same_session_synthesis"
    if re.search(r"(我给你|我发给你|如下(?:是)?|总结如下|被蒸馏过的)", text, re.I):
        return "user_provides_material"
    if re.search(r"世界模型|world model|JEPA|杨立昆", text, re.I):
        if not EXPLICIT_CROSS_SESSION_RE.search(text):
            return "topic_discussion_no_recall_ask"
    if RECALL_RE.search(text) and not EXPLICIT_CROSS_SESSION_RE.search(text):
        return "broad_recall_not_explicit"
    return ""


def cross_session_requires_search_first(user_text: str) -> bool:
    text = (user_text or "").strip()
    if not text or exclude_user_message(text):
        return False
    return bool(EXPLICIT_CROSS_SESSION_RE.search(text))


def _tool_name_from_call(call: Any) -> str:
    if isinstance(call, dict):
        if call.get("type") == "function" and isinstance(call.get("function"), dict):
            return str(call["function"].get("name") or "")
        return str(call.get("name") or "")
    return ""


def _normalize_messages(messages: Sequence[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in messages:
        if isinstance(m, dict):
            out.append(m)
            continue
        role = getattr(m, "role", None)
        if hasattr(role, "value"):
            role = role.value
        entry: Dict[str, Any] = {
            "role": str(role or ""),
            "content": getattr(m, "content", "") or "",
        }
        tool_calls = getattr(m, "tool_calls", None)
        if tool_calls:
            entry["tool_calls"] = tool_calls
        tool_call_id = getattr(m, "tool_call_id", None)
        if tool_call_id:
            entry["tool_call_id"] = tool_call_id
        name = getattr(m, "name", None)
        if name:
            entry["tool_name"] = name
        out.append(entry)
    return out


def last_user_text(messages: Sequence[Any]) -> str:
    for m in reversed(_normalize_messages(messages)):
        if m.get("role") == "user":
            content = m.get("content") or ""
            if isinstance(content, str) and _is_injected_user_message(content):
                continue
            return content.strip() if isinstance(content, str) else str(content)
    return ""


def session_search_used_in_slice(messages: Sequence[Any]) -> bool:
    for m in _normalize_messages(messages):
        role = m.get("role")
        if role == "tool":
            if m.get("tool_name") == SESSION_SEARCH_TOOL:
                return True
            content = str(m.get("content") or "")
            if SESSION_SEARCH_TOOL in content and "error" not in content.lower()[:80]:
                return True
        if role == "assistant":
            for call in m.get("tool_calls") or []:
                if _tool_name_from_call(call) == SESSION_SEARCH_TOOL:
                    return True
            content = str(m.get("content") or "")
            if SESSION_SEARCH_TOOL in content and "must call" not in content.lower():
                return True
    return False


def preemptive_search_in_slice(messages: Sequence[Any]) -> bool:
    for m in _normalize_messages(messages):
        if m.get("role") != "user":
            continue
        content = str(m.get("content") or "").strip()
        if content.startswith(PREEMPTIVE_MARKER):
            return True
    return False


def session_search_satisfied_since_last_user(messages: Sequence[Any]) -> bool:
    norm = _normalize_messages(messages)
    last_user_idx = -1
    for i, m in enumerate(norm):
        if m.get("role") == "user":
            content = str(m.get("content") or "")
            if _is_injected_user_message(content):
                continue
            last_user_idx = i
    if last_user_idx < 0:
        return False
    slice_msgs = norm[last_user_idx:]
    return session_search_used_in_slice(slice_msgs) or preemptive_search_in_slice(
        slice_msgs
    )


def block_tool_reason(tool_name: str, messages: Sequence[Any]) -> Optional[str]:
    if not guard_enabled():
        return None
    user_text = last_user_text(messages)
    if not cross_session_requires_search_first(user_text):
        return None
    if session_search_satisfied_since_last_user(messages):
        return None
    if (tool_name or "").strip() == SESSION_SEARCH_TOOL:
        return None
    return (
        "Cross-session recall: call session_search with a query about the user's "
        "topic before using other tools or answering from memory alone."
    )


def should_block_text_only_finish(
    messages: Sequence[Any],
    assistant_content: str,
    *,
    has_tool_schemas: bool,
) -> bool:
    if not guard_enabled() or not has_tool_schemas:
        return False
    if session_search_satisfied_since_last_user(messages):
        return False
    user_text = last_user_text(messages)
    if not cross_session_requires_search_first(user_text):
        return False
    if (assistant_content or "").strip():
        return True
    return True


def build_nudge_message() -> str:
    return (
        f"{_MARKER} The user asked about prior sessions or cross-session history. "
        "You must call session_search with a focused query before other tools or "
        "a text-only answer. Do not guess from memory alone."
    )
