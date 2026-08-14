"""BRAIN-03: contract tests for conversation nudges (memory + skill)."""

import os
from unittest.mock import patch

import pytest

from agent.conversation_nudges import (
    MEMORY_NUDGE_MARKER,
    SKILL_NUDGE_MARKER,
    maybe_memory_nudge_message,
    maybe_skill_nudge_message,
)


@pytest.fixture(autouse=True)
def _isolate_nudge_env():
    """隔离 nudge 环境变量——测试自持数据，不继承 shell/gateway 环境。

    背景：运行环境（gateway .env / shell）可能注入 MIMIR_MEMORY_NUDGE_INTERVAL=0
    或 MIMIR_SKILL_NUDGE_INTERVAL=0（生产禁 nudge 配置），若测试继承该环境，
    maybe_*_nudge_message 读到 interval=0 全部返回 None，导致"应触发"断言失败
    （2026-08-15 Ralph 清债 root-cause：7 failed 中 4 个源于此）。
    本 fixture 在每个测试前清除这 3 个变量，让测试在默认间隔下运行。
    """
    for var in (
        "MIMIR_MEMORY_NUDGE_INTERVAL",
        "MIMIR_SKILL_NUDGE_INTERVAL",
        "MIMIR_SKILL_NUDGE_MIN_TOOLS",
    ):
        os.environ.pop(var, None)
    yield


class TestMemoryNudge:
    """maybe_memory_nudge_message — default interval 10."""

    def test_turn_0_no_nudge(self):
        """Turn 0 should never produce a memory nudge."""
        assert maybe_memory_nudge_message(0) is None

    def test_turn_9_triggers_memory_nudge(self):
        """Turn 9 (0-indexed, 10th turn) should produce MEMORY_NUDGE_MARKER."""
        result = maybe_memory_nudge_message(9)
        assert result is not None
        assert MEMORY_NUDGE_MARKER in result

    def test_turn_19_triggers_memory_nudge(self):
        """Turn 19 (20th turn) should also produce MEMORY_NUDGE_MARKER."""
        result = maybe_memory_nudge_message(19)
        assert result is not None
        assert MEMORY_NUDGE_MARKER in result

    def test_turn_5_no_nudge(self):
        """Turn 5 (not a multiple of 10) should not produce a nudge."""
        assert maybe_memory_nudge_message(5) is None

    def test_interval_zero_disables(self):
        """Interval=0 should suppress all memory nudges."""
        with patch.dict(os.environ, {"MIMIR_MEMORY_NUDGE_INTERVAL": "0"}):
            assert maybe_memory_nudge_message(9) is None
            assert maybe_memory_nudge_message(99) is None


class TestSkillNudge:
    """maybe_skill_nudge_message — default interval 10, min_tools 3."""

    def test_turn_0_no_nudge(self):
        """Turn 0 should never produce a skill nudge."""
        assert maybe_skill_nudge_message(0, 5) is None

    def test_turn_9_too_few_tools(self):
        """Turn 9 with 0 tools should not trigger (below min_tools)."""
        result = maybe_skill_nudge_message(9, 0)
        assert result is None

    def test_turn_9_enough_tools_triggers(self):
        """Turn 9 with 3+ tools should produce SKILL_NUDGE_MARKER."""
        result = maybe_skill_nudge_message(9, 3)
        assert result is not None
        assert SKILL_NUDGE_MARKER in result

    def test_turn_9_just_enough_tools(self):
        """Turn 9 with exactly min_tools=3 should trigger."""
        result = maybe_skill_nudge_message(9, 3)
        assert result is not None

    def test_custom_interval(self):
        """Custom interval via env should shift trigger turn."""
        with patch.dict(os.environ, {"MIMIR_SKILL_NUDGE_INTERVAL": "5", "MIMIR_SKILL_NUDGE_MIN_TOOLS": "1"}):
            # Turn 4 (0-indexed, 5th turn) with 1 tool
            result = maybe_skill_nudge_message(4, 1)
            assert result is not None
            assert SKILL_NUDGE_MARKER in result
            # Turn 3 should not trigger
            assert maybe_skill_nudge_message(3, 1) is None
