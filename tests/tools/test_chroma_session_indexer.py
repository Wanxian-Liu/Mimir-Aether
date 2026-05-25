"""Unit tests for chroma_session_indexer (SEM-02)."""

from __future__ import annotations

from unittest.mock import MagicMock

from tools.chroma_session_indexer import (
    COLLECTION_NAME,
    ChromaBackfillStats,
    backfill_chroma_sessions,
    hash_embed_batch,
    hash_embed_text,
    iter_indexable_messages,
    message_doc_id,
)
from tools.session_search_tool import SessionSearchDB


def test_message_doc_id_stable():
    assert message_doc_id("sess-1", 42) == "sess-1:42"


def test_hash_embed_deterministic():
    a = hash_embed_text("hello world")
    b = hash_embed_text("hello world")
    assert a == b
    assert len(a) == 384
    norm = sum(v * v for v in a) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_hash_embed_batch_matches_single():
    texts = ["alpha", "beta"]
    batch = hash_embed_batch(texts)
    assert len(batch) == 2
    assert batch[0] == hash_embed_text("alpha")


def test_iter_indexable_messages_skips_empty(tmp_path):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="test", title="t")
    db.add_message("s1", "user", "hello")
    db.add_message("s1", "assistant", "   ")

    rows = list(iter_indexable_messages(db_path))
    assert len(rows) == 1
    assert rows[0].session_id == "s1"
    assert rows[0].content == "hello"
    assert rows[0].source == "test"


def test_backfill_chroma_sessions_idempotent_upsert(tmp_path):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="cli", title="demo")
    db.add_message("s1", "user", "semantic memory test")
    db.add_message("s1", "assistant", "acknowledged")

    collection = MagicMock()
    stats1 = backfill_chroma_sessions(db_path, collection=collection)
    assert stats1.messages_indexed == 2
    assert stats1.batches == 1
    collection.upsert.assert_called_once()
    call = collection.upsert.call_args.kwargs
    assert call["ids"] == ["s1:1", "s1:2"]
    assert call["documents"] == ["semantic memory test", "acknowledged"]
    assert call["metadatas"][0]["session_id"] == "s1"
    assert call["metadatas"][0]["message_id"] == 1

    collection.reset_mock()
    stats2 = backfill_chroma_sessions(db_path, collection=collection)
    assert stats2.messages_indexed == 2
    collection.upsert.assert_called_once()


def test_backfill_missing_db_returns_zero_stats(tmp_path):
    stats = backfill_chroma_sessions(tmp_path / "missing.db", collection=MagicMock())
    assert stats == ChromaBackfillStats()


def test_collection_name_constant():
    assert COLLECTION_NAME == "session_messages"
