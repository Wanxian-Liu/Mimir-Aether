"""IQ-33: contract tests for preemptive search vs intent/WM nudge coexistence."""

from __future__ import annotations

import os

from agent.intent_predictor import IntentPrediction, build_intent_context_block, predict
from agent.search_first_guard import (
    preemptive_search_in_slice,
    session_search_satisfied_since_last_user,
)
from agent.world_model_spike import is_wm_predictor_enabled, predict as wm_predict


def _wm_prediction_block(user_message: str) -> str:
    pred = wm_predict(
        {"user_message": user_message, "intent": "", "objective": ""},
    )
    if not pred.next_context_needs:
        return ""
    return (
        "<wm-prediction>\n"
        f"  expected_outcome: {pred.expected_outcome}\n"
        f"  next_context_needs: {', '.join(pred.next_context_needs)}\n"
        f"  applicable_skills: {', '.join(pred.applicable_skills)}\n"
        "</wm-prediction>"
    )


def test_preemptive_satisfied_guard_allows_tools():
    msgs = [
        {"role": "user", "content": "还记得上次的任务么"},
        {"role": "user", "content": "[preemptive-search] Queried sessions.\nmatches: 1"},
    ]
    assert preemptive_search_in_slice(msgs)
    assert session_search_satisfied_since_last_user(msgs)


def test_low_confidence_recall_skips_strong_recall_directive():
    pred = IntentPrediction(
        intent="recall",
        complexity="simple",
        confidence=0.4,
        prefer_session_search=True,
        block_cheap_route=False,
    )
    block = build_intent_context_block(pred)
    assert "low-confidence prediction" in block
    assert "search sessions or MEMORY.md first" not in block


def test_wm_and_intent_blocks_use_distinct_markers():
    user = "还记得上次 gateway 的问题吗"
    wm_block = _wm_prediction_block(user)
    intent_block = build_intent_context_block(predict(user))
    assert wm_block
    assert "<wm-prediction>" in wm_block
    assert "<intent-context>" in intent_block
    assert "<wm-prediction>" not in intent_block
    assert "</wm-prediction>" not in intent_block


def test_wm_predictor_off_by_default(monkeypatch):
    monkeypatch.delenv("MIMIR_WM_PREDICTOR", raising=False)
    assert is_wm_predictor_enabled() is False
