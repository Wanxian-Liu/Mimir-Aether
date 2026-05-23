"""Intent-action guard: block text-only turns that defer work the user asked for."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Sequence

MAX_INTENT_NUDGES = 2

_NUDGE_MARKER = "[intent-action-guard]"

# User asked for grounded file/doc work (not casual chat).
_TASK_GROUNDING_RE = re.compile(
    r"(?i)"
    r"playbook|ev-l|ev_l|勾选|对齐|收尾|"
    r"read_file|读取|读一下|读\s*[\w./-]+\.(md|py|yaml|json|txt)|"
    r"看看.*(文件|playbook|backlog|docs/)|"
    r"打开.*\.(md|py)|"
    r"patch|修改.*docs/|更新.*docs/|"
    r"不用回答|只.*结果|直接做|直接开始"
)

# Assistant promised action or claimed done without tools in session.
_DEFERRAL_RE = re.compile(
    r"(?i)"
    r"先(读|看|查看|读取|打开)|现在(读|看|读取|调)|我会|让我|我去|"
    r"先看看|接下来|稍后|马上(读|看|调)|"
    r"✅|完成|对齐完成|已读|已经读"
)

_META_PRESSURE_RE = re.compile(
    r"(?i)"
    r"看了么|读了吗|你读了|诚实|光说不做|骗我|调了吗|做了么"
)


def guard_enabled() -> bool:
    return os.environ.get("MIMIR_INTENT_ACTION_GUARD", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def session_tools_used(messages: Sequence[Dict[str, Any]]) -> bool:
    return any(m.get("role") == "tool" for m in messages)


def _user_texts(messages: Sequence[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for m in messages:
        if m.get("role") != "user":
            continue
        content = m.get("content", "")
        if isinstance(content, str) and content.strip():
            if content.strip().startswith(_NUDGE_MARKER):
                continue
            out.append(content.strip())
    return out


def task_requires_tool_grounding(user_text: str) -> bool:
    if not user_text:
        return False
    return bool(_TASK_GROUNDING_RE.search(user_text))


def assistant_defers_or_fakes_completion(content: str) -> bool:
    if not content or not content.strip():
        return False
    return bool(_DEFERRAL_RE.search(content))


def combined_user_intent(messages: Sequence[Dict[str, Any]]) -> str:
    texts = _user_texts(messages)
    if not texts:
        return ""
    # Weight recent user messages; meta follow-ups still inherit prior task.
    recent = texts[-3:]
    return "\n".join(recent)


def should_block_text_only_finish(
    messages: Sequence[Dict[str, Any]],
    assistant_content: str,
    *,
    has_tool_schemas: bool,
) -> bool:
    """True when a no-tool assistant turn should not end the loop yet."""
    if not guard_enabled() or not has_tool_schemas:
        return False
    if session_tools_used(messages):
        return False

    intent = combined_user_intent(messages)
    if not intent:
        return False

    needs_grounding = task_requires_tool_grounding(intent)
    meta_pressure = bool(_META_PRESSURE_RE.search(intent.split("\n")[-1]))

    if not needs_grounding and not meta_pressure:
        return False

    # Meta-only thread ("你读了吗") after prior playbook task → still block.
    if meta_pressure and len(_user_texts(messages)) >= 1:
        prior = "\n".join(_user_texts(messages)[:-1])
        if prior and task_requires_tool_grounding(prior):
            needs_grounding = True

    if not needs_grounding:
        return False

    if assistant_defers_or_fakes_completion(assistant_content):
        return True

    # Short status-only replies under action tasks (e.g. "还没。")
    if len((assistant_content or "").strip()) < 120:
        return True

    return False


def build_nudge_message() -> str:
    return (
        f"{_NUDGE_MARKER} Your last reply had no tool calls but the user expects "
        "concrete work. Call read_file, search_files, grep, or patch now — do not "
        "reply with only promises, apologies, or claimed completion. "
        "Mimir Playbook path: docs/MIMIR_EV_L_INDUSTRIAL_LEARNING.md "
        "(there is no docs/PLAYBOOK.md). §2c checkboxes live in that Playbook; "
        "docs/MIMIR_EXEC_BACKLOG.md §2c is a separate tracking table."
    )
