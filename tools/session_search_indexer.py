"""Backfill session_search.db and optional fts5_search.db from gateway JSONL transcripts."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

logger = logging.getLogger(__name__)

_SKIP_ROLES = frozenset({"session_meta"})


def _parse_timestamp(raw: Any) -> float:
    if raw is None:
        return datetime.now().timestamp()
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return datetime.now().timestamp()


def extract_searchable_message(record: Dict[str, Any]) -> Optional[Tuple[str, str, Optional[str], float]]:
    """Return (role, content, tool_name, timestamp) or None if not indexable."""
    role = record.get("role")
    if not role or role in _SKIP_ROLES:
        return None
    content = record.get("content") or record.get("text") or ""
    if not isinstance(content, str):
        return None
    content = content.strip()
    if not content:
        tool_calls = record.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            names = []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    name = tc.get("name") or (tc.get("function") or {}).get("name")
                    if name:
                        names.append(str(name))
            if names:
                content = f"[Called: {', '.join(names)}]"
        if not content:
            return None
    tool_name = record.get("tool_name") or record.get("name")
    if tool_name is not None:
        tool_name = str(tool_name)
    return str(role), content, tool_name, _parse_timestamp(record.get("timestamp"))


def load_sessions_index(sessions_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load gateway sessions.json mapping session_id -> metadata."""
    index_path = sessions_dir / "sessions.json"
    if not index_path.exists():
        return {}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", index_path, exc)
        return {}
    if not isinstance(data, dict):
        return {}
    by_id: Dict[str, Dict[str, Any]] = {}
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        sid = entry.get("session_id")
        if sid:
            by_id[str(sid)] = entry
    return by_id


