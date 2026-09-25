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

    stats = backfill_chroma_sessions(like_db, chroma_dir=chroma_dir)
    print(
        f"chroma backfill done: messages={stats.messages_indexed} "
        f"batches={stats.batches} skipped={stats.messages_skipped}"
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
