"""IQ-EVO-47 IntentPredictor MVP."""
from __future__ import annotations

import sys
from pathlib import Path

# Add repo root so we can import intent_predictor
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from agent.intent_predictor import (
    IntentPrediction,
    build_intent_context_block,
    predict,
    predict_and_format,
    predictor_enabled,
)


def test_predict_debug_complex():
    pred = predict("Please debug this traceback in agent_loop.py")
    assert pred.intent == "debug"
    assert pred.complexity in ("medium", "complex")
    assert pred.block_cheap_route is True


def test_predict_recall_prefers_search():
    pred = predict("还记得上次飞书会话里说的 gateway 问题吗")
    assert pred.intent == "recall"
    assert pred.prefer_session_search is True


def test_predict_chat_simple():
    pred = predict("你好")
    assert pred.intent == "chat"
    assert pred.complexity == "simple"
    assert pred.block_cheap_route is False


def test_build_intent_context_block():
    pred = predict("fix the patch in core_loop")
    block = build_intent_context_block(pred)
    assert "<intent-context>" in block
    assert "intent=" in block


def test_predictor_disabled(monkeypatch):
    monkeypatch.setenv("MIMIR_INTENT_PREDICTOR", "0")
    assert predictor_enabled() is False
    pred, block = predict_and_format("implement feature X")
    assert pred is None
    assert block == ""


def test_predictor_enabled_default(monkeypatch):
    monkeypatch.delenv("MIMIR_INTENT_PREDICTOR", raising=False)
    assert predictor_enabled() is True


def test_high_confidence_full_context():
    pred = IntentPrediction(
        intent="code",
        complexity="complex",
        confidence=0.75,
        prefer_session_search=True,
        block_cheap_route=True,
    )
    block = build_intent_context_block(pred)
    assert "Grounded task:" in block
    assert "low-confidence" not in block


def test_low_confidence_lite_context():
    pred = IntentPrediction(
        intent="general",
        complexity="simple",
        confidence=0.4,
        prefer_session_search=False,
        block_cheap_route=False,
    )
    block = build_intent_context_block(pred)
    assert "low-confidence prediction" in block
    assert "Grounded task:" not in block


def test_predict_and_format_low_confidence_general():
    pred, block = predict_and_format("说说今天")
    assert pred is not None
    assert pred.confidence < 0.5
    assert "low-confidence" in block


# ═══════════════════════════════════════════════════════════════════════════
# TD-01（2026-08-18）：research 口语 pattern 扩展
# 8/17 论文任务失败根因之一：口语化请求（"了解一下"/"帮我找找"）不命中 research
# ═══════════════════════════════════════════════════════════════════════════

def _intent(text: str) -> str:
    return predict(text).intent


def test_research_casual_liaojie() -> None:
    """「了解一下」→ research（口语触发词）。"""
    assert _intent("了解一下") == "research"


def test_research_casual_zhaozhao() -> None:
    """「帮我找找」→ research（找找触发词）。"""
    assert _intent("帮我找找") == "research"


def test_research_casual_geiwozhao() -> None:
    """「给我找一篇数学论文」→ research。"""
    assert _intent("给我找一篇数学论文") == "research"


def test_research_casual_kankan() -> None:
    """「帮我看看有什么好东西」→ research。"""
    assert _intent("帮我看看有什么好东西") == "research"


def test_research_followup_question() -> None:
    """追问「什么论文？」→ research（8/17 场景：用户追问仍要识别为 research）。"""
    assert _intent("什么论文？") == "research"
