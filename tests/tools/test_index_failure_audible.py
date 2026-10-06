"""索引面「静默失败 → 出声 + 计数」回归（P0 诊断 2026-10-05 §8-2）。

背景：三级 fail-open 只记 `logger.debug`，某会话掉了 91% 索引而盘上无痕。
本套用**受控差分**证明四处呼叫点都会（a）WARNING 出声（b）计数落盘。
"""
from __future__ import annotations

import logging

import pytest

from tools import chroma_session_indexer as csi
from tools import session_search_indexer as ssi
from tools.chroma_session_indexer import IndexedMessage


@pytest.fixture()
def counter_path(tmp_path, monkeypatch):
    p = tmp_path / "data" / "index_failure_counts.json"
    monkeypatch.setattr(csi, "_index_failure_path", lambda: p)
    monkeypatch.setattr(csi, "_INDEX_FAILURE_COUNTS", {})
    return p


def test_note_index_failure_writes_counter_and_warns(counter_path, caplog):
    with caplog.at_level(logging.WARNING, logger="tools.chroma_session_indexer"):
        csi.note_index_failure("unit_stage", ValueError("boom"), sink="test")
        csi.note_index_failure("unit_stage", ValueError("boom2"), sink="test")

    data = csi.index_failure_counts()
    assert data["unit_stage"]["count"] == 2
    assert data["unit_stage"]["last_error"] == "ValueError: boom2"
    assert data["unit_stage"]["sink"] == "test"
    assert any("[INDEX-FAIL]" in r.getMessage() for r in caplog.records)
    assert all(r.levelno >= logging.WARNING for r in caplog.records)


def test_counter_is_empty_dict_when_missing(counter_path):
    assert csi.index_failure_counts() == {}


def test_sync_message_to_chroma_failure_is_audible(counter_path, monkeypatch):
    monkeypatch.setattr(csi, "chroma_incremental_enabled", lambda: True)

    def _boom(*_a, **_k):
        raise RuntimeError("upsert exploded")

    monkeypatch.setattr(csi, "upsert_indexed_messages", _boom)
    ok = csi.sync_message_to_chroma(
        IndexedMessage(message_id=1, session_id="s", role="user", content="hi",
                       source="test", timestamp=1.0)
    )
    assert ok is False
    assert csi.index_failure_counts()["incremental_upsert"]["count"] == 1


def test_incremental_hook_failure_is_audible(counter_path, monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("hook exploded")

    monkeypatch.setattr(csi, "sync_message_to_chroma", _boom)

    class _DB:
        db_path = "/tmp/nonexistent-sessions.db"

        def add_session(self, *a, **k):
            return None

        def add_message(self, *a, **k):
            return 42

    assert ssi.index_transcript_message(
        "s1", {"role": "user", "content": "hello"}, like_db=_DB()
    )
    assert csi.index_failure_counts()["incremental_hook"]["count"] == 1


def test_gateway_helper_falls_back_to_log_without_raising(counter_path, monkeypatch, caplog):
    import gateway.session as gs

    def _boom(*_a, **_k):
        raise ImportError("counter unavailable")

    monkeypatch.setattr(csi, "note_index_failure", _boom)
    with caplog.at_level(logging.WARNING, logger="gateway.session"):
        gs._note_index_failure("append", RuntimeError("x"))

    assert any("[INDEX-FAIL]" in r.getMessage() for r in caplog.records)


def test_gateway_helper_counts_via_shared_counter(counter_path):
    import gateway.session as gs

    gs._note_index_failure("sessions_search_rewrite", RuntimeError("rw"))
    assert csi.index_failure_counts()["sessions_search_rewrite"]["count"] == 1
