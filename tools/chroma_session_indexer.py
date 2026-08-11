"""Backfill Chroma session_messages collection from sessions_search.db (SEM-02)."""

from __future__ import annotations

import hashlib
import logging
import math
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

COLLECTION_NAME = "session_messages"
DEFAULT_EMBED_DIM = 384
DEFAULT_BATCH_SIZE = 128


@dataclass
class ChromaBackfillStats:
    messages_indexed: int = 0
    messages_skipped: int = 0
    batches: int = 0


@dataclass(frozen=True)
class IndexedMessage:
    message_id: int
    session_id: str
    role: str
    content: str
    source: str
    timestamp: float
    tool_name: Optional[str] = None


def chroma_available() -> bool:
    """Return True when chromadb is importable."""
    try:
        import chromadb  # noqa: F401

        return True
    except ImportError:
        return False


def message_doc_id(session_id: str, message_id: int) -> str:
    """Stable Chroma document id for idempotent upsert."""
    return f"{session_id}:{message_id}"


def hash_embed_text(text: str, *, dim: int = DEFAULT_EMBED_DIM) -> List[float]:
    """Deterministic offline embedding (tier0 / dev without ML deps)."""
    vec = [0.0] * dim
    if not text:
        return vec
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    for i in range(dim):
        byte = digest[i % len(digest)]
        vec[i] = (byte / 255.0) * 2.0 - 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def hash_embed_batch(texts: Sequence[str], *, dim: int = DEFAULT_EMBED_DIM) -> List[List[float]]:
    return [hash_embed_text(t, dim=dim) for t in texts]


class HashEmbeddingFunction:
    """Chroma-compatible embedding function using hash_embed_batch."""

    def __init__(self, dim: int = DEFAULT_EMBED_DIM) -> None:
        self._dim = dim

    def __call__(self, input: Sequence[str]) -> List[List[float]]:
        return hash_embed_batch(list(input), dim=self._dim)

    def embed_query(self, input: Sequence[str]) -> List[List[float]]:
        return self.__call__(input)

    def name(self) -> str:
        return "hash_embedding"

    def get_config(self) -> Dict[str, Any]:
        return {"dim": self._dim}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "HashEmbeddingFunction":
        return HashEmbeddingFunction(dim=int(config.get("dim", DEFAULT_EMBED_DIM)))


def get_mimir_chroma_dir() -> Path:
    from mimir_constants import get_mimir_chroma_dir as _path

    return _path()


class LocalSentenceTransformerEmbeddingFunction:
    """Chroma-compatible embedding function backed by a local sentence-transformers
    model (e.g. /home/rayliu/models/bge-m3). Retrieval-optimized:
    max_seq_length=512 truncation, 16 threads, L2-normalized vectors (cosine).

    P0 (2026-08-11): real bge-m3 replaces the deterministic hash placeholder.
    """

    DEFAULT_MAX_SEQ_LENGTH = 512
    DEFAULT_NUM_THREADS = 16

    def __init__(
        self,
        model_path: str,
        max_seq_length: int = DEFAULT_MAX_SEQ_LENGTH,
        num_threads: int = DEFAULT_NUM_THREADS,
    ) -> None:
        self._model_path = model_path
        self._max_seq_length = max_seq_length
        try:
            import torch
            import sentence_transformers

            torch.set_num_threads(num_threads)
            self._model = sentence_transformers.SentenceTransformer(
                model_path, device="cpu"
            )
            self._model.max_seq_length = max_seq_length
        except Exception as exc:  # noqa: BLE001 - re-raise with context
            raise ImportError(
                f"local ST model {model_path} failed to load: {exc}"
            ) from exc

    def __call__(self, input: Sequence[str]) -> List[List[float]]:
        import numpy as np

        vecs = self._model.encode(
            list(input),
            normalize_embeddings=True,
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        if isinstance(vecs, np.ndarray):
            return [v.tolist() for v in vecs]
        return [v.tolist() for v in vecs]

    def embed_query(self, input: Sequence[str]) -> List[List[float]]:
        return self.__call__(input)

    def name(self) -> str:
        return "local_sentence_transformer"

    def get_config(self) -> Dict[str, Any]:
        return {
            "model_path": self._model_path,
            "max_seq_length": self._max_seq_length,
        }

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "LocalSentenceTransformerEmbeddingFunction":
        return LocalSentenceTransformerEmbeddingFunction(
            model_path=str(config.get("model_path", "")),
            max_seq_length=int(config.get("max_seq_length", LocalSentenceTransformerEmbeddingFunction.DEFAULT_MAX_SEQ_LENGTH)),
        )


def resolve_embedding_function(model: Optional[str] = None):
    """Pick embedding backend: local ST model (e.g. bge-m3) when configured, else
    chromadb ST by name, else deterministic hash (tier0 / no ML deps)."""
    model = (model or os.getenv("MIMIR_EMBED_MODEL", "")).strip()
    if model:
        # 1) local path on disk -> retrieval-optimized local embedding (P0: bge-m3)
        model_path = Path(model).expanduser()
        if model_path.is_dir():
            try:
                return LocalSentenceTransformerEmbeddingFunction(str(model_path))
            except Exception as exc:
                logger.warning(
                    "MIMIR_EMBED_MODEL=%s local load failed (%s); falling back to chromadb ST / hash",
                    model,
                    exc,
                )
        # 2) model name resolvable via chromadb sentence-transformers extras
        try:
            from chromadb.utils import embedding_functions

            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=model
            )
        except ImportError:
            logger.warning(
                "MIMIR_EMBED_MODEL=%s but sentence-transformers/chromadb extras "
                "unavailable; using hash embeddings",
                model,
            )
    return HashEmbeddingFunction()