def iter_transcript_messages(path: Path) -> Iterator[Tuple[int, Dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError:
                logger.debug("Skip invalid JSON in %s:%s", path, line_no)


@dataclass
class BackfillStats:
    sessions: int = 0
    messages: int = 0
    skipped_files: int = 0
    fts_messages: int = 0
    # ── RS20（§29 Q16 · 2026-09-14）幂等口径 ────────────────────────────────
    fts_duplicates_skipped: int = 0   # 被唯一约束挡下的重复插入
    fts_rows: int = 0                 # 回填后库内行数
    fts_distinct_pairs: int = 0       # distinct(session_id, content_hash)
    fts_ratio: float = 1.0            # rows / distinct_pairs（>1 = 非幂等）


def clear_like_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        conn.commit()
    finally:
        conn.close()


def backfill_sessions(
    sessions_dir: Path,
    *,
    like_db_path: Optional[Path],
    fts_db_path: Optional[Path] = None,
    fresh: bool = False,
) -> BackfillStats:
    """Index all *.jsonl transcripts under sessions_dir into search DB(s).

    ``like_db_path=None`` → **只回填 FTS5，完全跳过 like 库**（档2-③ 2026-09-11）。
    必要性：like 库由 gateway 增量维护（已是全量），重复回填会重复插入消息；
    而 FTS5 只能手工回填（gateway 增量路径不写 FTS——见 gateway/session.py
    `_append_to_sessions_search_index`），故需要"仅 FTS"模式。
    """
    from tools.session_search_tool import SessionSearchDB

    stats = BackfillStats()
    if not sessions_dir.is_dir():
        logger.warning("Sessions dir missing: %s", sessions_dir)
        return stats

    like_db = None
    if like_db_path is not None:
        like_db_path.parent.mkdir(parents=True, exist_ok=True)
        if fresh and like_db_path.exists():
            clear_like_db(like_db_path)
        like_db = SessionSearchDB(str(like_db_path))

    fts_engine = None
    if fts_db_path is not None:
        if fresh and fts_db_path.exists():
            fts_db_path.unlink(missing_ok=True)
        elif like_db is None:
            logger.info("FTS-only backfill: appending into existing %s", fts_db_path)
        from tools.fts5_search.engine import FTS5SearchEngine

        fts_engine = FTS5SearchEngine(str(fts_db_path))

    index = load_sessions_index(sessions_dir)

    for path in sorted(sessions_dir.glob("*.jsonl")):
        session_id = path.stem
        meta = index.get(session_id, {})
        source = str(meta.get("platform") or meta.get("source") or "unknown")
        title = str(meta.get("display_name") or meta.get("title") or session_id)
        msg_count = 0

        if like_db is not None:
            like_db.add_session(session_id, source=source, title=title)

        for _line_no, record in iter_transcript_messages(path):
            parsed = extract_searchable_message(record)
            if parsed is None:
                continue
            role, content, tool_name, _ts = parsed
            if like_db is not None:
                like_db.add_message(session_id, role, content, tool_name=tool_name)
            msg_count += 1
            if fts_engine is not None:
                # RS20：① 传 **transcript 真时间**（不再用 now()）——重跑得到同一行；
                #       ② index_message 返回 0 = 命中去重，记数但不谎报"已索引"
                inserted = fts_engine.index_message(
                    session_id,
                    role,
                    content,
                    metadata={"source": source, "title": title},
                    created_at=_ts,
                )
                if inserted > 0:
                    stats.fts_messages += 1
                elif inserted == 0:
                    stats.fts_duplicates_skipped += 1

        if msg_count:
            stats.sessions += 1
            stats.messages += msg_count
        else:
            stats.skipped_files += 1

    if fts_engine is not None:
        # RS20：写完立刻自检 "批写入行数 vs distinct hash"。不是事后再跑一个脚本
        # ——写路径自己报出非幂等（与本轮 RS17「让重复自己暴露」同族）。
        try:
            from tools.fts5_search.integrity import check_fts_integrity

            report = check_fts_integrity(fts_db_path)
            checks = report.get("checks") or {}
            stats.fts_rows = int(checks.get("rows", 0) or 0)
            stats.fts_distinct_pairs = int(checks.get("distinct_pairs", 0) or 0)
            ratio = checks.get("ratio")
            stats.fts_ratio = float(ratio) if isinstance(ratio, (int, float)) else 1.0
            if report.get("verdict") != "PASS":
                logger.warning(
                    "FTS 幂等自检 FAIL：rows=%s distinct=%s ratio=%s failures=%s",
                    stats.fts_rows, stats.fts_distinct_pairs, ratio,
                    report.get("failures"),
                )
            else:
                logger.info(
                    "FTS 幂等自检 PASS：rows=%s distinct=%s ratio=1.0 dup_skipped=%s",
                    stats.fts_rows, stats.fts_distinct_pairs,
                    stats.fts_duplicates_skipped,
                )
        except Exception as exc:  # 自检不得让回填失败
            logger.warning("FTS 幂等自检异常（回填结果仍有效）：%s", exc)
        fts_engine.close()

    return stats


def index_transcript_message(
    session_id: str,
    message: Dict[str, Any],
    *,
    like_db: Any,
    source: str = "unknown",
    title: str = "",
    ensure_session: bool = True,
) -> bool:
    """Append one JSONL transcript row to sessions_search.db. Returns True if indexed."""
    parsed = extract_searchable_message(message)
    if parsed is None:
        return False
    role, content, tool_name, _ts = parsed
    if ensure_session:
        like_db.add_session(session_id, source=source, title=title)
    message_id = like_db.add_message(session_id, role, content, tool_name=tool_name)
    if message_id > 0:
        try:
            from tools.chroma_session_indexer import IndexedMessage, sync_message_to_chroma

            sync_message_to_chroma(
                IndexedMessage(
                    message_id=message_id,
                    session_id=session_id,
                    role=role,
                    content=content,
                    source=source,
                    timestamp=_ts,
                    tool_name=tool_name,
                )
            )
        except Exception as exc:
            from tools.chroma_session_indexer import note_index_failure

            note_index_failure("incremental_hook", exc, sink="session_search_indexer")
    return True


# --- 增量水位 + 断点续传（2026-10-06 · 治「清空重建 + 30s 截断」） --------------
#
# 事故（P0 诊断 2026-10-05）：卫生压缩对某会话「先清空本会话行、再逐条重嵌」，
# 2908 条在 30s 上限内只做完 258 条 ⇒ 索引只剩块头 9%，且三处 fail-open 只记 debug。
# 对策：① 水位——前缀未变就不重做前缀（只补尾部）② 续传——没做完的会话落 pending
# 标记，resume 只补「SQLite 有、chroma 没有」的那部分，不从零重嵌。
_WATERMARK_ENV = "MIMIR_INDEX_WATERMARK_PATH"
_PENDING_ENV = "MIMIR_INDEX_PENDING_PATH"


def _state_path(env_key: str, filename: str) -> Path:
    import os

    raw = (os.environ.get(env_key) or "").strip()
    if raw:
        return Path(raw)
    from mimir_constants import get_mimir_home

    return Path(get_mimir_home()) / "data" / filename


def _watermark_path() -> Path:
    return _state_path(_WATERMARK_ENV, "index_watermark.json")


def _pending_path() -> Path:
    return _state_path(_PENDING_ENV, "index_pending.json")


def _load_state(path: Path) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(path: Path, data: Dict[str, Any]) -> None:
    import os

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as exc:
        logger.warning("index state write failed (%s): %s", path, exc)


def messages_digest(messages, upto: Optional[int] = None) -> str:
    """Stable digest of the first ``upto`` messages.

    Only role/content/tool_name enter the digest: ``extract_searchable_message``
    stamps a *now* timestamp when the record has none, so hashing its full
    output would make the digest time-dependent (and the watermark useless).
    """
    import hashlib

    h = hashlib.sha256()
    seq = messages if upto is None else list(messages)[:upto]
    for m in seq:
        parsed = extract_searchable_message(m) if isinstance(m, dict) else None
        key = (parsed[0], parsed[1], parsed[2]) if parsed else None
        h.update(repr(key).encode("utf-8", "replace"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def watermark_prefix_len(session_id: str, messages) -> int:
    """Leading messages already indexed (0 = prefix changed / unknown)."""
    rec = (_load_state(_watermark_path()).get(session_id) or {})
    n = int(rec.get("n") or 0)
    if n <= 0 or n > len(messages):
        return 0
    if messages_digest(messages, n) != rec.get("digest"):
        return 0
    return n


def record_watermark(session_id: str, messages, indexed_n: Optional[int] = None) -> None:
    n = len(messages) if indexed_n is None else int(indexed_n)
    data = _load_state(_watermark_path())
    data[session_id] = {"n": n, "digest": messages_digest(messages, n), "ts": _now_ts()}
    _save_state(_watermark_path(), data)


def _now_ts() -> float:
    return datetime.now().timestamp()


def record_pending(session_id: str, total: int, *, source: str = "", title: str = "") -> None:
    """Mark a session as mid-flight BEFORE the expensive work (crash-safe)."""
    data = _load_state(_pending_path())
    data[session_id] = {"total": int(total), "source": source, "title": title, "ts": _now_ts()}
    _save_state(_pending_path(), data)


def clear_pending(session_id: str) -> None:
    data = _load_state(_pending_path())
    if session_id in data:
        data.pop(session_id, None)
        _save_state(_pending_path(), data)


def pending_index_report() -> Dict[str, Any]:
    return _load_state(_pending_path())



def resume_session_index(session_id: str, *, like_db: Any, batch_size: int = 128) -> Dict[str, Any]:
    """断点续传：只补「SQLite 有、chroma 缺」的行，不重嵌已就位部分。

    用于 30s 上限把某会话索引截断后的收尾（P0 诊断 2026-10-05）。
    """
    out: Dict[str, Any] = {"session_id": session_id}
    db_path = getattr(like_db, "db_path", None)
    if not db_path:
        out["error"] = "like_db has no db_path"
        return out
    from tools.chroma_session_indexer import (
        IndexedMessage,
        get_chroma_collection,
        message_doc_id,
        upsert_indexed_messages,
    )

    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT id, role, content, tool_name, timestamp FROM messages "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    finally:
        con.close()
    out["indexed_rows"] = len(rows)

    col = get_chroma_collection()
    have, off = set(), 0
    while True:
        got = col.get(where={"session_id": session_id}, include=[], limit=1000, offset=off).get("ids") or []
        if not got:
            break
        have |= set(got)
        off += len(got)
        if len(got) < 1000:
            break
    out["chroma_docs"] = len(have)

    missing = [r for r in rows if message_doc_id(session_id, int(r[0])) not in have]
    out["filled"] = 0
    for i in range(0, len(missing), batch_size):
        chunk = missing[i:i + batch_size]
        batch = [
            IndexedMessage(
                message_id=int(r[0]), session_id=session_id, role=str(r[1] or "unknown"),
                content=str(r[2] or ""), source="resume", timestamp=float(r[3] or 0.0),
                tool_name=str(r[4]) if r[4] else None,
            )
            for r in chunk
        ]
        out["filled"] += upsert_indexed_messages(batch, collection=col)
    return out


def resume_pending_indexes(*, like_db: Any = None, limit: Optional[int] = None) -> Dict[str, Any]:
    """续传所有 pending 会话（崩溃/超时留下的半成品）。"""
    pending = _load_state(_pending_path())
    done: Dict[str, Any] = {}
    for sid in list(pending)[: limit if limit else None]:
        try:
            done[sid] = resume_session_index(sid, like_db=like_db)
            clear_pending(sid)
        except Exception as exc:
            from tools.chroma_session_indexer import note_index_failure

            note_index_failure("resume_pending", exc, sink="session_search_indexer")
            done[sid] = {"error": f"{type(exc).__name__}: {exc}"}
    return {"pending_seen": len(pending), "resumed": done}

def reindex_session_transcript(
    session_id: str,
    messages: list,
    *,
    like_db: Any,
    source: str = "unknown",
    title: str = "",
    incremental: bool = True,
) -> int:
    """Replace search index rows for a session (e.g. after rewrite_transcript).

    Incremental (2026-10-06): when the stored watermark proves the leading ``n``
    messages are unchanged, those rows are kept and only the tail is re-indexed.
    A hygiene compression used to clear + re-embed the whole session, which the
    30s off-loop budget truncated (P0 diagnosis 2026-10-05, S8-2).
    """
    keep = watermark_prefix_len(session_id, messages) if incremental else 0
    clear = getattr(like_db, "clear_session_messages", None)
    if callable(clear):
        try:
            clear(session_id, keep_first=keep)
        except TypeError:
            clear(session_id)  # legacy store without keep_first
            keep = 0
    like_db.add_session(session_id, source=source, title=title)
    record_pending(session_id, len(messages), source=source, title=title)
    count = 0
    for message in messages[keep:]:
        if index_transcript_message(
            session_id,
            message,
            like_db=like_db,
            source=source,
            title=title,
            ensure_session=False,
        ):
            count += 1
    if keep == 0:
        try:
            from tools.chroma_session_indexer import sync_session_chroma_from_db

            db_path = getattr(like_db, "db_path", None)
            if db_path:
                sync_session_chroma_from_db(session_id, db_path)
        except Exception as exc:
            from tools.chroma_session_indexer import note_index_failure

            note_index_failure("session_resync_hook", exc, sink="session_search_indexer")
    record_watermark(session_id, messages)
    clear_pending(session_id)
    return count
