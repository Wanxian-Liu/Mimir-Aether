"""
Tests for agent.degeneration_guard — degeneration detection engine.

Covers:
  - loop_detection
  - information_density
  - context_quality_drop
  - surprise_gate
  - recovery_loop signal
  - DegenerationGuard.run_checks()
  - DegenerationReport properties
"""

import time

import pytest

from agent.degeneration_guard import (
    DegenerationGuard,
    DegenerationSignal,
    DegenerationReport,
    get_guard,
    reset_guard,
)


class TestDegenerationReport:
    """DegenerationReport properties."""

    def test_clean_report(self):
        r = DegenerationReport()
        assert r.is_clean
        assert not r.needs_replan
        assert not r.needs_warning

    def test_surprise_needs_replan(self):
        r = DegenerationReport(signal=DegenerationSignal.SURPRISE_DETECTED)
        assert not r.is_clean
        assert r.needs_replan
        assert not r.needs_warning

    def test_recovery_loop_needs_replan(self):
        r = DegenerationReport(signal=DegenerationSignal.RECOVERY_LOOP)
        assert r.needs_replan

    def test_loop_detected_needs_warning(self):
        r = DegenerationReport(signal=DegenerationSignal.LOOP_DETECTED)
        assert r.needs_warning
        assert not r.needs_replan


class TestDegenerationGuardBasics:
    """Basic initialization and recording."""

    def test_guard_init(self):
        g = DegenerationGuard()
        assert g._turn_counter == 0
        assert len(g.turns) == 0

    def test_record_turn(self):
        g = DegenerationGuard()
        g.record_turn(tools=["read_file", "search_files"], has_new_info=True)
        assert g._turn_counter == 1
        assert len(g.turns) == 1
        assert g.turns[0].tools_called == ["read_file", "search_files"]

    def test_record_signal(self):
        g = DegenerationGuard()
        g.record_signal("recovery_loop", {"count": 3})
        assert len(g._external_signals) == 1
        assert g._external_signals[0]["signal"] == "recovery_loop"

    def test_record_compression(self):
        g = DegenerationGuard()
        g.record_compression(pre_message_count=100, post_message_count=30, key_info_retained=0.6)
        assert g._last_compression_context["retention_rate"] == 0.6

    def test_reset(self):
        g = DegenerationGuard()
        g.record_turn(tools=["read_file"])
        g.record_signal("test", {})
        g.reset()
        assert g._turn_counter == 0
        assert len(g.turns) == 0
        assert len(g._external_signals) == 0

    def test_get_summary(self):
        g = DegenerationGuard()
        g.record_turn(tools=["read_file"])
        summary = g.get_summary()
        assert "1 turns" in summary


class TestLoopDetection:
    """Loop: same tool ≥3x in window with no file progress."""

    def test_clean_small_sample(self):
        g = DegenerationGuard()
        g.record_turn(tools=["read_file"], has_new_info=True)
        report = g.run_checks()
        assert report.is_clean

    def test_diverse_tools_no_loop(self):
        g = DegenerationGuard()
        for i in range(5):
            tools = ["read_file", "search_files", "web_search", "terminal", "write_file"]
            g.record_turn(tools=[tools[i]], files_touched={"file.txt"}, has_new_info=True)
        report = g.run_checks()
        assert report.is_clean

    def test_loop_detected(self):
        g = DegenerationGuard()
        for i in range(6):
            g.record_turn(tools=["read_file"], has_new_info=False)
        report = g.run_checks()
        assert not report.is_clean
        assert report.signal == DegenerationSignal.LOOP_DETECTED

    def test_loop_with_file_progress_not_detected(self):
        g = DegenerationGuard()
        for i in range(6):
            g.record_turn(
                tools=["read_file"],
                files_touched={f"file_{i}.txt"},  # different files → progress
                has_new_info=True,
            )
        report = g.run_checks()
        # Loop detection checks for zero file progress across all turns
        # With different files each turn, there IS progress
        # Note: loop detection is per-tool count; 6x read_file with files → no loop
        assert report.signal != DegenerationSignal.LOOP_DETECTED


