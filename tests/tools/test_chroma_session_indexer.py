"""Unit tests for chroma_session_indexer (SEM-02)."""

from __future__ import annotations

from unittest.mock import MagicMock

from tools.chroma_session_indexer import (
    COLLECTION_NAME,
    ChromaBackfillStats,
    IndexedMessage,
    backfill_chroma_sessions,
    hash_embed_batch,
    hash_embed_text,
    is_garbage_content,
    iter_indexable_messages,
    message_doc_id,
    sync_message_to_chroma,
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


def test_is_garbage_content_patterns():
    # System-error boilerplate and placeholders must be filtered (P0 audit).
    assert is_garbage_content("抱歉,任务迭代次数已达上限。")
    assert is_garbage_content("抱歉,任务迭代次数已达上限。\n这是什么意思")
    assert is_garbage_content("抱歉,模型调用失败,请稍后重试。")
    assert is_garbage_content("(No response generated)")
    assert is_garbage_content("[Old tool output cleared to save context space]")
    assert is_garbage_content("[CONTEXT COMPACTION — REFERENCE ONLY]")
    assert is_garbage_content("   ")  # whitespace-only
    assert is_garbage_content("")  # empty
    assert is_garbage_content(None)  # null-safe


def test_is_garbage_content_keeps_legit_mentions():
    # Substring-match would wrongly kill real conversation that *quotes* these
    # strings (verified against 20,895-row sessions_search.db on 2026-08-11).
    assert not is_garbage_content("刘哥，我用最简单的话说清楚。上下文 = 咱俩这次对话的记忆。")
    assert not is_garbage_content(
        "在 Mimir 的 system prompt 里加一条铁律：执行任何 '继续' 类操作前，必须先验证。"
    )
    assert not is_garbage_content("hello")
    assert not is_garbage_content("状态")
    assert not is_garbage_content("现在是第几次session")


def test_iter_indexable_messages_skips_garbage(tmp_path):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="test", title="t")
    db.add_message("s1", "user", "hello")
    db.add_message("s1", "assistant", "抱歉,任务迭代次数已达上限。")
    db.add_message("s1", "assistant", "(No response generated)")
    db.add_message("s1", "assistant", "正常回答内容")

    rows = list(iter_indexable_messages(db_path))
    contents = [r.content for r in rows]
    assert len(rows) == 2
    assert "hello" in contents
    assert "正常回答内容" in contents
    assert "抱歉" not in contents
    assert "(No response generated)" not in contents


def test_sync_message_to_chroma_skips_garbage(monkeypatch):
    """Incremental path must not re-pollute the index with system boilerplate."""
    monkeypatch.setenv("MIMIR_CHROMA_INCREMENTAL", "1")
    garbage = IndexedMessage(
        message_id=1,
        session_id="s1",
        role="assistant",
        content="抱歉,任务迭代次数已达上限。",
        source="feishu",
        timestamp=0.0,
    )
    assert sync_message_to_chroma(garbage) is False

    legit = IndexedMessage(
        message_id=2,
        session_id="s1",
        role="assistant",
        content="正常回答内容",
        source="feishu",
        timestamp=0.0,
    )
    # chromadb may or may not be installed in the test env; fail-open still
    # means: if it IS available, garbage must be rejected before any upsert.
    # We assert garbage is rejected in all cases; legit path is environment-dependent.
    from tools.chroma_session_indexer import chroma_available

    if chroma_available():
        assert sync_message_to_chroma(legit) is True
    else:
        assert sync_message_to_chroma(legit) is False


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
