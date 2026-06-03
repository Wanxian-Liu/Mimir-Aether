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


def should_block_finish(messages: list[dict[str, Any]], assistant_text: str) -> bool:
    if not guard_enabled():
        return False
    last_user = _last_user_text(messages)
    if last_user and any(p in last_user for p in STATUS_QUERY_PATTERNS):
        return False
    text = (assistant_text or "").lower()
    return any(trigger.lower() in text for trigger in VERIFY_TRIGGERS)


def build_nudge_message() -> str:
    return (
        "[verify-before-report] 你刚才的回复中含有声明性结论。"
        "请先调用 read_file 或对应工具确认证据真实存在，再输出最终结论。"
        "不要凭记忆报告——工具结果优先。"
    )
