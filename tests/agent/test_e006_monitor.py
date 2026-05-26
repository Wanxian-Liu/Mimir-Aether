"""E-006 D6-0b — agent monitor thresholds and alerts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_monitor_error_rate_and_alert_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    from agent.monitor import (
        get_agent_error_rate,
        get_agent_health_status,
        record_tool_outcome,
        reset_monitor_state,
    )

    reset_monitor_state()

    for _ in range(5):
        record_tool_outcome("ok_tool", success=True)
    for _ in range(5):
        record_tool_outcome("bad_tool", success=False, error_message="boom")

    rate = get_agent_error_rate()
    assert rate == 0.5
    assert get_agent_health_status() == "degraded"

    alert_path = tmp_path / "data" / "monitor_alerts.json"
    assert alert_path.exists()
    alerts = json.loads(alert_path.read_text(encoding="utf-8"))
    assert isinstance(alerts, list)
    assert alerts[-1]["agent_error_rate"] > 0.10

    reset_monitor_state()


def test_monitor_threshold_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_MONITOR_ERROR_RATE_THRESHOLD", "0.25")
    from agent.monitor import (
        get_agent_health_status,
        get_monitor_error_rate_threshold,
        record_tool_outcome,
        reset_monitor_state,
    )

    reset_monitor_state()
    assert get_monitor_error_rate_threshold() == 0.25

    for _ in range(4):
        record_tool_outcome("ok_tool", success=True)
    record_tool_outcome("bad_tool", success=False)
    assert get_agent_health_status() == "ok"

    for _ in range(4):
        record_tool_outcome("bad_tool", success=False)
    assert get_agent_health_status() == "degraded"

    reset_monitor_state()
