"""E-011b: tool duration percentiles in monitor + /health (ISSUES #11)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_health_snapshot_includes_tool_duration_percentiles(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    from agent.monitor import (
        get_tool_duration_percentiles,
        record_tool_outcome,
        reset_monitor_state,
        snapshot_for_health,
    )

    reset_monitor_state()
    for ms in (10.0, 20.0, 30.0, 40.0, 1000.0):
        record_tool_outcome("read_file", success=True, duration_ms=ms)

    pct = get_tool_duration_percentiles()
    assert pct["p50_ms"] >= 20.0
    assert pct["p95_ms"] >= 40.0
    assert pct["p99_ms"] >= 40.0

    snap = snapshot_for_health()
    assert snap["agent_tool_p50_ms"] >= 20.0
    assert snap["agent_tool_p95_ms"] >= 40.0
    assert snap["agent_tool_p99_ms"] >= 40.0

    reset_monitor_state()