# Garbage / non-retrieval content prefixes (P0 audit 2026-08-11: system error
# boilerplate and placeholder text was polluting the semantic index — e.g. 39x
# "抱歉,任务迭代次数已达上限" occupied HippoRAG2 query top-5 slots).
# NOTE: prefix match only — substring match would kill legitimate conversation
# that merely *mentions* these strings (e.g. a user asking what
# "[Old tool output cleared ...]" means).
_GARBAGE_PREFIXES: Tuple[str, ...] = (
    "抱歉,任务迭代次数已达上限",
    "抱歉,模型调用失败,请稍后重试",
    "(No response generated)",
    "[Old tool output cleared",
    "[CONTEXT COMPACTION",
)


def is_garbage_content(content: Optional[str]) -> bool:
    """True when content has no retrieval value (system errors / placeholders).

    Conservative prefix rules: never substring-match, so real conversation that
    quotes a placeholder stays indexable.
    """
    stripped = (content or "").strip()
    if not stripped:
        return True
    return stripped.startswith(_GARBAGE_PREFIXES)


def iter_indexable_messages(db_path: Path) -> Iterator[IndexedMessage]:
    """Yield searchable rows from sessions_search.db (garbage-filtered)."""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            """
            SELECT m.id, m.session_id, m.role, m.content, m.tool_name, m.timestamp,
                   COALESCE(s.source, 'unknown')
            FROM messages m
            LEFT JOIN sessions s ON m.session_id = s.session_id
            WHERE m.content IS NOT NULL AND TRIM(m.content) != ''
            ORDER BY m.id
            """
        )
        for row in cursor:
            message_id, session_id, role, content, tool_name, timestamp, source = row
            if is_garbage_content(content):
                continue
            yield IndexedMessage(
                message_id=int(message_id),
                session_id=str(session_id),
                role=str(role or "unknown"),
                content=str(content),
                source=str(source or "unknown"),
                timestamp=float(timestamp or 0.0),
                tool_name=str(tool_name) if tool_name else None,
            )
    finally:
        conn.close()


def _message_metadata(msg: IndexedMessage) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "session_id": msg.session_id,
        "message_id": msg.message_id,
        "role": msg.role,
        "source": msg.source,
        "timestamp": msg.timestamp,
    }
    if msg.tool_name:
        meta["tool_name"] = msg.tool_name
    return meta


def _upsert_batch(collection: Any, batch: Sequence[IndexedMessage]) -> int:
    ids = [message_doc_id(m.session_id, m.message_id) for m in batch]
    documents = [m.content for m in batch]
    metadatas = [_message_metadata(m) for m in batch]
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(batch)


