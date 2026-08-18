"""P1-1 PI 自动触发评估（2026-08-19 执行卡 #5）

Loki 修正：触发条件 = 预估轮次 ≥8（非关键词）——delegate overhead (~10s) 抵 1 轮 API (~20s)。
估算启发：任务文本长度 + 关键词 + 工具需求信号。
"""
from __future__ import annotations

import os
import re
from typing import List, Dict, Optional

PI_NUDGE_MARKER = "[MIMIR_PI_NUDGE]"

# 任务特征关键词（配合长度估算——不单独作为触发条件）
_RESEARCH_HINTS = (
    "调研", "审计", "交叉", "验证", "多源", "批量", "汇总", "扫描",
    "research", "audit", "review", "verify", "survey",
    "所有", "全部", "清单", "逐个",
)

# 长任务信号词（预估轮次≥8 的指示）
_LONG_TASK_HINTS = (
    "全部", "所有", "逐个", "批量", "清单", "审计", "扫描",
    "each", "all", "every", "batch", "list", "audit",
)


def _extract_user_task(messages: List[Dict]) -> str:
    """取最后一条真实用户消息文本。"""
    for msg in reversed(messages):
        if not msg:
            continue
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user" and isinstance(content, str):
            # 跳过系统注入类（含 marker 的）
            if "[MIMIR_" in content or "[CONTEXT" in content:
                continue
            return content[:2000]
    return ""


def _estimate_turns(task_text: str) -> int:
    """启发式轮次预估：
    - 长度 ≥ 300 字 → +3
    - 长度 ≥ 100 字 → +1
    - 每个长任务信号词 → +1
    - 每个调研关键词 → +0.5
    - 含路径/文件列表 → +2
    """
    score = 1  # 基线 1 轮
    n = len(task_text)
    if n >= 300:
        score += 3
    elif n >= 100:
        score += 1

    low = task_text.lower()
    for hint in _LONG_TASK_HINTS:
        if hint in low:
            score += 1

    for hint in _RESEARCH_HINTS:
        if hint in low:
            score += 0.5

    # 路径/文件信号（读多文件的迹象）
    if re.search(r"(~/[\w/]+|/[\w/]+\.\w{2,4})", task_text):
        score += 2
    if task_text.count("、") >= 3 or task_text.count(",") >= 3:
        score += 1

    return int(round(score))


def maybe_pi_delegate_nudge(messages: List[Dict]) -> Optional[str]:
    """任务启动评估：预估轮次 ≥8 → 注入 delegate 提示（MIMIR_PI_MIN_TURNS 可调）。"""
    min_turns = int(os.environ.get("MIMIR_PI_MIN_TURNS", "8"))
    task_text = _extract_user_task(messages)
    if not task_text:
        return None
    est = _estimate_turns(task_text)
    if est < min_turns:
        return None
    return (
        f"{PI_NUDGE_MARKER} 当前任务预估需 {est} 轮（≥{min_turns}）。"
        "若该任务可拆分为 ≥3 个独立子任务（多源调研/批量验证/多文件扫描），"
        "请考虑使用 delegate_task 并行派发（每子任务独立上下文+工具，结果精简回传）——"
        "并行执行省 2-4 倍总耗时。若任务强依赖链不可拆，忽略本提示继续串行。"
    )


__all__ = ["PI_NUDGE_MARKER", "maybe_pi_delegate_nudge", "_estimate_turns", "_extract_user_task"]
