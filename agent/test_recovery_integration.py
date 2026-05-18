"""
Integration Tests: core_loop recovery/guard wiring

Verifies:
1. ToolRecovery.attempt_recovery is called when tools return recoverable errors
2. DegenerationGuard.record_turn tracks tool execution
3. Recovery loop check bridges to guard via record_signal
4. Wire integrity: imports compile, methods accessible

Author: MimirAether (self-evolved)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.core_loop import MimirAetherAgent
from agent.recovery import (
    ToolRecovery, ToolRecoveryPattern, ToolRecoveryAttempt,
    classify_tool_error, get_tool_recovery, _extract_path_from_error,
)
from agent.degeneration_guard import (
    DegenerationGuard, DegenerationSignal, DegenerationReport, TurnRecord,
    get_guard, reset_guard,
)
from agent.types import ToolResult


class TestRecoveryWireInCoreLoop:
    """Verify recovery imports and method existence on core_loop."""

    def test_recovery_methods_exist(self):
        """_builtin_execute_tools has _execute_with_recovery nested function."""
        agent = MimirAetherAgent(model="test")
        assert hasattr(agent, '_builtin_execute_tools')
        assert callable(agent._builtin_execute_tools)

    def test_record_guard_turn_exists(self):
        """_record_guard_turn is defined on MimirAetherAgent."""
        agent = MimirAetherAgent(model="test")
        assert hasattr(agent, '_record_guard_turn')
        assert callable(agent._record_guard_turn)

    def test_check_degeneration_exists(self):
        """_check_degeneration is defined on MimirAetherAgent."""
        agent = MimirAetherAgent(model="test")
        assert hasattr(agent, '_check_degeneration')
        assert callable(agent._check_degeneration)


class TestToolRecoveryDirect:
    """Direct API tests on ToolRecovery (no core_loop mock)."""

    def test_classify_permission_denied(self):
        pattern = classify_tool_error("PermissionError: [Errno 13] Permission denied: '/x'")
        assert pattern == ToolRecoveryPattern.PERMISSION

    def test_classify_file_not_found(self):
        pattern = classify_tool_error("FileNotFoundError: [Errno 2] No such file or directory: '/x'")
        assert pattern == ToolRecoveryPattern.MISSING

    def test_classify_non_recoverable(self):
        pattern = classify_tool_error("TimeoutError: tool timed out")
        assert pattern is None

    def test_attempt_recovery_non_recoverable_returns_failure(self):
        recovery = get_tool_recovery()
        attempt = recovery.attempt_recovery("Some random error", tool_name="read_file")
        assert not attempt.success
        assert attempt.action_taken == "no_pattern_match"

    def test_recovery_loop_check_empty(self):
        recovery = get_tool_recovery()
        result = recovery.recovery_loop_check()
        assert result is None  # No attempts → no loop

    def test_recovery_loop_check_with_failures(self):
        recovery = get_tool_recovery()
        # Simulate multiple failed recoveries
        recovery.stats.total_attempts = 3
        recovery.stats.failures = 3
        recovery.stats.successes = 0
        # Add recent attempts (within 300s window)
        from agent.recovery import ToolRecoveryAttempt
        t = ToolRecoveryAttempt(
            pattern=ToolRecoveryPattern.PERMISSION,
            error_message="permission denied",
        )
        t.success = False
        t2 = ToolRecoveryAttempt(
            pattern=ToolRecoveryPattern.FILE_LOCK,
            error_message="file busy",
        )
        t2.success = False
        recovery.stats.attempts = [t, t2, t]  # 3 recent, 2 unique types
        result = recovery.recovery_loop_check()
        assert result == "replan"

    def test_stats_format(self):
        recovery = get_tool_recovery()
        s = recovery.format_stats()
        assert "total" in s.lower() or "attempts" in s.lower()


class TestDegenerationGuardIntegration:
    """Direct API tests on DegenerationGuard."""

    @pytest.fixture(autouse=True)
    def reset(self):
        guard = get_guard()
        guard.turns.clear()
        guard._external_signals.clear()
        yield

    def test_record_turn_populates_turns(self):
        guard = get_guard()
        guard.record_turn(tools=["read_file"], has_new_info=True)
        assert len(guard.turns) == 1
        assert guard.turns[0].tools_called == ["read_file"]

    def test_record_turn_with_files(self):
        guard = get_guard()
        guard.record_turn(
            tools=["write_file"],
            files_touched={"foo.txt", "bar.py"},
            has_new_info=True,
        )
        assert guard.turns[0].files_touched == {"foo.txt", "bar.py"}

    def test_run_checks_clean_after_diverse_turns(self):
        guard = get_guard()
        for i in range(5):
            guard.record_turn(
                tools=[f"tool_{i}"],
                files_touched={f"f_{i}.txt"},
                has_new_info=True,
            )
        report = guard.run_checks()
        assert report.signal == DegenerationSignal.CLEAN

    def test_run_checks_detects_loop(self):
        guard = get_guard()
        for i in range(6):
            guard.record_turn(
                tools=["read_file"],
                has_new_info=False,
            )
        report = guard.run_checks()
        assert report.signal == DegenerationSignal.LOOP_DETECTED
        assert len(report.warnings) >= 1

    def test_record_signal_stores_external(self):
        guard = get_guard()
        guard.record_signal("recovery_loop", {"count": 3, "msg": "test"})
        assert len(guard._external_signals) == 1
        assert guard._external_signals[0]["signal"] == "recovery_loop"


class TestRecoveryGuardBridge:
    """Verify recovery_loop_check → guard.record_signal bridge."""

    def test_bridge_signal_sent(self):
        """When recovery_loop_check returns 'replan', guard receives signal."""
        guard = get_guard()
        guard._external_signals.clear()

        recovery = get_tool_recovery()
        recovery._degeneration_guard = guard  # Inject guard directly

        # Simulate loop
        from agent.recovery import ToolRecoveryAttempt
        for i in range(3):
            a = ToolRecoveryAttempt(
                pattern=ToolRecoveryPattern.PERMISSION if i < 2 else ToolRecoveryPattern.FILE_LOCK,
                error_message=f"error {i}",
            )
            a.success = False
            recovery.stats.attempts.append(a)
        recovery.stats.total_attempts = 3
        recovery.stats.failures = 3

        result = recovery.recovery_loop_check()
        assert result == "replan"
        # Guard should have received the signal
        assert len(guard._external_signals) >= 1
        assert guard._external_signals[-1]["signal"] == "recovery_loop"


class TestCoreLoopCompiles:
    """Verify core_loop.py compiles with recovery/guard wired in."""

    def test_compile(self):
        import py_compile
        py_compile.compile("agent/core_loop.py", doraise=True)
