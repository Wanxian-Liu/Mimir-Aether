"""WM-P11-01: learned surprise recall index tests."""

from __future__ import annotations

import json

from agent.wm_voe_learning import (
    append_surprise_event,
    lookup_learned_surprise,
    normalize_pair,
    record_surprise_learning,
)


def test_record_or_lookup_first_write(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "1")
    index_path = tmp_path / "learned_surprises.json"
    record_surprise_learning(
        "operation success",
        "operation failed",
        "outcome reversal",
        path=index_path,
    )
    data = json.loads(index_path.read_text(encoding="utf-8"))
    key = normalize_pair("operation success", "operation failed")
    assert key in data["entries"]
    assert data["entries"][key]["hit_count"] == 1
    assert data["entries"][key]["surprise_label"] == "outcome reversal"


def test_record_or_lookup_jsonl_dual_write(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "1")
    jsonl_path = tmp_path / "surprise_events.jsonl"
    index_path = tmp_path / "learned_surprises.json"
    msg = "🔴 SURPRISE_DETECTED: outcome reversal — expected 'a' but got 'b'."
    append_surprise_event(
        "operation success",
        "operation failed",
        "outcome reversal",
        {},
        msg,
        path=jsonl_path,
        learned_path=index_path,
    )
    assert len(jsonl_path.read_text(encoding="utf-8").strip().splitlines()) == 1
    assert index_path.exists()
    assert lookup_learned_surprise(
        "operation success", "operation failed", path=index_path
    )


def test_record_or_lookup_lookup_hit(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "1")
    index_path = tmp_path / "learned_surprises.json"
    record_surprise_learning("operation success", "operation failed", "outcome reversal", path=index_path)
    hit = lookup_learned_surprise("operation success", "operation failed", path=index_path)
    assert hit is not None
    assert "learning_hint" in hit
    assert hit["expected"] == "operation success"


def test_record_or_lookup_env_zero_no_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "0")
    jsonl_path = tmp_path / "surprise_events.jsonl"
    index_path = tmp_path / "learned_surprises.json"
    record_surprise_learning("a", "b", "label", path=index_path)
    append_surprise_event("a", "b", "label", {}, "msg", path=jsonl_path, learned_path=index_path)
    assert not jsonl_path.exists()
    assert not index_path.exists()


def test_record_or_lookup_increments_hit_count(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "1")
    index_path = tmp_path / "learned_surprises.json"
    for _ in range(2):
        record_surprise_learning("operation success", "operation failed", "outcome reversal", path=index_path)
    data = json.loads(index_path.read_text(encoding="utf-8"))
    key = normalize_pair("operation success", "operation failed")
    assert data["entries"][key]["hit_count"] == 2


def test_replan_context_surprise_has_learning_context(monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_REPLAN_CTX", "1")
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "0")
    monkeypatch.setenv("MIMIR_WM_VOE_RECALL", "0")
    from agent.degeneration_guard import DegenerationGuard

    report = DegenerationGuard().run_checks(
        expected_vs_actual=("operation success", "operation failed")
    )
    assert report.signal.value == "surprise_detected"
    ctx = report.details["wm_learning_context"]
    assert "Prior VoE" in ctx
    assert "operation success" in ctx
    assert "operation failed" in ctx
    assert "outcome reversal" in ctx


def test_replan_context_env_zero_no_field(monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_REPLAN_CTX", "0")
    monkeypatch.setenv("MIMIR_WM_VOE_RECALL", "0")
    from agent.degeneration_guard import DegenerationGuard

    report = DegenerationGuard().run_checks(
        expected_vs_actual=("operation success", "operation failed")
    )
    assert report.signal.value == "surprise_detected"
    assert "wm_learning_context" not in report.details


_PAIR = ("operation success", "operation failed")


def test_second_no_surprise_first_then_clean(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "1")
    monkeypatch.setenv("MIMIR_WM_VOE_RECALL", "1")
    jsonl_path = tmp_path / "surprise_events.jsonl"
    index_path = tmp_path / "learned_surprises.json"
    monkeypatch.setattr(
        "agent.wm_voe_learning.default_surprise_events_path",
        lambda: jsonl_path,
    )
    monkeypatch.setattr(
        "agent.wm_voe_learning.default_learned_surprises_path",
        lambda: index_path,
    )
    from agent.degeneration_guard import DegenerationGuard

    guard = DegenerationGuard()
    first = guard.run_checks(expected_vs_actual=_PAIR)
    second = guard.run_checks(expected_vs_actual=_PAIR)
    assert first.signal.value == "surprise_detected"
    assert second.signal.value == "clean"
    assert second.details.get("surprise_suppressed") is True
    assert second.details.get("suppressed_reason") == "learned_voe"
    assert len(jsonl_path.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_second_no_surprise_recall_off_writes_twice(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_WM_VOE_LEARNING", "1")
    monkeypatch.setenv("MIMIR_WM_VOE_RECALL", "0")
    jsonl_path = tmp_path / "surprise_events.jsonl"
    index_path = tmp_path / "learned_surprises.json"
    monkeypatch.setattr(
        "agent.wm_voe_learning.default_surprise_events_path",
        lambda: jsonl_path,
    )
    monkeypatch.setattr(
        "agent.wm_voe_learning.default_learned_surprises_path",
        lambda: index_path,
    )
    from agent.degeneration_guard import DegenerationGuard

    guard = DegenerationGuard()
    assert guard.run_checks(expected_vs_actual=_PAIR).signal.value == "surprise_detected"
    assert guard.run_checks(expected_vs_actual=_PAIR).signal.value == "surprise_detected"
    assert len(jsonl_path.read_text(encoding="utf-8").strip().splitlines()) == 2
