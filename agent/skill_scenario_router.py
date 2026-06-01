"""Scenario → skill_view recommendations (meta-cognition nudge · BRAIN-11)."""

from __future__ import annotations

import os
import re
from typing import Any, List, Optional, Sequence, Tuple

from agent.search_first_guard import last_user_text

MARKER = "[MIMIR_SKILL_ROUTE_NUDGE]"
SKILL_VIEW_TOOL = "skill_view"

# (pattern, skills, label) — first match wins per label; union all matching labels
_SCENARIOS: List[Tuple[re.Pattern[str], List[str], str]] = [
    (
        re.compile(
            r"进步|变强|能力|自我|状态|净化|怎么样了|变好|meta|自评|audit",
            re.IGNORECASE,
        ),
        ["mimiraether-self-audit"],
        "self_status",
    ),
    (
        re.compile(
            r"debug|bug|失败|错误|根因|tier0|修复|fix|broken|exception|traceback",
            re.IGNORECASE,
        ),
        ["mimiraether-root-cause-debugging"],
        "debug",
    ),
    (
        re.compile(
            r"设计|brainstorm|方案|架构|立项|spike|该怎么建|怎么实现",
            re.IGNORECASE,
        ),
        ["mimiraether-brainstorming"],
        "design",
    ),
    (
        re.compile(
            r"报告|周报|总结|HTML|复杂表|成绩单|dashboard",
            re.IGNORECASE,
        ),
        ["mimiraether-html-output"],
        "report",
    ),
    (
        re.compile(
            r"健康检查|health\s*check|自检|体检|gateway\s*ok",
            re.IGNORECASE,
        ),
        ["mimiraether-self_health_check"],
        "health",
    ),
    (
        re.compile(
            r"BRAIN-\d+|§10|任务链|下一粒|继续下一|自治链|HANDOFF",
            re.IGNORECASE,
        ),
        ["mimiraether-ship"],
        "task_chain",
    ),
]


def skill_route_nudge_enabled() -> bool:
    return os.environ.get("MIMIR_SKILL_ROUTE_NUDGE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def recommend_skills(user_text: str) -> List[str]:
    """Return deduplicated skill names suggested for this user message."""
    if not (user_text or "").strip():
        return []
    seen: set[str] = set()
    out: List[str] = []
    matched_labels: set[str] = set()
    for pattern, skills, label in _SCENARIOS:
        if label in matched_labels:
            continue
        if not pattern.search(user_text):
            continue
        matched_labels.add(label)
        for name in skills:
            if name not in seen:
                seen.add(name)
                out.append(name)
    return out


def build_skill_route_nudge(skill_names: Sequence[str]) -> str:
    joined = ", ".join(skill_names)
    extra = ""
    if any("ship" in s for s in skill_names):
        extra = (
            " After tier0 green: commit and push; then mark TASK_QUEUE §10 [x] and "
            "start the next [ ] grain without asking 刘哥 to continue."
        )
    return (
        f"{MARKER} Meta-cognition step (mandatory before other work): call skill_view "
        f"for each skill: {joined}. Follow each skill's workflow; do not use intuition "
        f"alone when a skill exists.{extra}"
    )


def _normalize_messages(messages: Sequence[Any]) -> List[dict]:
    out: List[dict] = []
    for m in messages:
        if isinstance(m, dict):
            out.append(m)
        else:
            out.append(
                {
                    "role": getattr(m, "role", None),
                    "content": getattr(m, "content", None),
                    "tool_calls": getattr(m, "tool_calls", None),
                    "name": getattr(m, "name", None),
                }
            )
    return out


def _skill_viewed_in_slice(messages: Sequence[Any], skill_name: str) -> bool:
    needle = skill_name.strip().lower()
    for m in _normalize_messages(messages):
        role = m.get("role")
        if role == "tool" and m.get("name") == SKILL_VIEW_TOOL:
            body = str(m.get("content") or "").lower()
            if needle in body:
                return True
        if role == "assistant":
            for call in m.get("tool_calls") or []:
                fn = call.get("function") if isinstance(call, dict) else getattr(call, "function", None)
                if not fn:
                    continue
                fname = fn.get("name") if isinstance(fn, dict) else getattr(fn, "name", "")
                if fname != SKILL_VIEW_TOOL:
                    continue
                args = fn.get("arguments") if isinstance(fn, dict) else getattr(fn, "arguments", "")
                if needle in str(args).lower():
                    return True
    return False


def skill_route_satisfied_since_last_user(
    messages: Sequence[Any], required_skills: Sequence[str]
) -> bool:
    if not required_skills:
        return True
    norm = _normalize_messages(messages)
    last_user_idx = -1
    for i, m in enumerate(norm):
        if m.get("role") != "user":
            continue
        content = str(m.get("content") or "")
        if content.strip().startswith(MARKER):
            continue
        last_user_idx = i
    if last_user_idx < 0:
        return False
    slice_msgs = norm[last_user_idx:]
    return all(_skill_viewed_in_slice(slice_msgs, s) for s in required_skills)


def should_inject_skill_route_nudge(
    messages: Sequence[Any],
) -> Tuple[bool, List[str]]:
    if not skill_route_nudge_enabled():
        return False, []
    user_text = last_user_text(messages)
    skills = recommend_skills(user_text)
    if not skills:
        return False, []
    if skill_route_satisfied_since_last_user(messages, skills):
        return False, []
    return True, skills


__all__ = [
    "MARKER",
    "SKILL_VIEW_TOOL",
    "skill_route_nudge_enabled",
    "recommend_skills",
    "build_skill_route_nudge",
    "skill_route_satisfied_since_last_user",
    "should_inject_skill_route_nudge",
]
