"""verify-before-report guard — 汇报前验证守卫。

在 assistant 回复含有声明性结论时，强制触发验证提醒。
env 门控: MIMIR_VERIFY_BEFORE_REPORT=1
"""

import os
import json
from typing import Any

VERIFY_TRIGGERS = [
    "已验证", "已完成", "已修复", "已通过", "全绿",
    "verified", "completed", "fixed", "passed",
    "PASS", "zero errors", "no failures", "all green",
    "已修", "已推送",
    "收官", "已解决", "完工", "收工", "搞定了",
]

STATUS_QUERY_PATTERNS = [
    "状态", "status", "check", "在吗", "在么",
]


def guard_enabled() -> bool:
    return os.environ.get("MIMIR_VERIFY_BEFORE_REPORT", "0") == "1"


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            return msg["content"]
    return ""


def _has_verified_this_turn(messages: list[dict[str, Any]]) -> bool:
    """检查本轮是否有调过验证工具"""
    VERIFICATION_TOOLS = {"read_file", "search_files", "terminal", "git", "memory", "mimir_ops", "get_env", "session_search"}
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                if tc.get("function", {}).get("name", "") in VERIFICATION_TOOLS:
                    return True
        if msg.get("role") == "user":
            break
    return False


def should_block_finish(messages: list[dict[str, Any]], assistant_text: str) -> bool:
    if not guard_enabled():
        return False
    # 自引用豁免：讨论守卫本身时跳过（含中文/英文关键词）
    text_lower = (assistant_text or "").lower()
    if any(kw in text_lower for kw in ["verify-before-report", "守卫", "before-report", "before_report"]):
        return False
    # 如果已调过验证工具 → 放行
    if _has_verified_this_turn(messages):
        return False
    last_user = _last_user_text(messages)
    if last_user and any(p in last_user for p in STATUS_QUERY_PATTERNS):
        return False
    text = (assistant_text or "").lower()
    return any(trigger.lower() in text for trigger in VERIFY_TRIGGERS)


def build_nudge_message() -> str:
    return (
        "[BLOCKED:verify-before-report] 你的回复被阻止——含有未经验证的声明性结论。"
        "你的回复已被从历史记录中移除。请先调用 read_file / json.load / terminal 等工具"
        "确认盘上证据真实存在，再重新输出结论。不要凭记忆报告。"
    )
