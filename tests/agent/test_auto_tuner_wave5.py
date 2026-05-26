"""Tests for Wave 5 auto-tuner and tuned thresholds."""

from __future__ import annotations

import json

from agent import auto_tuner as at
from agent import tuned_thresholds as tt


def test_tuned_thresholds_clamp(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    tt.reset_overrides_for_tests()
    entry = tt.set_override("compressor.threshold_percent", 0.99, reason="test")
    assert entry["value"] == 0.70
    assert tt.get_tuned_float("compressor.threshold_percent") == 0.70


def test_auto_tuner_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("MIMIR_AUTO_TUNER", raising=False)
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    tt.reset_overrides_for_tests()
    changes = at.run_tune_after_pipeline_close({"degraded_tools": [("x", 0.1)]})
    assert changes == []


def test_auto_tuner_writes_audit(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_AUTO_TUNER", "1")
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    tt.reset_overrides_for_tests()
    fb = tmp_path / "data" / "feedback_events.jsonl"
    fb.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"event_type": "tool_failure", "payload": {"tool_name": "read_file"}},
    ] * 5
    fb.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    changes = at.run_tune_after_pipeline_close(
        {"degraded_tools": [("read_file", 0.2)], "errors": ["e1", "e2"]},
    )
    assert changes
    audit = (tmp_path / "data" / "tune_audit.jsonl").read_text(encoding="utf-8")
    assert "compressor.threshold_percent" in audit or "degeneration" in audit
