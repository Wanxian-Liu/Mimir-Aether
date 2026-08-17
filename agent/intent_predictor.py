"""IQ-EVO-47: minimal production IntentPredictor (rule-based MVP).

Not a trained classifier — labels user turns for prompt hints and routing guardrails.
Offline batch labeling remains in ``scripts/label_intent_offline.py`` (IQ-EVO-32).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Tuple

# Reuse complexity signals aligned with smart_model_routing (no import cycle).
_COMPLEX_RE = re.compile(
    r"(?i)\b("
    r"debug|implement|refactor|patch|traceback|stacktrace|exception|"
    r"analyze|investigate|architecture|pytest|benchmark|optimize|"
    r"调试|实现|重构|分析|架构|测试|优化"
    r")\b"
)
_CODE_BLOCK_RE = re.compile(r"```|`")
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)

_LOW_CONFIDENCE_THRESHOLD = 0.5

_INTENT_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("debug", re.compile(r"(?i)debug|traceback|stack\s*trace|报错|异常|error\s*code")),
    ("code", re.compile(r"(?i)implement|refactor|patch|fix\s+|修复|实现|改代码|写代码|提交")),
    ("recall", re.compile(r"(?i)上次|之前|记得|session_search|搜.*会话|历史.*对话|还记得")),
    ("ops", re.compile(r"(?i)gateway|health_check|mimir_ops|tier0|restart|/new|日志|agent\.log")),
    ("chat", re.compile(r"(?i)^(hi|hello|你好|谢谢|在吗|早上好)[\s!?.。]*$")),
    # 2026-08-17 根治：research 意图——找论文/找资料/搜索/调研类请求必须触发搜索（刘哥"找数学论文"被误判 general/simple 的修复）
    # 2026-08-18 TD-01：补口语触发词——了解一下/帮我找找/给我找/找找/看看/了解（8/17 追问"什么论文？"仍识别 research）
    ("research", re.compile(r"(?i)论文|research|调研|找.*(论文|资料|信息|项目|仓库|卡)|查.*(论文|资料|信息)|搜.*|热门|炙手可热|推荐|看看.*(什么|论文)|了解.*(什么|方向)|了解一下|找找|帮我找|给我找|帮我看看|有.*(论文|项目|资料)|讲.*(论文|项目)")),
)


@dataclass(frozen=True)
class IntentPrediction:
    intent: str
    complexity: str
    confidence: float
    prefer_session_search: bool
    block_cheap_route: bool


def predictor_enabled() -> bool:
    return os.environ.get("MIMIR_INTENT_PREDICTOR", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _estimate_complexity(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "simple"
    if len(t) > 500 or t.count("\n") > 6:
        return "complex"
    if _CODE_BLOCK_RE.search(t) or _URL_RE.search(t) or _COMPLEX_RE.search(t):
        return "complex"
    if len(t) > 180 or len(t.split()) > 35:
        return "medium"
    if len(t) < 60 and not _COMPLEX_RE.search(t):
        return "simple"
    return "medium"


def _classify_intent(text: str) -> Tuple[str, float]:
    t = (text or "").strip()
    if not t:
        return "general", 0.3
    for name, pattern in _INTENT_PATTERNS:
        if pattern.search(t):
            return name, 0.75
    if _COMPLEX_RE.search(t):
        return "code", 0.55
    return "general", 0.4


# ── P0: 续执行/接力 强制 block_cheap ──
# 当用户说"继续"或类似接力语时，不允许 LLM 跳过工具验证直接回答问题。
_CONTINUE_PATTERNS = re.compile(r"(?i)继续|接着|cont|resume|继续离席|new 了|新对话|再做|再做下去|继续完成")


def predict(user_message: str) -> IntentPrediction:
    intent, confidence = _classify_intent(user_message)
    complexity = _estimate_complexity(user_message)
    prefer_search = intent in ("recall", "research") or (
        intent in ("code", "debug", "ops") and complexity != "simple"
    )
    block_cheap = complexity == "complex" or intent in ("code", "debug", "ops", "research")

    # P0 override: 续执行时强制走工具验证 + 搜历史
    if _CONTINUE_PATTERNS.search(user_message):
        block_cheap = True
        prefer_search = True

    return IntentPrediction(
        intent=intent,
        complexity=complexity,
        confidence=confidence,
        prefer_session_search=prefer_search,
        block_cheap_route=block_cheap,
    )


def build_intent_context_block(prediction: IntentPrediction) -> str:
    lines = [
        "<intent-context>",
        f"intent={prediction.intent} complexity={prediction.complexity} "
        f"confidence={prediction.confidence:.2f}",
    ]
    if prediction.confidence < _LOW_CONFIDENCE_THRESHOLD:
        lines.append(
            "(low-confidence prediction — treat as suggestion, not directive)"
        )
        lines.append("</intent-context>")
        return "\n".join(lines)
    if prediction.prefer_session_search:
        lines.append(
            "Prefer session_search (or read_file) before answering from memory alone."
        )
    if prediction.intent in ("code", "debug", "ops"):
        lines.append("Grounded task: use tools in this turn; do not defer with text-only plans.")
    if prediction.intent == "recall":
        lines.append("User likely refers to prior work — search sessions or MEMORY.md first.")
    if prediction.intent == "research":
        lines.append("Research task: MUST use web_search/read_file this turn; do NOT answer from memory alone.")
    lines.append("</intent-context>")
    return "\n".join(lines)


def predict_and_format(user_message: str) -> tuple[IntentPrediction | None, str]:
    if not predictor_enabled():
        return None, ""
    pred = predict(user_message)
    return pred, build_intent_context_block(pred)