def get_chroma_collection(
    chroma_dir: Optional[Path] = None,
    *,
    embedding_function: Any = None,
):
    """Open or create the session_messages collection."""
    if not chroma_available():
        raise ImportError(
            "chromadb is not installed; pip install chromadb to use semantic index"
        )
    import chromadb

    root = chroma_dir or get_mimir_chroma_dir()
    root.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(root))
    ef = embedding_function if embedding_function is not None else resolve_embedding_function()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def chroma_incremental_enabled() -> bool:
    """Gateway/indexer incremental upsert when chromadb is available (IQ-EVO-11)."""
    if not chroma_available():
        return False
    return os.environ.get("MIMIR_CHROMA_INCREMENTAL", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


_cached_chroma_collection: Any = None


def _get_incremental_collection() -> Any:
    global _cached_chroma_collection
    if _cached_chroma_collection is None:
        _cached_chroma_collection = get_chroma_collection()
    return _cached_chroma_collection


def reset_chroma_collection_cache() -> None:
    """Test helper: drop lazy collection cache."""
    global _cached_chroma_collection
    _cached_chroma_collection = None


def upsert_indexed_messages(
    messages: Sequence[IndexedMessage],
    *,
    collection: Any = None,
) -> int:
    """Upsert one or more messages into Chroma (idempotent by doc id)."""
    if not messages:
        return 0
    if collection is None:
        collection = _get_incremental_collection()
    batch_size = DEFAULT_BATCH_SIZE
    indexed = 0
    batch: List[IndexedMessage] = []
    for msg in messages:
        batch.append(msg)
        if len(batch) >= batch_size:
            indexed += _upsert_batch(collection, batch)
            batch = []
    if batch:
        indexed += _upsert_batch(collection, batch)
    return indexed


def sync_message_to_chroma(msg: IndexedMessage) -> bool:
    """Incremental upsert for a single message row (fail-open).

    Garbage guard (P0 audit 2026-08-11): incremental path bypasses
    iter_indexable_messages() filtering, so system-error boilerplate would
    re-pollute the index after backfill purge. Skip garbage at the entry.
    """
    if not chroma_incremental_enabled():
        return False
    if is_garbage_content(msg.content):
        return False
    try:
        upsert_indexed_messages([msg])
        return True
    except Exception as exc:
        logger.debug("chroma incremental upsert failed: %s", exc)
        return False


def delete_session_chroma_documents(session_id: str, *, collection: Any = None) -> None:
    """Remove all Chroma docs for a session (before full re-sync)."""
    if not chroma_available():
        return
    if collection is None:
        collection = _get_incremental_collection()
    try:
        collection.delete(where={"session_id": session_id})
    except Exception as exc:
        logger.debug("chroma delete session %s failed: %s", session_id, exc)


def sync_session_chroma_from_db(
    session_id: str,
    like_db_path: Path | str,
    *,
    replace_existing: bool = True,
) -> int:
    """Re-sync one session from sessions_search.db into Chroma."""
    if not chroma_incremental_enabled():
        return 0
    like_db_path = Path(like_db_path)
    if not like_db_path.is_file():
        return 0
    try:
        collection = _get_incremental_collection()
        if replace_existing:
            delete_session_chroma_documents(session_id, collection=collection)
        batch: List[IndexedMessage] = []
        count = 0
        for msg in iter_indexable_messages(like_db_path):
            if msg.session_id != session_id:
                continue
            batch.append(msg)
            if len(batch) >= DEFAULT_BATCH_SIZE:
                count += upsert_indexed_messages(batch, collection=collection)
                batch = []
        if batch:
            count += upsert_indexed_messages(batch, collection=collection)
        return count
    except Exception as exc:
        logger.debug("chroma session sync failed %s: %s", session_id, exc)
        return 0


def backfill_chroma_sessions(
    like_db_path: Path | str,
    *,
    chroma_dir: Optional[Path] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    collection: Any = None,
) -> ChromaBackfillStats:
    """Index sessions_search.db rows into Chroma (idempotent upsert)."""
    like_db_path = Path(like_db_path)
    stats = ChromaBackfillStats()
    if not like_db_path.is_file():
        logger.warning("sessions_search.db missing: %s", like_db_path)
        return stats

    if collection is None:
        collection = get_chroma_collection(chroma_dir)

    batch: List[IndexedMessage] = []
    for msg in iter_indexable_messages(like_db_path):
        batch.append(msg)
        if len(batch) >= batch_size:
            stats.messages_indexed += _upsert_batch(collection, batch)
            stats.batches += 1
            batch = []

    if batch:
        stats.messages_indexed += _upsert_batch(collection, batch)
        stats.batches += 1

    return stats


def query_session_messages(
    query: str,
    *,
    limit: int = 5,
    chroma_dir: Optional[Path] = None,
    collection: Any = None,
) -> List[Dict[str, Any]]:
    """Semantic query against session_messages (requires chromadb index)."""
    if collection is None:
        collection = get_chroma_collection(chroma_dir)
    result = collection.query(query_texts=[query], n_results=limit)
    hits: List[Dict[str, Any]] = []
    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    for doc_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
        hits.append(
            {
                "id": doc_id,
                "content": doc,
                "metadata": meta or {},
                "distance": dist,
            }
        )
    return hits
