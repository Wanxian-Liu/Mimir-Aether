"""auto_retrospective.py — 自动化复盘器。

当 verify-before-report guard 拦截时，自动：
1. 提取根因（assistant 文本中的假声明）
2. 写入复盘日志 (data/retrospectives.jsonl)

env 门控: MIMIR_AUTO_RETROSPECTIVE=1
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

RETRO_FILE = "data/retrospectives.jsonl"

VERIFY_TRIGGERS = [
    "已验证", "已完成", "已修复", "已通过", "全绿",
    "verified", "completed", "fixed", "passed",
    "已修", "已推送",
]


def enabled() -> bool:
    return os.environ.get("MIMIR_AUTO_RETROSPECTIVE", "1") == "1"


def _extract_claim(text: str) -> str:
    """从 assistant 文本中提取声明性结论行"""
    lines = text.split("\n")
    hits = []
    for line in lines:
        low = line.lower()
        if any(t.lower() in low for t in VERIFY_TRIGGERS):
            hits.append(line.strip()[:200])
    if hits:
        return "\n".join(hits[:5])
    return text[:300]


def _last_user_text(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            return msg["content"][:300]
    return ""


def record(messages: list[dict], assistant_text: str):
    """guard 触发时记录一调复盘日志。

    纯加法：写入失败只打 warning，不阻塞任何路径。
    """
    if not enabled():
        return

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "claim": _extract_claim(assistant_text),
        "user": _last_user_text(messages),
        "trigger": "verify-before-report",
    }

    home = os.environ.get("MIMIR_AETHER_HOME") or os.path.expanduser("~/.mimiraether")
    path = os.path.join(home, RETRO_FILE)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info("[auto-retro] recorded: %s", entry["claim"][:80])
    except Exception as e:
        logger.warning("[auto-retro] write failed: %s", e)
