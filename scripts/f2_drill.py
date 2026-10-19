#!/usr/bin/env python3
"""F2 演练（可复跑判据 · 2026-10-19 Mimir 全面审计 J2）。

纪律：**不碰生产库**。整个演练跑在沙箱里——`MIMIR_SESSION_DB` / `MIMIR_CHROMA_DIR` /
`MIMIR_INDEX_PENDING*_PATH` / `MIMIR_INDEX_WATERMARK_PATH` 全部指向
`~/.mimiraether/tmp/f2drill/`，但**跑的是生产代码路径**
（`reindex_session_transcript` / `record_pending_delete` / `resume_pending_deletes` /
`resume_pending_indexes`）。嵌入用 tier0 确定性 hash（`MIMIR_EMBED_MODEL=""`），
耗时 <5s，不吃 4GB。

判据（J2）：
  删 1 -> pending_deletes +1 -> resume -> chroma -N（N=该会话 doc 数）
  补 1 -> pending_index  +1 -> resume -> chroma +1
  且两次 resume 后 pending 均归零；差集扫描 orphans=0。

退出码 0 = 全绿；1 = 任一判据不符（打印 where）。
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

SANDBOX = Path(os.path.expanduser("~/.mimiraether/tmp/f2drill"))
ROOT = Path(__file__).resolve().parents[1]

SCHEMA = [
    """CREATE TABLE sessions (
        session_id TEXT PRIMARY KEY, source TEXT, started_at REAL, ended_at REAL,
        title TEXT, message_count INTEGER DEFAULT 0)""",
    """CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT,
        content TEXT, tool_name TEXT, timestamp REAL)""",
]


def setup_env() -> None:
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    (SANDBOX / "chroma").mkdir(parents=True, exist_ok=True)
    os.environ["MIMIR_SESSION_DB"] = str(SANDBOX / "sessions_search.db")
    os.environ["MIMIR_CHROMA_DIR"] = str(SANDBOX / "chroma")
    os.environ["MIMIR_INDEX_PENDING_PATH"] = str(SANDBOX / "index_pending.json")
    os.environ["MIMIR_INDEX_PENDING_DELETES_PATH"] = str(SANDBOX / "index_pending_deletes.json")
    os.environ["MIMIR_INDEX_WATERMARK_PATH"] = str(SANDBOX / "index_watermark.json")
    os.environ["MIMIR_CHROMA_DEGRADE_STATE_PATH"] = str(SANDBOX / "chroma_degraded.json")
    os.environ["MIMIR_EMBED_MODEL"] = ""  # tier0 hash，避免加载 bge-m3
    os.environ.pop("MIMIR_CHROMA_DEGRADED", None)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def make_source() -> None:
    db = sqlite3.connect(os.environ["MIMIR_SESSION_DB"])
    for stmt in SCHEMA:
        db.execute(stmt)
    for sid, msgs in (("D1", 3), ("D2", 2)):
        db.execute("INSERT INTO sessions (session_id, source, started_at, title) VALUES (?,?,?,?)",
                   (sid, "drill", 1760000000.0, "drill-" + sid))
        for i in range(msgs):
            db.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)",
                       (sid, "user" if i % 2 == 0 else "assistant",
                        "%s message %d drill payload" % (sid, i), 1760000000.0 + i))
    db.commit()
    db.close()


def add_message(sid: str, text: str) -> None:
    db = sqlite3.connect(os.environ["MIMIR_SESSION_DB"])
    db.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)",
               (sid, "user", text, 1760000900.0))
    db.commit()
    db.close()


def drop_session(sid: str) -> None:
    db = sqlite3.connect(os.environ["MIMIR_SESSION_DB"])
    db.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    db.execute("DELETE FROM sessions WHERE session_id = ?", (sid,))
    db.commit()
    db.close()


def main() -> int:
    setup_env()
    from tools.chroma_session_indexer import get_chroma_collection
    from tools.session_search_indexer import (
        pending_delete_report,
        pending_index_report,
        record_pending,
        record_pending_delete,
        resume_pending_deletes,
        resume_pending_indexes,
        scan_orphan_sessions,
    )
    from tools.session_search_tool import SessionSearchDB

    make_source()
    db = SessionSearchDB(os.environ["MIMIR_SESSION_DB"])
    col = get_chroma_collection()

    # 预置：两个会话各 3/2 条进 chroma（走生产 resume 路径写）
    for sid, n in (("D1", 3), ("D2", 2)):
        record_pending(sid, n, source="drill", title="drill-" + sid)
    resume_pending_indexes(like_db=db)

    base = col.count()
    print(json.dumps({"step": "baseline", "chroma_total": base,
                      "pending_index": len(pending_index_report()),
                      "pending_deletes": len(pending_delete_report())}, ensure_ascii=False))

    fails = []

    # ---- A1 复现缺口：只删源库，chroma 不动（这正是 F2 要治的）
    drop_session("D1")
    after_drop = col.count()
    print(json.dumps({"step": "A1 只删源库", "chroma_total": after_drop,
                      "期望": "不变(=pre-F2 行为·缺口实证)"}, ensure_ascii=False))
    if after_drop != base:
        fails.append("A1 源库删除竟改了 chroma（判据前提不成立）")

    # ---- A2 记账：删除即记 pending
    record_pending_delete("D1", reason="session_deleted")
    pd = pending_delete_report()
    print(json.dumps({"step": "A2 记账", "pending_deletes": len(pd), "keys": list(pd)},
                     ensure_ascii=False))
    if len(pd) != 1 or "D1" not in pd:
        fails.append("A2 pending_deletes 未 +1")

    # ---- A3 resume：删掉 chroma 里 D1 的 3 条
    res = resume_pending_deletes()
    after_del = col.count()
    print(json.dumps({"step": "A3 resume_deletes", "res": res, "chroma_total": after_del},
                     ensure_ascii=False))
    if after_del != base - 3:
        fails.append("A3 chroma 未 -3（实测 %d，期望 %d）" % (after_del, base - 3))
    if pending_delete_report():
        fails.append("A3 resume 后 pending_deletes 未归零")

    # ---- A4 差集兜底：此刻应无 orphan
    scan = scan_orphan_sessions(record=True)
    print(json.dumps({"step": "A4 scan_orphans", "scan": scan}, ensure_ascii=False))
    if scan.get("orphans") != 0:
        fails.append("A4 差集扫描仍报 orphan=%s" % scan.get("orphans"))

    # ---- B1 补 1 条 -> 记 pending_index
    before_add = col.count()
    add_message("D2", "D2 extra drill payload")
    record_pending("D2", 3, source="drill", title="drill-D2")
    pi = pending_index_report()
    print(json.dumps({"step": "B1 补 1 记账", "pending_index": len(pi), "keys": list(pi)},
                     ensure_ascii=False))
    if len(pi) != 1:
        fails.append("B1 pending_index 未 +1")

    # ---- B2 resume：chroma +1
    resume_pending_indexes(like_db=db)
    after_add = col.count()
    print(json.dumps({"step": "B2 resume_indexes", "chroma_total": after_add,
                      "期望": before_add + 1}, ensure_ascii=False))
    if after_add != before_add + 1:
        fails.append("B2 chroma 未 +1（实测 %d，期望 %d）" % (after_add, before_add + 1))
    if pending_index_report():
        fails.append("B2 resume 后 pending_index 未归零")

    print(json.dumps({"verdict": "GREEN" if not fails else "RED", "fails": fails},
                     ensure_ascii=False))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