class TestInformationDensity:
    """Info density < min threshold."""

    def test_all_new_info_clean(self):
        g = DegenerationGuard()
        tools_cycle = ["read_file", "search_files", "web_search", "terminal", "write_file"]
        for i in range(5):
            g.record_turn(tools=[tools_cycle[i]], has_new_info=True, files_touched={"f.txt"})
        report = g.run_checks()
        assert report.is_clean

    def test_low_density_detected(self):
        g = DegenerationGuard()
        for i in range(5):
            g.record_turn(tools=["read_file"], has_new_info=False)
        report = g.run_checks()
        assert not report.is_clean

    def test_mixed_density(self):
        g = DegenerationGuard()
        for i in range(5):
            g.record_turn(
                tools=[f"tool_{i % 3}"],  # diverse tools
                files_touched={f"f_{i}.txt"},
                has_new_info=(i % 3 == 0),  # 2/5 = 40%
            )
        report = g.run_checks()
        # 40% → exactly at threshold (not below), should be clean
        assert not any("LOW_INFORMATION_DENSITY" in w for w in report.warnings)


class TestContextQuality:
    """Context quality after compression."""

    def test_no_compression_no_warning(self):
        g = DegenerationGuard()
        report = g.run_checks()
        assert report.is_clean  # no context quality check without compression data

    def test_good_retention(self):
        g = DegenerationGuard()
        g.record_compression(100, 80, 0.80)
        report = g.run_checks()
        assert report.is_clean

    def test_poor_retention(self):
        g = DegenerationGuard()
        g.record_compression(100, 30, 0.30)
        report = g.run_checks()
        assert not report.is_clean
        assert report.signal == DegenerationSignal.CONTEXT_QUALITY_DROP


class TestSurpriseGate:
    """Semantic vs surface deviation."""

    def test_surprise_existence_mismatch(self):
        g = DegenerationGuard()
        msg = g.detect_surprise(
            expected="file should be found at /tmp/test",
            actual="file not found: /tmp/test does not exist",
        )
        assert msg is not None
        assert "SURPRISE" in msg

    def test_surprise_outcome_reversal(self):
        g = DegenerationGuard()
        msg = g.detect_surprise(
            expected="build should pass",
            actual="build failed with errors",
        )
        assert msg is not None
        assert "SURPRISE" in msg

    def test_no_surprise_same_tenor(self):
        g = DegenerationGuard()
        msg = g.detect_surprise(
            expected="file content: hello world",
            actual="file content: hello world\n",
        )
        assert msg is None  # no semantic contradiction


class TestRecoveryLoopSignal:
    """Recovery loop → degeneration guard signal channel."""

    def test_external_signal_propagation(self):
        g = DegenerationGuard()
        g.record_signal("recovery_loop", {
            "count": 3,
            "unique_errors": 2,
            "task_id": "test",
            "message": "🔴 RECOVERY_LOOP: ...",
        })
        msg = g.detect_recovery_loop()
        assert msg is not None
        assert "RECOVERY_LOOP" in msg

    def test_no_signal_clean(self):
        g = DegenerationGuard()
        msg = g.detect_recovery_loop()
        assert msg is None


class TestRunChecksPriority:
    """run_checks() returns highest-priority signal first."""

    def test_clean(self):
        g = DegenerationGuard()
        g.record_turn(tools=["read_file"], has_new_info=True)
        report = g.run_checks()
        assert report.is_clean

    def test_recovery_loop_priority(self):
        g = DegenerationGuard()
        g.record_signal("recovery_loop", {
            "count": 3, "unique_errors": 2, "task_id": "t",
            "message": "🔴 RECOVERY_LOOP",
        })
        # Also trigger loop detection
        for i in range(6):
            g.record_turn(tools=["read_file"], has_new_info=False)
        report = g.run_checks()
        # Recovery loop takes priority (checked first)
        assert report.signal == DegenerationSignal.RECOVERY_LOOP

    def test_surprise_priority_over_warnings(self):
        g = DegenerationGuard()
        tools_cycle = ["read_file", "search_files", "web_search", "terminal", "write_file", "read_file"]
        for i in range(6):
            g.record_turn(tools=[tools_cycle[i]], has_new_info=True, files_touched={"f.txt"})
        report = g.run_checks(
            expected_vs_actual=("file exists", "file doesn't exist"),
        )
        assert report.signal == DegenerationSignal.SURPRISE_DETECTED


class TestGlobalInstance:
    """Global singleton behavior."""

    def test_singleton(self):
        g1 = get_guard()
        g2 = get_guard()
        assert g1 is g2

    def test_reset_global(self):
        g = get_guard()
        g.record_turn(tools=["read_file"])
        reset_guard()
        g2 = get_guard()
        assert g2._turn_counter == 0
