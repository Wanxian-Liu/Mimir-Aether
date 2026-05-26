"""Horizon B1 · OBS-B1-02 — ops panel + monitor thresholds."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPS_PANEL = ROOT / "docs/ops/MIMIR_OPS_PANEL.md"
HEALTH_SCRIPT = ROOT / "scripts/mimir_health_check.sh"
MONITOR = ROOT / "agent/monitor.py"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
TIER0 = ROOT / "run_ralph_tier0.sh"


def test_ops_panel_documents_weekly_and_thresholds():
    assert OPS_PANEL.is_file()
    text = OPS_PANEL.read_text(encoding="utf-8")
    assert "mimir_health_check.sh" in text
    assert "MIMIR_MONITOR_ERROR_RATE_THRESHOLD" in text
    assert "TRUNCATE" in text
    assert "run_evolution_eval" in text


def test_health_script_has_r3b_and_truncate_env():
    text = HEALTH_SCRIPT.read_text(encoding="utf-8")
    assert "check_r3b" in text
    assert "MIMIR_TRUNCATE_SINCE_START_MAX" in text
    assert "MIMIR_MONITOR_ERROR_RATE_THRESHOLD" in text


def test_monitor_exports_threshold_helpers():
    text = MONITOR.read_text(encoding="utf-8")
    assert "get_monitor_error_rate_threshold" in text
    assert "get_monitor_window_seconds" in text
    assert "MIMIR_MONITOR_ERROR_RATE_THRESHOLD" in text


def test_backlog_obs_b1_02_present():
    assert "**OBS-B1-02**" in BACKLOG.read_text(encoding="utf-8")


def test_obs_b1_02_contract_in_tier0():
    assert "tests/contract/test_horizon_obs_b1_02.py" in TIER0.read_text(encoding="utf-8")
