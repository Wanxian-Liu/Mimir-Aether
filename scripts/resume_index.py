#!/usr/bin/env python3
"""索引断点续传入口：先消费删侧 pending，再补齐写侧 pending。

顺序（刘哥 P1 裁决 **先删后补**）：脏召回比缺口更贵——源库已删的消息若还留在
chroma，检索会返回不存在的内容；而缺口有 `chroma_backfill_full.py --verify-only`
兜底（J1）。

用法：
  .venv/bin/python3 scripts/resume_index.py            # 先删后补
  .venv/bin/python3 scripts/resume_index.py --report   # 只看两张 pending 清单
  .venv/bin/python3 scripts/resume_index.py --scan     # 差集兜底：chroma 多出的会话记账
  .venv/bin/python3 scripts/resume_index.py --session <sid>

退出码：0 = 两张 pending 都清空；1 = 仍有残留。
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
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delete-batch", type=int, default=1000)
    ap.add_argument("--delete-pause", type=float, default=0.0)
    args = ap.parse_args()

    from mimir_constants import get_mimir_session_search_db_path
    from tools.session_search_indexer import (
        pending_delete_report,
        pending_index_report,
        resume_pending_deletes,
        resume_pending_indexes,
        resume_session_index,
        scan_orphan_sessions,
    )
    from tools.session_search_tool import SessionSearchDB

    if args.report:
        print(json.dumps({"pending_deletes": pending_delete_report(),
                          "pending_index": pending_index_report()},
                         ensure_ascii=False, indent=2))
        return 1 if (pending_delete_report() or pending_index_report()) else 0

    result = {}
    if args.scan:
        result["scan"] = scan_orphan_sessions(record=True)

    # ① 先删：冷召回污染先清
    result["deletes"] = resume_pending_deletes(limit=args.limit,
                                               batch=args.delete_batch,
                                               pause_s=args.delete_pause)

    # ② 后补：SQLite 有、chroma 缺
    db = SessionSearchDB(str(get_mimir_session_search_db_path()))
    if args.session:
        result["resumed"] = {args.session: resume_session_index(args.session, like_db=db)}
    else:
        result["resumed"] = resume_pending_indexes(like_db=db, limit=args.limit)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if (pending_delete_report() or pending_index_report()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
