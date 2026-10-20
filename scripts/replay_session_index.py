#!/usr/bin/env python3
"""P0 · 定向重放单个会话 jsonl → sessions_search.db（+ chroma）。

为什么需要它（2026-10-20）：
    gateway 实时路径因 ``skip_db=agent_persisted`` 把派生索引一并跳过，
    导致今日会话 jsonl 有 2,400 行、db 有 0 行。``scripts/backfill_sessions_search.py``
    没有会话过滤参数，跑全量会把**继承副本**会话一并重放（10-20 01:09 那次 +49,469 行
    膨胀就是这么来的）——所以必须能只跑一个会话。

为什么安全（幂等）：
    add_message 带会话内 ``seq`` 且 messages 表有 ``UNIQUE(session_id, seq)``
    （2026-10-20 加），重放同一会话不会重复插入；本次同时实测 before/after 计数。

用法：
    ~/src/MimirAether/.venv/bin/python3 scripts/replay_session_index.py \
        --session 20261020_203241_e9b0dd55
    ... --limit 200 --no-chroma        # 只验路径、不烧嵌入
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(
    os.environ.get("MIMIR_CODE_ROOT", str(Path.home() / "src" / "MimirAether"))
).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mimir_constants import get_mimir_data_dir, get_mimir_sessions_dir  # noqa: E402
from tools.session_search_indexer import (  # noqa: E402
    extract_searchable_message,
    index_transcript_message,
    iter_transcript_messages,
    load_sessions_index,
)
from tools.session_search_tool import SessionSearchDB  # noqa: E402


def db_count(db_path: Path, session_id: str) -> int:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=15)
    try:
        return int(con.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()[0])
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--sessions-dir", type=Path, default=None)
    ap.add_argument("--like-db", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=0, help="0 = 全部")
    ap.add_argument("--no-chroma", action="store_true", help="不写 chroma（只验库路径）")
    a = ap.parse_args()

    sessions_dir = a.sessions_dir or get_mimir_sessions_dir()
    db_path = a.like_db or (get_mimir_data_dir() / "sessions_search.db")
    path = sessions_dir / f"{a.session}.jsonl"
    if not path.exists():
        print(f"FATAL session jsonl not found: {path}")
        return 2

    meta = load_sessions_index(sessions_dir).get(a.session, {})
    source = str(meta.get("platform") or meta.get("source") or "unknown")
    title = str(meta.get("display_name") or meta.get("title") or a.session)

    before = db_count(db_path, a.session)
    db = SessionSearchDB(str(db_path))
    db.add_session(a.session, source=source, title=title)

    if a.no_chroma:
        # 只验库路径、不烧嵌入：chroma 同步函数在 index_transcript_message 内部
        # 按模块属性取用，故此处整体置空即可（循环外一次，勿放循环内）。
        import tools.chroma_session_indexer as _csi

        _csi.sync_message_to_chroma = lambda *x, **k: None  # type: ignore[assignment]

    indexed = skipped = parsed_n = dup = pos = 0
    for _ln, record in iter_transcript_messages(path):
        parsed_n += 1
        if a.limit and pos >= a.limit:
            break
        if extract_searchable_message(record) is None:
            skipped += 1
            continue
        # seq = 会话内「可搜索消息」的 1-based 序号。必须与实时路径一致
        # （实时路径只存可搜索消息、按 MAX+1 递增），这样重放才真正撞 UNIQUE。
        pos += 1
        ok = index_transcript_message(
            a.session, record, like_db=db, source=source, title=title, seq=pos
        )
        if ok:
            indexed += 1
        else:
            dup += 1

    after = db_count(db_path, a.session)
    print(
        f"replay session={a.session} jsonl_records={parsed_n} "
        f"indexed={indexed} dup_skipped={dup} non_searchable_skipped={skipped} "
        f"db_before={before} db_after={after} delta={after - before}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
