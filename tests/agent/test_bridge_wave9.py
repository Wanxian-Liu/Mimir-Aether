"""Bridge Wave 9: context usage hint, subdirectory hints wiring, read-only tool cache."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent.prompt_builder import _build_context_usage_hint, _build_cross_session_context
from agent.subdirectory_hints import SubdirectoryHintTracker
from agent.tool_call_cache import get_cached, set_cached, should_cache_tool


def test_context_usage_hint_from_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    ops = tmp_path / "data" / "ops"
    ops.mkdir(parents=True)
    (ops / "last_context_usage.json").write_text(
        json.dumps({"total_tokens": 12000, "threshold_tokens": 100000, "message_count": 42}),
        encoding="utf-8",
    )
    hint = _build_context_usage_hint()
    assert "12000" in hint
    assert "100000" in hint
    assert "42" in hint


def test_cross_session_includes_context_usage_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data" / "persistent.json").write_text(
        json.dumps({"session_count": 1, "memory": {}}),
        encoding="utf-8",
    )
    (tmp_path / "data" / "ops").mkdir(parents=True)
    (tmp_path / "data" / "ops" / "last_context_usage.json").write_text(
        json.dumps({"total_tokens": 999}),
        encoding="utf-8",
    )
    ctx = _build_cross_session_context()
    assert "999" in ctx


def test_subdirectory_hint_on_first_visit(tmp_path: Path) -> None:
    sub = tmp_path / "backend"
    sub.mkdir()
    (sub / "AGENTS.md").write_text("backend agents rules", encoding="utf-8")
    tracker = SubdirectoryHintTracker(working_dir=tmp_path)
    hints = tracker.check_tool_call("read_file", {"path": str(sub / "main.py")})
    assert hints is not None
    assert "backend agents" in hints


def test_tool_call_cache_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIMIR_TOOL_CALL_CACHE", "1")
    assert should_cache_tool("read_file")
    set_cached("read_file", {"path": "/tmp/x"}, "hello")
    assert get_cached("read_file", {"path": "/tmp/x"}) == "hello"
    assert get_cached("read_file", {"path": "/tmp/y"}) is None
