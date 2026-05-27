"""OS-SCH-02: RRF fusion ranking for session_search semantic_hybrid."""

from __future__ import annotations

from unittest.mock import patch

from tools.session_search_tool import (
    SessionSearchDB,
    rank_fusion_rrf,
    session_search,
    session_search_fusion_enabled,
)


def test_rank_fusion_rrf_boosts_overlap():
    fused = rank_fusion_rrf(
        {
            "lexical": ["a", "b", "c"],
            "semantic": ["b", "d"],
        },
        k=60,
    )
    order = [sid for sid, _ in fused]
    assert order[0] == "b"
    assert set(order) == {"a", "b", "c", "d"}


def test_rank_fusion_rrf_empty_lists():
    assert rank_fusion_rrf({"lexical": [], "semantic": []}) == []


def test_session_search_fusion_disabled(monkeypatch, tmp_path):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="cli", title="t")
    db.add_message("s1", "user", "waterfall-token")

    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic_hybrid")
    monkeypatch.setenv("MIMIR_SESSION_SEARCH_FUSION", "0")
    with patch(
        "tools.session_search_tool._semantic_index_ready",
        return_value=True,
    ), patch(
        "tools.chroma_session_indexer.query_session_messages",
        return_value=[],
    ):
        results = session_search("waterfall-token", db_path=str(db_path))
    assert len(results) == 1


def test_semantic_hybrid_fusion_prefers_semantic_messages(tmp_path, monkeypatch):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="cli", title="Demo")
    db.add_message("s1", "user", "sqlite filler only")

    chroma_hits = [
        {
            "id": "s1:1",
            "content": "semantic fusion winner",
            "metadata": {
                "session_id": "s1",
                "message_id": 1,
                "role": "assistant",
                "source": "cli",
                "timestamp": 1.0,
            },
            "distance": 0.02,
        }
    ]

    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic_hybrid")
    monkeypatch.delenv("MIMIR_SESSION_SEARCH_FUSION", raising=False)
    assert session_search_fusion_enabled()

    with patch(
        "tools.session_search_tool._semantic_index_ready",
        return_value=True,
    ), patch(
        "tools.chroma_session_indexer.query_session_messages",
        return_value=chroma_hits,
    ), patch(
        "tools.session_search_tool._default_fts5_db_path",
        return_value=str(tmp_path / "missing_fts.db"),
    ):
        results = session_search("fusion query", db_path=str(db_path))

    assert len(results) == 1
    assert "semantic fusion winner" in results[0]["summary"]


def test_fusion_orders_semantic_only_when_lexical_empty(tmp_path, monkeypatch):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="cli", title="t")
    db.add_message("s1", "user", "unrelated sqlite text")

    chroma_hits = [
        {
            "id": "s1:9",
            "content": "only semantic leg",
            "metadata": {
                "session_id": "s1",
                "message_id": 9,
                "role": "user",
                "timestamp": 2.0,
            },
            "distance": 0.1,
        }
    ]

    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic_hybrid")
    with patch(
        "tools.session_search_tool._semantic_index_ready",
        return_value=True,
    ), patch(
        "tools.chroma_session_indexer.query_session_messages",
        return_value=chroma_hits,
    ), patch(
        "tools.session_search_tool._default_fts5_db_path",
        return_value=str(tmp_path / "no_fts.db"),
    ):
        results = session_search("paraphrase-only", db_path=str(db_path))

    assert len(results) == 1
    assert "only semantic leg" in results[0]["summary"]
