#!/usr/bin/env python3
"""Backfill sessions_search.db (and optional fts5_search.db) from gateway JSONL transcripts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mimir_constants import get_mimir_data_dir, get_mimir_sessions_dir
from tools.session_search_indexer import backfill_sessions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=None,
        help="Gateway sessions dir (default: $MIMIR_AETHER_HOME/data/sessions)",
    )
    parser.add_argument(
        "--like-db",
        type=Path,
        default=None,
        help="sessions_search.db path (default: data/sessions_search.db under home)",
    )
    parser.add_argument(
        "--fts-db",
        type=Path,
        default=None,
        help="Also index into fts5_search.db at this path (default: skip)",
    )
    parser.add_argument(
        "--with-fts",
        action="store_true",
        help="Index into default fts5_search.db under MIMIR home",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Clear existing index before backfill",
    )
    args = parser.parse_args()

    sessions_dir = args.sessions_dir or get_mimir_sessions_dir()
    like_db = args.like_db or (get_mimir_data_dir() / "sessions_search.db")
    fts_db = args.fts_db
    if args.with_fts and fts_db is None:
        fts_db = get_mimir_data_dir() / "fts5_search.db"

    stats = backfill_sessions(
        sessions_dir,
        like_db_path=like_db,
        fts_db_path=fts_db,
        fresh=args.fresh,
    )
    print(
        f"backfill done: sessions={stats.sessions} messages={stats.messages} "
        f"skipped_files={stats.skipped_files} fts_messages={stats.fts_messages}"
    )
    print(f"  sessions_dir={sessions_dir}")
    print(f"  like_db={like_db}")
    if fts_db:
        print(f"  fts_db={fts_db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
