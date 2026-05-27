"""HERM-TGR-02: tool_call_cache hit/miss/size metrics and optional logging."""

from __future__ import annotations

import logging

import pytest

from agent import tool_call_cache as tcc


@pytest.fixture(autouse=True)
def _reset_cache_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIMIR_TOOL_CALL_CACHE", "1")
    monkeypatch.delenv("MIMIR_TOOL_CACHE_LOG", raising=False)
    tcc.clear_cache()
    tcc.reset_stats()


def test_get_stats_initial() -> None:
    assert tcc.get_stats() == {"hits": 0, "misses": 0, "size": 0}


def test_miss_on_empty_lookup() -> None:
    assert tcc.get_cached("read_file", {"path": "/a"}) is None
    assert tcc.get_stats()["misses"] == 1
    assert tcc.get_stats()["hits"] == 0


def test_hit_after_set() -> None:
    tcc.set_cached("read_file", {"path": "/a"}, "body")
    assert tcc.get_stats()["size"] == 1
    assert tcc.get_cached("read_file", {"path": "/a"}) == "body"
    stats = tcc.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0


def test_non_cacheable_tool_not_counted() -> None:
    assert not tcc.should_cache_tool("write_file")
    assert tcc.get_cached("write_file", {"path": "/a"}) is None
    assert tcc.get_stats() == {"hits": 0, "misses": 0, "size": 0}


def test_cache_log_emits_info_line(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIMIR_TOOL_CACHE_LOG", "1")
    caplog.set_level(logging.INFO, logger="agent.tool_call_cache")
    tcc.set_cached("read_file", {"path": "/x"}, "ok")
    tcc.get_cached("read_file", {"path": "/x"})
    assert any("tool_call_cache" in r.message for r in caplog.records)
