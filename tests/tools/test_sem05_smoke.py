"""SEM-05 smoke: SQLite → Chroma indexer → semantic session_search (mocked Chroma)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tools.chroma_session_indexer import backfill_chroma_sessions
from tools.session_search_tool import SessionSearchDB, session_search


def test_sem_smoke_sqlite_chroma_semantic_roundtrip(tmp_path, monkeypatch):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("wave-s1", source="cli", title="SEM smoke")
    db.add_message("wave-s1", "user", "Gateway 崩溃怎么恢复")

    collection = MagicMock()
    stats = backfill_chroma_sessions(db_path, collection=collection)
    assert stats.messages_indexed == 1
    collection.upsert.assert_called_once()

    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic")
    with patch("tools.session_search_tool._semantic_index_ready", return_value=True), patch(
        "tools.chroma_session_indexer.query_session_messages",
        return_value=[
            {
                "id": "wave-s1:1",
                "content": "Gateway 崩溃怎么恢复",
                "metadata": {
                    "session_id": "wave-s1",
                    "message_id": 1,
                    "role": "user",
                    "source": "cli",
                    "timestamp": 1.0,
                },
                "distance": 0.01,
            }
        ],
    ):
        results = session_search("Gateway 恢复", db_path=str(db_path))

    assert len(results) == 1
    assert results[0]["session_id"] == "wave-s1"
    assert "Gateway" in results[0]["summary"]
