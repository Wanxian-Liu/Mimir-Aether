"""WB-B02: VoE surprise → JSONL learning event tests."""

from __future__ import annotations

import json

from agent.degeneration_guard import DegenerationGuard
from agent.wm_voe_learning import append_surprise_event, is_wm_voe_learning_enabled


_REQUIRED_FIELDS = {
    "schema_version",
    "event_type",
    "timestamp",
    "expected",
    "actual",
    "surprise_label",
    "context_snapshot",
    "guard_message",
}


def test_append_surprise_event_writes_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "1")
    out = tmp_path / "surprise_events.jsonl"
    index = tmp_path / "learned_surprises.json"
    append_surprise_event(
        expected="command success",
        actual="command failed",
        surprise_label="outcome reversal",
        context_snapshot={"session_id": "s1"},
        guard_message="🔴 SURPRISE_DETECTED: outcome reversal — expected 'x' but got 'y'.",
        path=out,
        learned_path=index,
    )
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert _REQUIRED_FIELDS <= set(row.keys())
    assert row["schema_version"] == 1
    assert row["event_type"] == "voe_surprise"
    assert row["expected"] == "command success"
    assert row["actual"] == "command failed"
    assert row["surprise_label"] == "outcome reversal"
    assert row["context_snapshot"] == {"session_id": "s1"}


def test_run_checks_hook_writes_once_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "1")
    out = tmp_path / "events.jsonl"
    index = tmp_path / "learned_surprises.json"
    monkeypatch.setattr(
        "agent.wm_voe_learning.default_surprise_events_path",
        lambda: out,
    )
    monkeypatch.setattr(
        "agent.wm_voe_learning.default_learned_surprises_path",
        lambda: index,
    )
    guard = DegenerationGuard()
    report = guard.run_checks(expected_vs_actual=("operation success", "operation failed"))
    assert report.signal.value == "surprise_detected"
    assert len(out.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_run_checks_hook_no_write_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "0")
    out = tmp_path / "events.jsonl"
    index = tmp_path / "learned_surprises.json"
    monkeypatch.setattr(
        "agent.wm_voe_learning.default_surprise_events_path",
        lambda: out,
    )
    monkeypatch.setattr(
        "agent.wm_voe_learning.default_learned_surprises_path",
        lambda: index,
    )
    guard = DegenerationGuard()
    guard.run_checks(expected_vs_actual=("operation success", "operation failed"))
    assert not out.exists()


def test_append_twice_produces_two_lines(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "1")
    out = tmp_path / "surprise_events.jsonl"
    index = tmp_path / "learned_surprises.json"
    msg = "🔴 SURPRISE_DETECTED: outcome reversal — expected 'a' but got 'b'."
    for _ in range(2):
        append_surprise_event("success", "failed", "outcome reversal", {}, msg, path=out, learned_path=index)
    assert len(out.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_wm_voe_learning_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MIMIR_WM_VOE_LEARNING", raising=False)
    assert is_wm_voe_learning_enabled() is False
