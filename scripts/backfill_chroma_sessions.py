#!/usr/bin/env python3
"""Backfill Chroma session_messages from sessions_search.db (SEM-02)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mimir_constants import get_mimir_chroma_dir, get_mimir_session_search_db_path
from tools.chroma_session_indexer import (
    chroma_available,
    backfill_chroma_sessions,
    query_session_messages,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--like-db",
        type=Path,
        default=None,
        help="sessions_search.db path (default: get_mimir_session_search_db_path())",
    )
    parser.add_argument(
        "--chroma-dir",
        type=Path,
        default=None,
        help="Chroma persist root (default: get_mimir_chroma_dir())",
    )
    parser.add_argument(
        "--full-rebuild",
        action="store_true",
        help="全量重嵌（默认只补缺口：已存在的 doc 直接跳过）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印待嵌条数，不嵌入、不写库",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="",
        help="Optional smoke query after backfill",
    )
    parser.add_argument(
        "--query-limit",
        type=int,
        default=3,
        help="Max hits for --query smoke",
    )
    args = parser.parse_args()

    if not chroma_available():
        print(
            "error: chromadb not installed (pip install chromadb); "
            "semantic index unavailable",
            file=sys.stderr,
        )
        return 2

    like_db = args.like_db or get_mimir_session_search_db_path()
    chroma_dir = args.chroma_dir or get_mimir_chroma_dir()

    mode = "全量（--full-rebuild）" if args.full_rebuild else "缺口（跳过已存在）"
    print(f"模式={mode} · like_db={like_db} · chroma_dir={chroma_dir}")

    if args.dry_run:
        from tools.chroma_session_indexer import (
            get_chroma_collection,
            iter_indexable_messages,
            message_doc_id,
        )

        collection = get_chroma_collection(chroma_dir)
        have = set(collection.get(include=[])["ids"] or [])
        total = todo = 0
        for msg in iter_indexable_messages(like_db):
            total += 1
            if args.full_rebuild or message_doc_id(msg.session_id, msg.message_id) not in have:
                todo += 1
        print(f"dry-run: 源可索引 {total} 条 · 已有 {len(have)} 条 · **待嵌 {todo} 条**")
        return 0

    stats = backfill_chroma_sessions(
        like_db, chroma_dir=chroma_dir, skip_existing=not args.full_rebuild
    )
    print(
        f"chroma backfill done: 待嵌 {stats.messages_indexed} · "
        f"跳过已有 {stats.messages_skipped} · 批次 {stats.batches}"
    )
    print(f"  like_db={like_db}")
    print(f"  chroma_dir={chroma_dir}")

    if args.query.strip():
        hits = query_session_messages(
            args.query.strip(),
            limit=args.query_limit,
            chroma_dir=chroma_dir,
        )
        print(f"  query_hits={len(hits)}")
        for hit in hits:
            meta = hit.get("metadata") or {}
            sid = meta.get("session_id", "?")
            print(f"    - {hit.get('id')} session={sid} dist={hit.get('distance')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
