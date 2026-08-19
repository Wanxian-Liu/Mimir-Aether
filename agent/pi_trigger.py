"""P1-1 PI 自动触发评估（2026-08-19 执行卡 #5）· v2

Loki 修正：触发条件 = 预估轮次 ≥8（非关键词）——delegate overhead (~10s) 抵 1 轮 API (~20s)。
估算启发：任务文本长度 + 关键词 + 工具需求信号。

v2（2026-08-19 Mimir 第 4 项）：修复 Loki 10 边界用例 60% 漏触发率 → 0%
- 扩展 _LONG_TASK_HINTS：扫一遍/跑一遍/过一遍/遍历/逐条/每条/每张/逐项/整理/调研/commit/sources + 单字 扫/遍
- 短文本数量词加分："77 张"→+3（≥10 大数量→+5）、百分比阈值→+2
- 相对路径识别：wiki/、docs/、concepts/ 等词根（无斜杠也算）+2
- commit 哈希识别（7-40 位 hex）→+2
- 短文本长任务组合：<100 字且 ≥2 个 hint 命中 → +2
- 验证：Loki 10 边界用例 0 漏触发 + 负向 10 例 0 误触发
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

# 长任务信号词（预估轮次≥8 的指示）· v2 扩展
_LONG_TASK_HINTS = (
    "全部", "所有", "逐个", "批量", "清单", "审计", "扫描",
    "each", "all", "every", "batch", "list", "audit",
    # v2 扩展：扫/跑/过/遍/每/条/张/项/整理/调研/commit/sources
    "扫一遍", "跑一遍", "过一遍", "遍历", "逐条", "逐张", "逐项",
    "每条", "每张", "每页", "每份", "每篇", "逐一", "整理", "调研",
    "scan", "iterate", "review", "commit", "sources",
    # 单字强信号（配合子串匹配，短文本长任务核心：扫一遍/跑一遍/过一遍）
    "扫", "遍",
)

# 相对路径词根（v2：无斜杠也算——"扫一遍 wiki 讨论卡" 命中 wiki）
_RELPATH_ROOTS = ("wiki", "docs", "concepts", "entities", "sources", "src", "data", "路径", "path")


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
    """启发式轮次预估 v2：
    - 长度 ≥ 300 字 → +3；≥ 100 字 → +1
    - 每个长任务信号词 → +1
    - 每个调研关键词 → +0.5
    - 短文本数量词（"77 张"）→ +3；大数量（≥10）→ +5；百分比阈值 → +2
    - commit 哈希（7-40 位 hex）→ +2
    - 含路径/文件/相对路径词根（wiki/ docs/ 等）→ +2
    - 列表分隔（顿号+逗号 ≥3）→ +1
    - 短文本（<100 字）且 ≥2 个信号词 → +2（组合奖励）
    """
    score = 1  # 基线 1 轮
    n = len(task_text)
    if n >= 300:
        score += 3
    elif n >= 100:
        score += 1

    low = task_text.lower()
    hints_hit = 0
    for hint in _LONG_TASK_HINTS:
        if hint in low:
            score += 1
            hints_hit += 1

    for hint in _RESEARCH_HINTS:
        if hint in low:
            score += 0.5

    # v2: 短文本数量词加分（"77 张" → +3；≥10 → +5）
    m = re.search(r"(\d+)\s*(张|个|条|份|篇|页|卡|文件|sources|pages|files|docs)", low)
    if m:
        qty = int(m.group(1))
        score += 5 if qty >= 10 else 3
    # v2: 百分比阈值（≥80% 之类验收标准）→ +2
    if re.search(r"\d+\s*%", low):
        score += 2

    # v2: commit 哈希识别（review commit 9d61bd9 场景）→ +2
    if re.search(r"\b[0-9a-f]{7,40}\b", low):
        score += 2

    # 路径/文件信号（绝对路径 + v2 相对路径词根 + 文件后缀）
    path_hit = False
    if re.search(r"(~/[\w/]+|/[\w/]+\.\w{2,4})", task_text):
        path_hit = True
    for root in _RELPATH_ROOTS:
        if root in low:
            path_hit = True
            break
    if re.search(r"\b\w+\.\w{2,4}\b", task_text):
        path_hit = True
    if path_hit:
        score += 2

    # 列表分隔符（顿号/逗号合计 ≥3 → +1）
    if task_text.count("、") + task_text.count(",") >= 3:
        score += 1

    # v2: 短文本长任务组合奖励（<100 字 且 ≥2 个 hint 命中 → +2）
    if n < 100 and hints_hit >= 2:
        score += 2

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
