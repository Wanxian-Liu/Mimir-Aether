
import pytest
pytest.importorskip("agent.wm_voe_learning", reason="WM archived 2026-08-03")
pytest.importorskip("agent.world_model_spike", reason="WM archived 2026-08-03")

import os
from unittest.mock import patch

from agent.world_model_spike import (
    Prediction,
    predict,
    is_wm_predictor_enabled,
)

class TestVoEWmPrediction:
    """Validate world_model_spike.predict returns correct structure."""

    def test_recall_intent_needs_context(self):
        """User asking '上次' should trigger recall intent with context needs."""
        result = predict({
            "user_message": "上次我们聊到哪里了？",
            "intent": "",
            "objective": "",
        })
        assert isinstance(result, Prediction)
        assert "prior_session_context" in result.next_context_needs
        assert "memory_or_search" in result.next_context_needs

    def test_code_intent_needs_source_files(self):
        """User asking code-related should trigger source context needs."""
        result = predict({
            "user_message": "帮我修复这个bug",
            "intent": "code",
            "objective": "",
        })
        assert isinstance(result, Prediction)
        assert "source_files" in result.next_context_needs
        assert "repo_context" in result.next_context_needs

    def test_general_intent_no_special_needs(self):
        """General chat should only need user_message."""
        result = predict({
            "user_message": "你好",
            "intent": "general",
            "objective": "",
        })
        assert isinstance(result, Prediction)
        assert result.next_context_needs == ["user_message"]

    def test_wm_predictor_default_off(self):
        """MIMIR_WM_PREDICTOR should default to off (0)."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_wm_predictor_enabled() is False

    def test_wm_predictor_env_on(self):
        """MIMIR_WM_PREDICTOR=1 should enable the predictor."""
        with patch.dict(os.environ, {"MIMIR_WM_PREDICTOR": "1"}):
            assert is_wm_predictor_enabled() is True
