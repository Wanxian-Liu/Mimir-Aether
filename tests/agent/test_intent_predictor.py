"""IQ-EVO-47 IntentPredictor MVP."""

from __future__ import annotations

import os

from agent.intent_predictor import (
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
