from __future__ import annotations

import pytest
pytest.importorskip("agent.wm_voe_learning", reason="WM archived 2026-08-03")
pytest.importorskip("agent.world_model_spike", reason="WM archived 2026-08-03")

from dataclasses import fields

from agent.world_model_spike import Prediction, is_wm_predictor_enabled, predict

def test_prediction_dataclass_fields():
    names = {f.name for f in fields(Prediction)}
    assert names == {"next_context_needs", "applicable_skills", "expected_outcome", "tool_confidence"}

def test_predict_rich_snapshot_non_empty_outcome():
    snapshot = {
        "user_message": "还记得上次 gateway 重启的问题吗",
        "intent": "recall",
        "objective": "summarize prior fix",
    }
    pred = predict(snapshot)
    assert pred.expected_outcome
    assert isinstance(pred.next_context_needs, list)
    assert isinstance(pred.applicable_skills, list)
    assert all(isinstance(s, str) for s in pred.applicable_skills)
    assert "session_search" in pred.applicable_skills
    assert "Achieve objective: summarize prior fix" == pred.expected_outcome

def test_predict_is_deterministic():
    snapshot = {
        "user_message": "implement patch in agent_loop.py",
        "intent": "code",
        "objective": "",
    }
    first = predict(snapshot)
    second = predict(snapshot)
    assert first == second

def test_predict_empty_snapshot_conservative_default():
    pred = predict({})
    assert isinstance(pred, Prediction)
    assert pred.expected_outcome
    assert pred.next_context_needs == []
    assert pred.applicable_skills == []

def test_wm_predictor_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MIMIR_WM_PREDICTOR", raising=False)
    assert is_wm_predictor_enabled() is False

def test_wm_predictor_enabled(monkeypatch):
    monkeypatch.setenv("MIMIR_WM_PREDICTOR", "1")
    assert is_wm_predictor_enabled() is True
