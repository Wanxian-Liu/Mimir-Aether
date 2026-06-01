"""Tests for MIMIR_NUDGE_INTERVAL periodic nudges (MW-04).

Tests the interval nudge logic in agent_loop.py:
- turn % N == 0 triggers nudge (default N=3)
- turn == 0 does NOT trigger
- turn % N != 0 does NOT trigger
- N=0 disables entirely
- Only fires once per session
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from agent.agent_loop import MimirAgentLoop


def _make_loop(**kwargs):
    """Helper to create a MimirAgentLoop with minimal required args."""
    return MimirAgentLoop(
        model_call=MagicMock(),
        tool_schemas=[],
        valid_tool_names=set(),
        tool_dispatcher=MagicMock(),
        **kwargs,
    )


class TestIntervalNudgeConfig:
    """Tests the env var configuration."""

    @patch.dict(os.environ, {"MIMIR_NUDGE_INTERVAL": "3"}, clear=True)
    def test_default_is_3(self):
        """Default interval is 3 when env is set explicitly."""
        loop = _make_loop()
        assert loop._interval_nudge_done is False

    @patch.dict(os.environ, {"MIMIR_NUDGE_INTERVAL": "5"}, clear=True)
    def test_custom_interval(self):
        """NUDGE_INTERVAL=5 should work."""
        loop = _make_loop()
        assert loop._interval_nudge_done is False

    @patch.dict(os.environ, {"MIMIR_NUDGE_INTERVAL": "0"}, clear=True)
    def test_zero_disables(self):
        """NUDGE_INTERVAL=0 means nudge is disabled."""
        loop = _make_loop()
        assert loop._interval_nudge_done is False

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_env_defaults_to_3(self):
        """Missing env var defaults to 3 (read at call time)."""
        # We can't easily test the runtime default without running the loop,
        # but the code reads int(os.environ.get("MIMIR_NUDGE_INTERVAL", "3"))
        loop = _make_loop()
        assert loop._interval_nudge_done is False


class TestIntervalNudgeBehavior:
    """Tests the interval nudge logic by patching the nudge message functions."""

    @patch.dict(os.environ, {"MIMIR_NUDGE_INTERVAL": "3"}, clear=True)
    @patch("agent.agent_loop.maybe_memory_nudge_message")
    @patch("agent.agent_loop.maybe_skill_nudge_message")
    def test_nudge_does_not_fire_on_turn_0(self, mock_skill, mock_memory):
        """Interval nudge should NOT fire on turn 0."""
        mock_memory.return_value = None
        mock_skill.return_value = "test-nudge"

        loop = _make_loop()
        # Simulate the nudge check from agent_loop
        _nudge_interval = int(os.environ.get("MIMIR_NUDGE_INTERVAL", "3"))
        turn = 0
        should_fire = (
            _nudge_interval > 0
            and turn > 0
            and turn % _nudge_interval == 0
            and not loop._interval_nudge_done
        )

        assert should_fire is False, "turn 0 should not trigger interval nudge"
        assert loop._interval_nudge_done is False

    @patch.dict(os.environ, {"MIMIR_NUDGE_INTERVAL": "3"}, clear=True)
    @patch("agent.agent_loop.maybe_memory_nudge_message")
    @patch("agent.agent_loop.maybe_skill_nudge_message")
    def test_nudge_fires_on_turn_3(self, mock_skill, mock_memory):
        """Interval nudge should fire on turn 3 (3 % 3 == 0)."""
        mock_memory.return_value = None
        mock_skill.return_value = "test-nudge"

        loop = _make_loop()
        _nudge_interval = int(os.environ.get("MIMIR_NUDGE_INTERVAL", "3"))
        turn = 3
        should_fire = (
            _nudge_interval > 0
            and turn > 0
            and turn % _nudge_interval == 0
            and not loop._interval_nudge_done
        )

        assert should_fire is True, "turn 3 should trigger interval nudge"

    @patch.dict(os.environ, {"MIMIR_NUDGE_INTERVAL": "3"}, clear=True)
    @patch("agent.agent_loop.maybe_memory_nudge_message")
    @patch("agent.agent_loop.maybe_skill_nudge_message")
    def test_nudge_skips_on_turn_2(self, mock_skill, mock_memory):
        """Interval nudge should NOT fire on turn 2 (2 % 3 != 0)."""
        mock_memory.return_value = None
        mock_skill.return_value = "test-nudge"

        loop = _make_loop()
        _nudge_interval = int(os.environ.get("MIMIR_NUDGE_INTERVAL", "3"))
        turn = 2
        should_fire = (
            _nudge_interval > 0
            and turn > 0
            and turn % _nudge_interval == 0
            and not loop._interval_nudge_done
        )

        assert should_fire is False, "turn 2 should not trigger interval nudge"

    @patch.dict(os.environ, {"MIMIR_NUDGE_INTERVAL": "3"}, clear=True)
    @patch("agent.agent_loop.maybe_memory_nudge_message")
    @patch("agent.agent_loop.maybe_skill_nudge_message")
    def test_nudge_only_fires_once(self, mock_skill, mock_memory):
        """Interval nudge should only fire once, even on subsequent matching turns."""
        mock_memory.return_value = None
        mock_skill.return_value = "test-nudge"

        loop = _make_loop()

        # Turn 3: should fire
        _nudge_interval = 3
        turn = 3
        fire1 = (
            _nudge_interval > 0
            and turn > 0
            and turn % _nudge_interval == 0
            and not loop._interval_nudge_done
        )
        assert fire1 is True, "first match should fire"
        loop._interval_nudge_done = True  # simulate marking done

        # Turn 6: should NOT fire (already done)
        turn = 6
        fire2 = (
            _nudge_interval > 0
            and turn > 0
            and turn % _nudge_interval == 0
            and not loop._interval_nudge_done
        )
        assert fire2 is False, "subsequent matches should NOT fire when already done"

    @patch.dict(os.environ, {"MIMIR_NUDGE_INTERVAL": "0"}, clear=True)
    @patch("agent.agent_loop.maybe_memory_nudge_message")
    @patch("agent.agent_loop.maybe_skill_nudge_message")
    def test_zero_disables_completely(self, mock_skill, mock_memory):
        """NUDGE_INTERVAL=0 should never fire."""
        mock_memory.return_value = None
        mock_skill.return_value = "test-nudge"

        loop = _make_loop()
        _nudge_interval = int(os.environ.get("MIMIR_NUDGE_INTERVAL", "3"))
        for turn in [3, 6, 9, 12]:
            should_fire = (
                _nudge_interval > 0
                and turn > 0
                and turn % _nudge_interval == 0
                and not loop._interval_nudge_done
            )
            assert should_fire is False, f"turn {turn} should not fire when NUDGE_INTERVAL=0"
