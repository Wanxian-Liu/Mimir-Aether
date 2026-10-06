#!/usr/bin/env python3
"""索引断点续传入口：把 pending（超时/中断留下的半成品）会话补齐。

用法：
  .venv/bin/python3 scripts/resume_index.py            # 续传全部 pending
  .venv/bin/python3 scripts/resume_index.py --report   # 只看 pending 清单
  .venv/bin/python3 scripts/resume_index.py --session <sid>

只补「SQLite 有、chroma 缺」的行（不重嵌已就位部分）。
退出码：0 = 无残留 pending；1 = 仍有 pending（本次未补齐或新失败）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    from mimir_constants import get_mimir_session_search_db_path
    from tools.session_search_indexer import (
        pending_index_report,
        resume_pending_indexes,
        resume_session_index,
    )
    from tools.session_search_tool import SessionSearchDB

    pending = pending_index_report()
    if args.report:
        print(json.dumps({"pending": pending}, ensure_ascii=False, indent=2))
        return 1 if pending else 0

    db = SessionSearchDB(str(get_mimir_session_search_db_path()))
    if args.session:
        result = {"pending_seen": len(pending), "resumed": {args.session: resume_session_index(args.session, like_db=db)}}
    else:
        result = resume_pending_indexes(like_db=db, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if pending_index_report() else 0


if __name__ == "__main__":
    raise SystemExit(main())
