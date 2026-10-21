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
    """Incremental path must not re-pollute the index with system boilerplate.

    Stubs upsert so the test asserts the *guard* (garbage rejected before any
    upsert call), not the environment's chromadb/embedding availability.
    """
    monkeypatch.setenv("MIMIR_CHROMA_INCREMENTAL", "1")
    upsert_calls: list = []
    monkeypatch.setattr(
        "tools.chroma_session_indexer.upsert_indexed_messages",
        lambda msgs, **kw: upsert_calls.append(msgs) or len(msgs),
    )

    garbage = IndexedMessage(
        message_id=1,
        session_id="s1",
        role="assistant",
        content="抱歉,任务迭代次数已达上限。",
        source="feishu",
        timestamp=0.0,
    )
    assert sync_message_to_chroma(garbage) is False
    assert upsert_calls == []  # garbage never reaches chroma

    legit = IndexedMessage(
        message_id=2,
        session_id="s1",
        role="assistant",
        content="正常回答内容",
        source="feishu",
        timestamp=0.0,
    )
    assert sync_message_to_chroma(legit) is True
    assert len(upsert_calls) == 1  # legit content still upserts


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


# --------------------------------------------------------------------------- #
# RL-20261020-094 B2: the embedding pass must happen OUTSIDE the write lock
# --------------------------------------------------------------------------- #
import time  # noqa: E402

import pytest  # noqa: E402

import tools.chroma_session_indexer as csi  # noqa: E402


class SlowEF:
    """Deterministic embedding function that spends real wall time per document.

    Cost model mirrors production (bge-m3 embeds per document), so a lock-held
    measurement on this fixture is a genuine proxy: before the move, every
    ``sleep_per_doc`` was spent *inside* the guard.
    """

    def __init__(self, sleep_per_doc: float = 0.05, dim: int = 8):
        self.sleep_per_doc = sleep_per_doc
        self.dim = dim

    def __call__(self, input):  # chroma EmbeddingFunction protocol signature
        out = []
        for text in input:
            if self.sleep_per_doc:
                time.sleep(self.sleep_per_doc)
            vec = [0.0] * self.dim
            for i, ch in enumerate(str(text)):
                vec[i % self.dim] += (ord(ch) % 97) / 97.0
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            out.append([v / norm for v in vec])
        return out

    # chroma 1.x EmbeddingFunction surface (needed for a real collection)
    @staticmethod
    def name():
        return "slow-ef-test"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return SlowEF(sleep_per_doc=0.0)


class RecordingCollection:
    """Minimal collection double: only what _upsert_batch touches."""

    def __init__(self, ef):
        self._embedding_function = ef
        self.calls = []

    def upsert(self, **kwargs):
        self.calls.append(kwargs)


def _batch_of(n: int):
    return [
        csi.IndexedMessage(
            message_id=i,
            session_id="s1",
            role="user",
            content=f"document number {i}",
            source="test",
            timestamp=float(i),
        )
        for i in range(1, n + 1)
    ]


def test_embedding_is_computed_outside_the_write_lock(monkeypatch, tmp_path):
    """Two-sided: lock budget (<1s) AND the embedding really ran (>=6s total).

    Arm 1 measures the lock budget on a 128-doc batch with an EF that costs
    0.05s/doc. Arm 2 proves the vectors reaching chroma are the EF's own — a
    real chroma 1.5.9 collection, ``collection.get(include=["embeddings"])``
    compared element-wise with a direct ``ef([text])[0]``.
    """
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))  # lock file -> tmp
    real_lock = csi.chroma_write_lock
    spans = []

    class RecordingGuard:
        def __init__(self):
            self._inner = real_lock()
            self._t0 = 0.0

        def __enter__(self):
            self._t0 = time.monotonic()
            return self._inner.__enter__()

        def __exit__(self, *exc):
            try:
                return self._inner.__exit__(*exc)
            finally:
                spans.append(time.monotonic() - self._t0)

    monkeypatch.setattr(csi, "chroma_write_lock", lambda: RecordingGuard())
    ef = SlowEF(sleep_per_doc=0.05)
    collection = RecordingCollection(ef)

    # ---- arm 1: lock budget on a 128-document batch ----------------------- #
    t0 = time.monotonic()
    written = csi._upsert_batch(collection, _batch_of(128))
    total = time.monotonic() - t0
    held = sum(spans)

    assert written == 128
    assert len(spans) == 1, spans
    assert len(collection.calls) == 1
    assert len(collection.calls[0]["embeddings"]) == 128  # precomputed, outside
    assert total >= 6.0, f"embedding did not actually run: total={total:.3f}s"
    assert held < 1.0, f"embedding still inside the lock: held={held:.3f}s"

    # ---- arm 2: vectors reach chroma verbatim ---------------------------- #
    chromadb = pytest.importorskip("chromadb")
    plain_ef = SlowEF(sleep_per_doc=0.0)
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    real_collection = client.get_or_create_collection(
        name="verbatim_check",
        embedding_function=plain_ef,
        metadata={"hnsw:space": "cosine"},
    )
    samples = _batch_of(3)
    assert csi._upsert_batch(real_collection, samples) == 3

    ids = [csi.message_doc_id(m.session_id, m.message_id) for m in samples]
    got = real_collection.get(ids=ids, include=["embeddings"])
    assert sorted(got["ids"]) == sorted(ids)
    stored = dict(zip(got["ids"], got["embeddings"]))
    for msg in samples:
        doc_id = csi.message_doc_id(msg.session_id, msg.message_id)
        expected = plain_ef([msg.content])[0]
        actual = stored[doc_id]
        assert len(actual) == len(expected)
        delta = max(abs(float(a) - float(b)) for a, b in zip(actual, expected))
        assert delta < 1e-6, f"{doc_id}: max|delta|={delta}"
