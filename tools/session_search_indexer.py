"""Backfill session_search.db and optional fts5_search.db from gateway JSONL transcripts."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
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
    seq: Optional[int] = None,
) -> bool:
    """Append one JSONL transcript row to sessions_search.db. Returns True if indexed.

    ``seq`` 显式给出时交给 ``add_message`` 做 UNIQUE 去重（重放幂等，2026-10-20 P0-b）；
    返回 False 表示「已存在、未插入」。
    """
    parsed = extract_searchable_message(message)
    if parsed is None:
        return False
    role, content, tool_name, _ts = parsed
    if ensure_session:
        like_db.add_session(session_id, source=source, title=title)
    message_id = like_db.add_message(
        session_id, role, content, tool_name=tool_name, seq=seq
    )
    if seq is not None and message_id <= 0:
        return False
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
    if n <= 0:
        return 0
    if n <= len(messages) and messages_digest(messages, n) == rec.get("digest"):
        return n
    # F4(2026-10-19): 压缩会让消息数**变短**(实测 1753 -> 94)；旧实现 n > len
    # 直接 return 0 => 该会话永远全量 resync(每次 30s 超时 + 全量重嵌，水位永不动)。
    # 阶梯回退：取仍能匹配上的最大前缀(marks 只含记录时内容，新内容不会假匹配)。
    marks = rec.get("marks") or {}
    for L in sorted((int(k) for k in marks if str(k).isdigit()), reverse=True):
        if 0 < L <= len(messages) and messages_digest(messages, L) == marks.get(str(L)):
            return L
    return 0


_WATERMARK_LADDER = (8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384)


def _watermark_ladder(n: int) -> list:
    """前缀长度阶梯（<= n）：压缩后消息变短时，靠它回退到仍匹配的最大前缀。"""
    out = [L for L in _WATERMARK_LADDER if L <= n]
    if n > 0 and (not out or out[-1] != n):
        out.append(n)
    return out


# --- S3(2026-10-19): 全局三键 n/digest/ts 并进同一份 index_watermark.json -----------
# 契约：**不新建状态文件**——全局读数与会话级记录同住 data/index_watermark.json。
#   n      = 各会话已索引条数之和（增量口径，≠ 文件行数）
#   digest = 各会话 (sid:n:digest) 排序后的 rollup 摘要
#   ts     = 本次更新时刻
_GLOBAL_KEYS = ("n", "digest", "ts")


def _session_records(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """会话级记录（剔除全局三键与非 dict 值，供 rollup 与审计器共用）。"""
    return {k: v for k, v in data.items() if k not in _GLOBAL_KEYS and isinstance(v, dict)}


def merge_global_watermark(data: Dict[str, Any]) -> Dict[str, Any]:
    """就地写入全局三键（幂等 · 不触碰会话级记录）。"""
    import hashlib

    recs = _session_records(data)
    total = sum(int((r or {}).get("n") or 0) for r in recs.values())
    h = hashlib.sha256()
    for sid in sorted(recs):
        r = recs[sid] or {}
        h.update(f"{sid}:{int(r.get('n') or 0)}:{r.get('digest')}".encode("utf-8", "replace"))
        h.update(b"\x00")
    data["n"] = total
    data["digest"] = h.hexdigest()[:32]
    data["ts"] = _now_ts()
    return data


def refresh_global_watermark() -> Dict[str, Any]:
    """回填/修复全局三键（幂等）——一次性迁移与巡检入口；不动 chroma、不碰会话记录。"""
    data = _load_state(_watermark_path())
    merge_global_watermark(data)
    _save_state(_watermark_path(), data)
    return {k: data[k] for k in _GLOBAL_KEYS}


def record_watermark(session_id: str, messages, indexed_n: Optional[int] = None) -> None:
    n = len(messages) if indexed_n is None else int(indexed_n)
    data = _load_state(_watermark_path())
    data[session_id] = {
        "n": n,
        "digest": messages_digest(messages, n),
        "ts": _now_ts(),
        # F4(2026-10-19): 同时记阶梯摘要，供压缩后（消息变短）回退匹配。
        "marks": {str(L): messages_digest(messages, L) for L in _watermark_ladder(n)},
    }
    merge_global_watermark(data)
    _save_state(_watermark_path(), data)


def _now_ts() -> float:
    return datetime.now().timestamp()


def record_pending(
    session_id: str,
    total: int,
    *,
    source: str = "",
    title: str = "",
    actual: Optional[int] = None,
    chroma_docs: Optional[int] = None,
    reason: Optional[str] = None,
) -> None:
    """Mark a session as mid-flight BEFORE the expensive work (crash-safe).

    F7(2026-10-19): ``total`` 是**压缩前**的快照，压缩后必然大于源库实际行数
    （实测 pending.total=1952 / 实际 475）——单靠它，记录无法被复算。故额外记
    ``actual``（读回时源库真实行数）+ ``chroma_docs`` + ``reason``。
    """
    data = _load_state(_pending_path())
    rec = {"total": int(total), "source": source, "title": title, "ts": _now_ts()}
    if actual is not None:
        rec["actual"] = int(actual)
    if chroma_docs is not None:
        rec["chroma_docs"] = int(chroma_docs)
    if reason is not None:
        rec["reason"] = str(reason)
    data[session_id] = rec
    _save_state(_pending_path(), data)


def clear_pending(session_id: str) -> None:
    data = _load_state(_pending_path())
    if session_id in data:
        data.pop(session_id, None)
        _save_state(_pending_path(), data)


def _pending_clear_decision(*, wanted: int, chroma_docs: int) -> Tuple[bool, str]:
    """「补完了吗」的唯一裁决点（纯函数 · 可两向测）。

    F7(2026-10-19)：旧实现在 resume 之后**无条件** ``clear_pending()``，于是
    「清空 pending」被当成「补完了」的同义词。盘上实证：03:10:04 该文件从
    ``{"20261019_022057_9dc448fa": {"total": 1952}}`` 清成 ``{}``，而同一时刻
    该会话 chroma 约 249 条、源库 475 行——缺口一条没填，记录却消失了。

    判据是**读回**（chroma 实有 doc 数 vs 源库实际行数），不是自报进度；
    ``wanted <= 0`` ⇒ 源库该会话已无行（被压缩删掉），无事可补 ⇒ 允许清。
    """
    if int(wanted) <= 0:
        return True, "empty_session"
    if int(chroma_docs) >= int(wanted):
        return True, "complete"
    return False, "incomplete"


def _count_session_docs(session_id: str, *, collection: Any = None) -> Optional[int]:
    """读回本会话在 chroma 的 doc 数；失败/不可用返回 ``None``（**不许**当 0）。"""
    try:
        import tools.chroma_session_indexer as _csi

        col = collection
        if col is None:
            factory = getattr(_csi, "_get_incremental_collection", None) or _csi.get_chroma_collection
            col = factory()
        have, offset = 0, 0
        while True:
            got = col.get(
                where={"session_id": session_id}, include=[], limit=1000, offset=offset
            ).get("ids") or []
            if not got:
                break
            have += len(got)
            offset += len(got)
            if len(got) < 1000:
                break
        return have
    except Exception as exc:  # pragma: no cover - 依赖真 chroma
        from tools.chroma_session_indexer import note_index_failure

        note_index_failure("pending_clear_verify", exc, sink="session_search_indexer")
        return None


def pending_index_report() -> Dict[str, Any]:
    return _load_state(_pending_path())

# --- F2 (2026-10-19)：删侧 pending ——「删除即记账，续传才动 chroma」 -------------
#
# 事故（M6 审计实测）：源库删除点共 4 处——``mimir_state.py:981 delete_session()`` /
# ``:1015 prune_sessions()`` / ``tools/session_search_tool.py:390``（清会话消息）/
# 本文件 ``:112``（回填全清）——全部**只删 SQLite，chroma 一行不动**。而现成的
# ``chroma_session_indexer.delete_session_chroma_documents`` 与
# ``prune_session_chroma_orphans`` 在生产调用图里 **0 个调用者**（只有 def 与测试）。
# => 「删了还在」= 脏召回（召回到源库已不存在的消息）。
#
# 为什么不在删除点直接删 chroma：删除发生在 CLI / web_server / acp_adapter 进程里，
# 那条路径不加载 embedding，也不该因为 chroma 慢/坏而卡住删除。故只落一条
# **pending 记录**（毫秒级、失败不影响删除），chroma 删除交给 resume 在后台做。
#
# 表结构（JSON 文件 ``data/index_pending_deletes.json``；不新建 SQLite 表——源库与
# 索引库是两个进程共用的件，加表要迁移，加一个 JSON 路径不用）：
#   {
#     "<session_id>": {
#       "kind": "delete",            # 固定；防止与 index_pending.json 混读
#       "reason": "session_deleted|session_pruned|messages_cleared|orphan_scan",
#       "doc_count": 123,            # 记账时该会话在 chroma 的 doc 数（可选）
#       "ts": 1760000000.0,          # 记账时刻
#       "attempts": 0,               # 已尝试轮数；>=3 留人工，不无限重试
#       "last_error": ""             # 最近失败语义（成功即清空）
#     }
#   }
_PENDING_DELETES_ENV = "MIMIR_INDEX_PENDING_DELETES_PATH"
_FAILED_BACKLOG = 3


def _pending_deletes_path() -> Path:
    return _state_path(_PENDING_DELETES_ENV, "index_pending_deletes.json")


def record_pending_delete(
    session_id: str,
    *,
    reason: str = "",
    doc_count: Optional[int] = None,
) -> bool:
    """记账「该会话要删 chroma」（毫秒级 · 幂等 · 不抛）。

    F2 契约：删除方只负责记账，**不**在删除路径上动 chroma；补删由
    ``resume_pending_deletes`` 做。返回是否写成功（失败也不影响调用方删除）。
    """
    if not session_id:
        return False
    try:
        data = _load_state(_pending_deletes_path())
        rec = data.get(session_id) or {}
        rec["kind"] = "delete"
        if reason:
            rec["reason"] = str(reason)
        if doc_count is not None:
            rec["doc_count"] = int(doc_count)
        rec["ts"] = _now_ts()
        rec.setdefault("attempts", 0)
        data[session_id] = rec
        _save_state(_pending_deletes_path(), data)
        return True
    except Exception as exc:  # pragma: no cover - 记账失败不得拖垮删除
        logger.warning("record_pending_delete(%s) failed: %s", session_id, exc)
        return False


def pending_delete_report() -> Dict[str, Any]:
    return _load_state(_pending_deletes_path())


def resume_pending_deletes(
    *,
    collection: Any = None,
    batch: int = 1000,
    pause_s: float = 0.0,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """消费删侧 pending：分批删 chroma + **读回验证**（不是自报删完）。

    F7 同源纪律：清记录 != 做完了。只有「读回该会话 doc 数 == 0」才清账；
    读回不可用（chroma 坏）时**不许**当 0——记账保留、attempts+1，留给坏库降级
    与人工。``attempts >= _FAILED_BACKLOG`` 的记账不再自动重试。
    """
    path = _pending_deletes_path()
    data = _load_state(path)
    out: Dict[str, Any] = {
        "pending_seen": len(data),
        "deleted_sessions": 0,
        "docs_deleted": 0,
        "kept": 0,
        "errors": 0,
        "skipped_backlog": 0,
    }
    if not data:
        return out
    col = collection
    if col is None:
        try:
            import tools.chroma_session_indexer as _csi

            factory = getattr(_csi, "_get_incremental_collection", None) or _csi.get_chroma_collection
            col = factory()
        except Exception as exc:
            try:
                from tools.chroma_session_indexer import note_index_failure

                note_index_failure("pending_delete_open", exc, sink="session_search_indexer")
            except Exception:  # pragma: no cover
                pass
            out["error"] = "%s: %s" % (type(exc).__name__, exc)
            return out
    import tools.chroma_session_indexer as _csi
    for sid in list(data)[: limit if limit else None]:
        rec = data.get(sid) or {}
        if int(rec.get("attempts") or 0) >= _FAILED_BACKLOG:
            out["skipped_backlog"] += 1
            continue
        try:
            while True:
                got = col.get(
                    where={"session_id": sid}, include=[], limit=batch, offset=0
                ).get("ids") or []
                if not got:
                    break
                with _csi.chroma_write_lock():
                    col.delete(ids=got)
                out["docs_deleted"] += len(got)
                if pause_s:
                    import time as _time

                    _time.sleep(float(pause_s))
                if len(got) < batch:
                    break
            left = _count_session_docs(sid, collection=col)
            if left is None:  # 读回不可用 => 不清账（同 F7）
                rec["attempts"] = int(rec.get("attempts") or 0) + 1
                rec["last_error"] = "verify_unavailable"
                data[sid] = rec
                out["errors"] += 1
                continue
            if int(left) == 0:
                data.pop(sid, None)
                out["deleted_sessions"] += 1
            else:
                rec["attempts"] = int(rec.get("attempts") or 0) + 1
                rec["last_error"] = "residual=%d" % int(left)
                data[sid] = rec
                out["kept"] += 1
        except Exception as exc:
            rec["attempts"] = int(rec.get("attempts") or 0) + 1
            rec["last_error"] = "%s: %s" % (type(exc).__name__, exc)
            data[sid] = rec
            out["errors"] += 1
            try:
                from tools.chroma_session_indexer import note_index_failure

                note_index_failure("pending_delete", exc, sink="session_search_indexer")
            except Exception:  # pragma: no cover
                pass
    _save_state(path, data)
    return out


def _source_session_ids(db_path: Any) -> set:
    """源库出现过的 session_id（只读连接）。"""
    import sqlite3

    conn = sqlite3.connect("file:%s?mode=ro" % (db_path,), uri=True)
    try:
        return {row[0] for row in conn.execute("SELECT DISTINCT session_id FROM messages")}
    finally:
        conn.close()


def scan_orphan_sessions(
    *,
    collection: Any = None,
    db_path: Any = None,
    record: bool = True,
    batch: int = 1000,
) -> Dict[str, Any]:
    """差集兜底：chroma 有、源库没有的会话 => 记 pending delete。

    这是 F2 的第 ③ 条：不指望每条删除路径都记得记账，靠一次差集把漏网的捞回来。
    **只读扫描 + 只写记账**——绝不在这里删 chroma（删除唯一出口是
    ``resume_pending_deletes``，便于审计与分批）。
    """
    out: Dict[str, Any] = {"chroma_sessions": 0, "source_sessions": 0, "orphans": 0, "recorded": 0}
    if db_path is None:
        from mimir_constants import get_mimir_session_search_db_path

        db_path = get_mimir_session_search_db_path()
    col = collection
    if col is None:
        try:
            import tools.chroma_session_indexer as _csi

            factory = getattr(_csi, "_get_incremental_collection", None) or _csi.get_chroma_collection
            col = factory()
        except Exception as exc:
            out["error"] = "%s: %s" % (type(exc).__name__, exc)
            return out
    chroma_sids, offset = set(), 0
    while True:
        got = col.get(include=["metadatas"], limit=batch, offset=offset).get("metadatas") or []
        if not got:
            break
        for meta in got:
            sid = (meta or {}).get("session_id")
            if sid:
                chroma_sids.add(sid)
        offset += len(got)
        if len(got) < batch:
            break
    src = _source_session_ids(db_path)
    orphans = sorted(chroma_sids - src)
    out.update({
        "chroma_sessions": len(chroma_sids),
        "source_sessions": len(src),
        "orphans": len(orphans),
        "orphan_sample": orphans[:10],
    })
    if record:
        for sid in orphans:
            if record_pending_delete(sid, reason="orphan_scan"):
                out["recorded"] += 1
    return out



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


def reconcile_session_orphans(
    session_id: str, db_path: Any, *, dry_run: bool = False, collection: Any = None
) -> Dict[str, Any]:
    """Scoped orphan reconcile for ONE session (no full-library scan).

    ``chroma_session_indexer.prune_session_chroma_orphans`` answers the same
    question but pays ``iter_indexable_messages()`` over the whole DB, so it is
    unusable on a hot path. This reads only this session's docs and rows -- which
    makes it safe to call from the pending-resume path (runs at gateway start)
    and from the monitor's whitelist self-heal.

    Reading dict: ``chroma_docs`` / ``wanted`` / ``orphans`` / ``deleted``
    (+``skipped``/``error``). Never raises.
    """
    out: Dict[str, Any] = {
        "session_id": session_id,
        "chroma_docs": 0,
        "wanted": 0,
        "orphans": 0,
        "deleted": 0,
    }
    if not db_path:
        out["skipped"] = "no_db_path"
        return out
    try:
        import tools.chroma_session_indexer as _csi
        from tools.chroma_session_indexer import message_doc_id

        if not _csi.chroma_incremental_enabled():
            # 配对不变量（与 prune 同口径）：增量写者关着就不清理。
            out["skipped"] = "incremental_off"
            return out
        col = collection
        if col is None:
            factory = getattr(_csi, "_get_incremental_collection", None) or _csi.get_chroma_collection
            col = factory()
        have, offset = set(), 0
        while True:
            got = col.get(
                where={"session_id": session_id}, include=[], limit=1000, offset=offset
            ).get("ids") or []
            if not got:
                break
            have |= set(got)
            offset += len(got)
            if len(got) < 1000:
                break
        con = sqlite3.connect(str(db_path))
        try:
            rows = con.execute(
                "SELECT id FROM messages WHERE session_id = ?", (session_id,)
            ).fetchall()
        finally:
            con.close()
        wanted = {message_doc_id(session_id, int(r[0])) for r in rows}
        stale = sorted(have - wanted)
        out["chroma_docs"] = len(have)
        out["wanted"] = len(wanted)
        out["orphans"] = len(stale)
        if stale and not dry_run:
            with _csi.chroma_write_lock():
                col.delete(ids=stale)
            out["deleted"] = len(stale)
    except Exception as exc:
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
    return out


def resume_pending_indexes(*, like_db: Any = None, limit: Optional[int] = None) -> Dict[str, Any]:
    """续传所有 pending 会话（崩溃/超时留下的半成品）。"""
    pending = _load_state(_pending_path())
    done: Dict[str, Any] = {}
    for sid in list(pending)[: limit if limit else None]:
        try:
            # 2026-10-18：恢复前先做一次**本会话范围**的孤儿对账。
            # 为什么在 resume 之前：pending = 「上次没写完」，而没写完的重写
            # 正是孤儿产地；先对账再续传，续传面对干净基线，也不会把上次
            # 被删行的残留 doc 留到「下次重写才清」（旧行为）。
            rec = reconcile_session_orphans(sid, getattr(like_db, "db_path", None))
            res = resume_session_index(sid, like_db=like_db)
            if rec.get("orphans") or rec.get("deleted") or rec.get("error") or rec.get("skipped"):
                res["reconcile"] = rec
            # F7(2026-10-19): 清空必须有校验（旧实现无条件 clear ⇒ 清空被当成补完）。
            wanted = int(res.get("indexed_rows") or 0)
            have = _count_session_docs(sid)
            if res.get("error") or have is None:
                ok, why = False, ("error" if res.get("error") else "unverified")
            else:
                ok, why = _pending_clear_decision(wanted=wanted, chroma_docs=have)
            if ok:
                clear_pending(sid)
            else:
                prev = pending.get(sid) or {}
                record_pending(
                    sid,
                    wanted,
                    source=str(prev.get("source") or ""),
                    title=str(prev.get("title") or ""),
                    actual=wanted,
                    chroma_docs=have,
                    reason=why,
                )
            res["pending_cleared"] = ok
            res["pending_reason"] = why
            done[sid] = res
        except Exception as exc:
            from tools.chroma_session_indexer import note_index_failure

            note_index_failure("resume_pending", exc, sink="session_search_indexer")
            done[sid] = {"error": f"{type(exc).__name__}: {exc}"}
    return {"pending_seen": len(pending), "resumed": done}

# ── 孤儿清理解耦（2026-10-18 · DBRE：large deletes need a blast-radius estimate）──
# 旧形态：清理挂在重写循环**之后**（跑完全部 re-embed 才 prune），且 prune 要
# `iter_indexable_messages()` **全库扫描**。后果：① 30s off-loop 预算一截断，
# 清理那步根本没机会跑（orphans 复发）；② 只删本会话几个 id 却按全库算。
# 新形态：clear **之前**点名将被删的 rowid → clear 之后**立刻**删对应 doc。
# 不依赖重写跑完、不依赖全库扫描；窗口从「整个重写」缩到「clear 前后两次调用」。

def _stale_docs_before_clear(session_id: str, db_path: Any, keep: int) -> Tuple[list, int]:
    """Point-name the docs that ``clear_session_messages(keep_first=keep)`` will strand.

    Runs **before** the clear: the rows it returns are exactly the ones the DELETE
    removes (``id NOT IN (first keep rows)`` == ``id > last-kept id``), so their
    ``{session}:{id}`` docs become orphans the moment the clear commits.

    Returns ``(doc_ids, ceiling)``. ``ceiling`` = highest rowid in this snapshot:
    ids above it were inserted *after* the read (concurrent compression) and are
    excluded on purpose, so a racing writer's fresh rows never enter the delete
    list. ``keep <= 0`` => names **every** current row of this session (clear deletes
    them all); returning ``([], 0)`` here is what leaked orphans before 2026-10-19.
    """
    if not db_path:
        return [], 0
    if keep <= 0:
        # F1(2026-10-19): clear_session_messages(keep_first=0) 删**全部**行，旧实现
        # 返回 ([],0) 交给全量 resync —— 而 resync 的 delete 异常被 except 吞掉
        # (只落一条 debug)，于是旧 doc 与新 doc 并存 = 孤儿无限累积。
        # 现在：先点名本快照内全部行（ceiling 挡住并发写者后插入的行），clear 后立刻删。
        con = sqlite3.connect(str(db_path))
        try:
            rows = con.execute(
                "SELECT id FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        finally:
            con.close()
        if not rows:
            return [], 0
        from tools.chroma_session_indexer import message_doc_id

        return [message_doc_id(session_id, int(r[0])) for r in rows], int(rows[-1][0])
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(
            "SELECT id FROM messages WHERE session_id = ? ORDER BY id LIMIT 1 OFFSET ?",
            (session_id, int(keep) - 1),
        ).fetchone()
        if not row:
            return [], 0  # 行数不足 keep => clear 不删任何行
        prefix_max = int(row[0])
        rows = con.execute(
            "SELECT id FROM messages WHERE session_id = ? AND id > ? ORDER BY id",
            (session_id, prefix_max),
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return [], prefix_max
    from tools.chroma_session_indexer import message_doc_id

    return [message_doc_id(session_id, int(r[0])) for r in rows], int(rows[-1][0])


_PRUNE_LEDGER_ENV = "MIMIR_INDEX_PRUNE_LEDGER_PATH"
_PRUNE_LEDGER_MAX = 200


def _prune_ledger_path() -> Path:
    return _state_path(_PRUNE_LEDGER_ENV, "orphan_prune_ledger.json")


def _delete_stale_session_docs(session_id: str, doc_ids: list) -> Dict[str, Any]:
    """Delete exactly the docs the pre-clear snapshot named (whitelist scope guard).

    Whitelist, not a range: only ids **named by the snapshot** AND currently present
    for this session are deleted. A racing writer's rows are never in that set
    (their rowids postdate the snapshot ceiling) and other sessions are never
    touched — ``collection.get`` is filtered by ``session_id``, so the read cost is
    this session only (no full-library scan). Returns a measured reading; never
    raises, but failures are no longer silent (index-failure log + ``error`` field).
    """
    out: Dict[str, Any] = {"seeded": len(doc_ids or []), "present": 0, "deleted": 0}
    if not out["seeded"]:
        return out
    try:
        import tools.chroma_session_indexer as _csi

        if not _csi.chroma_incremental_enabled():
            # 配对不变量：增量写者关着 => 尾部从未重嵌，删了就是把「陈旧」换成「缺失」。
            out["skipped"] = "incremental_off"
            return out
        factory = getattr(_csi, "_get_incremental_collection", None) or _csi.get_chroma_collection
        collection = factory()
        have, offset = set(), 0
        while True:
            got = collection.get(
                where={"session_id": session_id}, include=[], limit=1000, offset=offset
            ).get("ids") or []
            if not got:
                break
            have |= set(got)
            offset += len(got)
            if len(got) < 1000:
                break
        target = [d for d in doc_ids if d in have]
        out["present"] = len(target)
        if target:
            # 分批(blast radius)：keep=0 一次可能点名上万条，单次巨型 delete 又慢又
            # 容易撞资源上限。1000 一批，逐批累计(deleted = 实际删成功的条数)。
            _BATCH = 1000
            deleted = 0
            for _i in range(0, len(target), _BATCH):
                _chunk = target[_i:_i + _BATCH]
                with _csi.chroma_write_lock():
                    collection.delete(ids=_chunk)
                deleted += len(_chunk)
            out["deleted"] = deleted
    except Exception as exc:
        try:
            from tools.chroma_session_indexer import note_index_failure

            note_index_failure("session_prune_inline", exc, sink="session_search_indexer")
        except Exception:  # pragma: no cover - 观测设施不得拖垮索引路径
            pass
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
    return out


def _note_prune_candidates(session_id: str, reading: Dict[str, Any]) -> None:
    """Record the sessions the write path pointed at => the monitor's prune whitelist.

    The monitor may only self-heal sessions that the writer itself named (whitelist
    scope guard): an unbounded "delete anything that looks stale" would make the
    monitor able to delete rows it never proved orphan.
    """
    try:
        path = _prune_ledger_path()
        data = _load_state(path)
        seeded = int(reading.get("seeded") or 0)
        deleted = int(reading.get("deleted") or 0)
        data[session_id] = {
            "ts": _now_ts(),
            "seeded": seeded,
            "deleted": deleted,
            "residual": max(0, seeded - deleted),
        }
        if len(data) > _PRUNE_LEDGER_MAX:
            ordered = sorted(data.items(), key=lambda kv: float((kv[1] or {}).get("ts") or 0.0))
            data = dict(ordered[-_PRUNE_LEDGER_MAX:])
        _save_state(path, data)
    except Exception:  # pragma: no cover
        logger.debug("prune ledger write failed (%s)", session_id)


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
    db_path = getattr(like_db, "db_path", None)
    # 解耦（2026-10-18）：clear 之前点名「将被删的 rowid」→ clear 之后立刻删。
    # 不再等重写循环跑完（30s 预算一截断，那一步永远等不到），也不再全库扫描。
    stale_docs, _stale_ceiling = _stale_docs_before_clear(session_id, db_path, keep)
    clear = getattr(like_db, "clear_session_messages", None)
    if callable(clear):
        try:
            clear(session_id, keep_first=keep)
        except TypeError:
            clear(session_id)  # legacy store without keep_first
            keep = 0
            stale_docs = []  # legacy 整会话清空 => 走下方全量重同步
    pruned = _delete_stale_session_docs(session_id, stale_docs)
    if pruned.get("seeded"):
        _note_prune_candidates(session_id, pruned)
        logger.debug("inline prune %s: %s", session_id, pruned)
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
            # F4(2026-10-19): 水位原先只在函数**返回前**写；30s off-loop 预算一截断
            # (今天 17 次 TIMEOUT)，水位就永远停在旧值 => 下次还是 keep=0。
            # 随进度打点：被打断也留下「已索引到哪」，下次走增量、逐次收敛。
            if count % 50 == 0:
                try:
                    record_watermark(session_id, messages, indexed_n=keep + count)
                except Exception:  # pragma: no cover - 打点失败不得拖垮索引
                    pass
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
    # F7(2026-10-19): 写者自报不足额（某条 upsert 失败）⇒ 不许清，留待 resume 补。
    if keep + count >= len(messages):
        clear_pending(session_id)
    else:
        record_pending(
            session_id,
            len(messages),
            source=source,
            title=title,
            actual=len(messages),
            chroma_docs=keep + count,
            reason="incomplete",
        )
    return count


# ── B4b · 启动钩子（2026-10-06 · 任务书 行218「B4b：接启动钩子 + 保留手动入口，不接 cron」）──
#
# 病灶：⑤ 的残留缺口①——「续传只有手动入口」（`scripts/resume_index.py`）。崩溃/超时留下的
# pending 半成品，只有人手动跑脚本才补；gateway 每次重启都不会自愈 ⇒ 索引缺行长期挂着。
#
# 形态：**一处**启动调用（`gateway/run.py`）+ 本模块内的实现（不新建文件、不接 cron）。
# - 无 pending ⇒ 早退，**不建 DB 连接、不加载 embedding**（零成本路径）。
# - 有 pending ⇒ 串行续传，默认**限 20 条/次**（`MIMIR_PENDING_INDEX_RESUME_LIMIT`）——
#   内存纪律：本进程 cgroup 上限 4G，chroma + bge-m3 同开曾致整机 OOM（2026-10-05 事故），
#   故不允许启动时无界回填；余量留给下次启动/手动入口继续。
# - **失败开放**：任何异常只记 warning，绝不影响启动；保留 `scripts/resume_index.py` 手动入口。
# - 关断：`MIMIR_PENDING_INDEX_RESUME=0`。
# - 延迟：`MIMIR_PENDING_INDEX_RESUME_DELAY_S`（默认 20s）——等启动/预热先落地，再吃 CPU/内存。

def _startup_resume_limit() -> Optional[int]:
    raw = os.environ.get("MIMIR_PENDING_INDEX_RESUME_LIMIT", "20")
    try:
        val = int(str(raw).strip() or "20")
    except Exception:
        return 20
    return None if val <= 0 else val


def startup_resume_pending(*, limit: Optional[int] = None) -> Dict[str, Any]:
    """启动钩子的核心逻辑（可离线测）：pending 空 ⇒ 早退；否则续传并回报。

    返回体字段即读数：`skipped` / `pending_seen` / `pending_after` / `resumed` / `error`。
    """
    if limit is None:
        limit = _startup_resume_limit()
    out: Dict[str, Any] = {"limit": limit}
    pending = pending_index_report()
    out["pending_seen"] = len(pending)
    if not pending:
        out["skipped"] = "no_pending"
        return out
    try:
        from mimir_constants import get_mimir_session_search_db_path
        from tools.session_search_tool import SessionSearchDB

        db = SessionSearchDB(str(get_mimir_session_search_db_path()))
        out["resumed"] = resume_pending_indexes(like_db=db, limit=limit)
    except Exception as exc:
        logger.warning("[PENDING_INDEX_RESUME] 续传失败（启动不受影响）：%s", exc)
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
        return out
    out["pending_after"] = len(pending_index_report())
    return out


def start_pending_index_resume_thread(*, logger: Any = None, delay_s: Optional[float] = None):
    """启动钩子入口：装 daemon 线程跑 `startup_resume_pending`。返回线程或 None（关断时）。

    **只读 env，不读配置系统**；不阻塞启动；任何异常都吞（返回 None）。
    """
    log = logger or globals().get("logger")
    if os.environ.get("MIMIR_PENDING_INDEX_RESUME", "1").strip().lower() in ("0", "false", "no", "off"):
        log.info("[PENDING_INDEX_RESUME] 已关断（MIMIR_PENDING_INDEX_RESUME=0）")
        return None
    try:
        if delay_s is None:
            raw = os.environ.get("MIMIR_PENDING_INDEX_RESUME_DELAY_S", "20")
            try:
                delay_s = max(0.0, float(str(raw).strip() or "20"))
            except Exception:
                delay_s = 20.0
    except Exception:
        delay_s = 20.0

    def _task() -> None:
        if delay_s:
            time.sleep(delay_s)
        try:
            result = startup_resume_pending()
            log.info("[PENDING_INDEX_RESUME] %s", result)
        except Exception as exc:  # pragma: no cover - 观测/自愈设施不得拖垮启动
            log.warning("[PENDING_INDEX_RESUME] 钩子异常（已降级）：%s", exc)

    thread = threading.Thread(target=_task, daemon=True, name="pending-index-resume")
    thread.start()
    return thread
