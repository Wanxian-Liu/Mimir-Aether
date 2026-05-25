"""SEM-03: semantic / semantic_hybrid session_search backends."""

from __future__ import annotations

from unittest.mock import patch

from tools.session_search_tool import (
    SessionSearchDB,
    get_session_search_backend,
    session_search,
)


def test_get_session_search_backend_semantic_values(monkeypatch):
    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic")
    assert get_session_search_backend() == "semantic"
    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic_hybrid")
    assert get_session_search_backend() == "semantic_hybrid"


def test_semantic_returns_empty_without_like_fallback(tmp_path, monkeypatch):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="cli", title="t")
    db.add_message("s1", "user", "unique-keyword-xyz")

    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic")
    with patch(
        "tools.session_search_tool._semantic_index_ready",
        return_value=True,
    ), patch(
        "tools.chroma_session_indexer.query_session_messages",
        return_value=[],
    ):
        results = session_search("unique-keyword-xyz", db_path=str(db_path))
    assert results == []


def test_semantic_hybrid_falls_back_to_like(tmp_path, monkeypatch):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="cli", title="t")
    db.add_message("s1", "user", "fallback-like-token")

    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic_hybrid")
    with patch(
        "tools.session_search_tool._semantic_index_ready",
        return_value=True,
    ), patch(
        "tools.chroma_session_indexer.query_session_messages",
        return_value=[],
    ):
        results = session_search("fallback-like-token", db_path=str(db_path))
    assert len(results) == 1
    assert results[0]["session_id"] == "s1"


def test_semantic_returns_chroma_hits_grouped_by_session(tmp_path, monkeypatch):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="cli", title="Demo")
    db.add_message("s1", "user", "ignored for chroma path")

    chroma_hits = [
        {
            "id": "s1:1",
            "content": "飞书 webhook 配置步骤",
            "metadata": {
                "session_id": "s1",
                "message_id": 1,
                "role": "user",
                "source": "cli",
                "timestamp": 1.0,
            },
            "distance": 0.1,
        }
    ]

    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic")
    with patch(
        "tools.session_search_tool._semantic_index_ready",
        return_value=True,
    ), patch(
        "tools.chroma_session_indexer.query_session_messages",
        return_value=chroma_hits,
    ):
        results = session_search("飞书", db_path=str(db_path))

    assert len(results) == 1
    assert results[0]["session_id"] == "s1"
    assert results[0]["title"] == "Demo"
    assert "飞书" in results[0]["summary"]


def test_semantic_hybrid_uses_semantic_when_hits_exist(tmp_path, monkeypatch):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="cli", title="t")
    db.add_message("s1", "user", "no-like-match-here")

    chroma_hits = [
        {
            "id": "s1:9",
            "content": "semantic-only hit",
            "metadata": {
                "session_id": "s1",
                "message_id": 9,
                "role": "assistant",
                "source": "cli",
                "timestamp": 2.0,
            },
            "distance": 0.05,
        }
    ]

    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic_hybrid")
    with patch(
        "tools.session_search_tool._semantic_index_ready",
        return_value=True,
    ), patch(
        "tools.chroma_session_indexer.query_session_messages",
        return_value=chroma_hits,
    ):
        results = session_search("no-like-match-here", db_path=str(db_path))

    assert len(results) == 1
    assert "semantic-only hit" in results[0]["summary"]
