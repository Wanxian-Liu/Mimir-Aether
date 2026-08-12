"""A3: max_turns 分档解析（短20 / 中40 / 长90）。

四方共识 + 刘哥批准（2026-08-12）：
  - 任务前置声明机制：任务开始时在消息中声明档位（`[tier:短]` / `[档位:长]` / `[tier:20]`）
  - 环境变量 MIMIR_MAX_TURNS_TIER（short|medium|long 或数字）作为全局兜底
  - 优先级：任务前置声明 > 环境变量 > 调用方传入 default（默认 90 = 长档）

使用：
    from agent.max_turns_tier import resolve_max_turns_tier
    turns, tier, cleaned = resolve_max_turns_tier(user_message, default=90)
    # turns: 实际 max_turns；tier: 'short'|'medium'|'long'|'default'；cleaned: 剥离声明后的消息
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# 分档表（四方共识：短20 / 中40 / 长90）
TIERS: dict = {
    "short": 20,
    "medium": 40,
    "long": 90,
}

# 中文别名 → 档位
_ALIAS_CN: dict = {
    "短": "short",
    "中": "medium",
    "长": "long",
    "short": "short",
    "medium": "medium",
    "long": "long",
}

# 匹配 [tier:xxx] 或 [档位:xxx]（大小写不敏感，冒号支持中文全角）
_DECL_RE = re.compile(
    r"\[\s*(?:tier|档位|max_turns)\s*[:：]\s*([^\]\s]+)\s*\]",
    re.IGNORECASE,
)


def _parse_value(raw: str) -> Optional[int]:
    """把声明/环境变量值解析为 max_turns 整数。非法返回 None。"""
    val = raw.strip().lower()
    if val in _ALIAS_CN:
        return TIERS[_ALIAS_CN[val]]
    if val.isdigit():
        n = int(val)
        if n > 0:
            return n
    return None


def resolve_max_turns_tier(
    user_message: str,
    default: int = 90,
) -> Tuple[int, str, str]:
    """解析任务前置声明与环境变量，返回 (max_turns, tier_name, cleaned_message)。

    tier_name ∈ {'short', 'medium', 'long', 'default'}：
      - 声明/环境变量命中分档表 → 对应档位名
      - 声明/环境变量为自定义数字 → 'custom'
      - 未命中 → 'default'

    cleaned_message：剥离声明片段后的消息正文（声明是元数据，不进模型上下文）。
    """
    msg = user_message or ""
    cleaned = msg

    # 1) 任务前置声明（最高优先级）
    m = _DECL_RE.search(msg)
    if m:
        turns = _parse_value(m.group(1))
        if turns is not None:
            # 剥离声明片段（仅剥离匹配到的这一段）
            cleaned = _DECL_RE.sub("", msg, count=1).strip()
            tier = "custom" if turns not in TIERS.values() else (
                next((k for k, v in TIERS.items() if v == turns), "custom")
            )
            logger.info(
                "[A3] max_turns tier declared in task: %s → %d",
                m.group(1), turns,
            )
            return turns, tier, cleaned

    # 2) 环境变量 MIMIR_MAX_TURNS_TIER（全局兜底）
    env_raw = os.getenv("MIMIR_MAX_TURNS_TIER")
    if env_raw:
        turns = _parse_value(env_raw)
        if turns is not None:
            tier = "custom" if turns not in TIERS.values() else (
                next((k for k, v in TIERS.items() if v == turns), "custom")
            )
            logger.info(
                "[A3] max_turns tier from env MIMIR_MAX_TURNS_TIER=%s → %d",
                env_raw, turns,
            )
            return turns, tier, cleaned

    # 3) 默认（调用方传入，agent_loop/core_loop 默认 90 = long）
    return default, "default", cleaned
