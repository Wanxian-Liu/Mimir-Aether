"""IEVO-05 / D6-3: monitor + insights tests stay on tier0 (≥3 paths)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIER0 = ROOT / "run_ralph_tier0.sh"

# D6-3 regression bundle (keep in sync with run_ralph_tier0.sh).
D6_MONITOR_INSIGHTS_TIER0 = (
    "tests/agent/test_e006_tool_call_sql.py",
    "tests/agent/test_e006_monitor.py",
    "tests/agent/test_e011_monitor_duration.py",
    "tests/agent/test_ievo05_monitor_insights_regression.py",
)


def test_d6_monitor_insights_paths_listed_in_run_ralph_tier0():
    text = TIER0.read_text(encoding="utf-8")
    missing = [p for p in D6_MONITOR_INSIGHTS_TIER0 if p not in text]
    assert not missing, "add to run_ralph_tier0.sh:\n" + "\n".join(missing)


def test_insights_engine_module_exports_sql_entrypoint():
    text = (ROOT / "agent/insights.py").read_text(encoding="utf-8")
    assert "class InsightsEngine" in text
    assert "def _generate_sql" in text
    assert "TOOL_CALL" in text


def test_monitor_module_exports_health_snapshot():
    text = (ROOT / "agent/monitor.py").read_text(encoding="utf-8")
    assert "def snapshot_for_health" in text
    assert "def record_tool_outcome" in text
    assert "monitor_alerts.json" in text
