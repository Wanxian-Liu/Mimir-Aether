#!/usr/bin/env python3
"""P1 · 会话库写入心跳量具（只读）。

背景（2026-10-20 实证）：
    sessions_search.db 的写路径可以**静默死亡**——实测停写 19h31m，
    期间 gateway 进程存活（MainPID 未变、NRestarts=0）、无 ERROR 日志、
    chroma 侧也照常"看起来健康"。既有的 F6 修的是"检测层崩溃被吞"，
    修不了"写入根本没发生"——因为没有「写入是否还活着」这个判据。

本量具补的正是这一个缺口：把「静默 19.5 小时」变成「超过阈值必红」。

判据（两个信号，任一新鲜即算活；两者都旧 = 红）：
    S1  库文件 mtime（journal_mode=delete 时即最后提交时刻；若库切到 WAL，
        则同时看 -wal 的 mtime，取较新者）
    S2  messages 表 max(timestamp)（注意：回填导致 rowid 与时序脱挂，
        故 S2 只作辅证，不单独作判据）

退出码：
    rc=0  新鲜（now - newest <= threshold）
    rc=1  停写（now - newest >  threshold）  ← 应当告警
    rc=2  库缺失 / 不可读

用法：
    python3 scripts/session_db_write_heartbeat.py
    python3 scripts/session_db_write_heartbeat.py --threshold 1800 --json
    python3 scripts/session_db_write_heartbeat.py --selftest   # 两向自检
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_DB = Path.home() / ".mimiraether" / "data" / "sessions_search.db"
DEFAULT_THRESHOLD = 1800  # 30 min


def _newest_mtime(db: Path) -> tuple[float, list[str]]:
    """库本体 + WAL/SHM 的最新 mtime（WAL 模式下提交落在 -wal 上）。"""
    cands = [db, Path(str(db) + "-wal")]
    best, seen = 0.0, []
    for p in cands:
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        seen.append(f"{p.name}:{int(m)}")
        best = max(best, m)
    return best, seen


def _max_ts(db: Path) -> float:
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error:
        return 0.0
    try:
        row = con.execute("SELECT MAX(timestamp) FROM messages").fetchone()
        return float(row[0] or 0.0)
    except sqlite3.Error:
        return 0.0
    finally:
        con.close()


def evaluate(db: Path, threshold: int) -> dict:
    if not db.exists():
        return {"rc": 2, "reason": "db_missing", "db": str(db)}
    mtime, files = _newest_mtime(db)
    if mtime <= 0:
        return {"rc": 2, "reason": "db_unreadable", "db": str(db)}
    ts = _max_ts(db)
    newest = max(mtime, ts)
    age = time.time() - newest
    stale = age > threshold
    return {
        "rc": 1 if stale else 0,
        "reason": "write_stalled" if stale else "write_alive",
        "db": str(db),
        "threshold_s": threshold,
        "age_s": round(age, 1),
        "files": files,
        "mtime": int(mtime),
        "max_timestamp": int(ts),
        "newest_src": "mtime" if mtime >= ts else "max_timestamp",
    }


def _selftest() -> int:
    """两向自检：旧库必红（rc=1）· 新库必绿（rc=0）。

    正控与负控用**不同**的临时库、**不同**的期望值——防空洞控制组。
    """
    fails = []
    with tempfile.TemporaryDirectory() as td:
        # 负控（该红）：造一个 2 小时前写入的库
        stale = Path(td) / "stale.db"
        con = sqlite3.connect(stale)
        con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, timestamp REAL)")
        con.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES ('s','user','x',?)",
                    (time.time() - 7200,))
        con.commit(); con.close()
        old = time.time() - 7200
        os.utime(stale, (old, old))
        r_neg = evaluate(stale, 1800)
        if r_neg["rc"] != 1:
            fails.append(f"NEG: expected rc=1 got {r_neg['rc']} ({r_neg['reason']})")

        # 正控（该绿）：造一个刚写入的库
        fresh = Path(td) / "fresh.db"
        con = sqlite3.connect(fresh)
        con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, timestamp REAL)")
        con.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES ('s','user','y',?)",
                    (time.time(),))
        con.commit(); con.close()
        r_pos = evaluate(fresh, 1800)
        if r_pos["rc"] != 0:
            fails.append(f"POS: expected rc=0 got {r_pos['rc']} ({r_pos['reason']})")

        # 缺库（该 rc=2）
        r_miss = evaluate(Path(td) / "nope.db", 1800)
        if r_miss["rc"] != 2:
            fails.append(f"MISS: expected rc=2 got {r_miss['rc']}")

    if fails:
        for f in fails:
            print(f"SELFTEST FAIL {f}")
        print("selftest: FAILED")
        return 1
    print("selftest: OK (neg rc=1 / pos rc=0 / missing rc=2)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return _selftest()

    res = evaluate(Path(a.db), a.threshold)
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        icon = {0: "OK", 1: "STALLED", 2: "MISSING"}[res["rc"]]
        print(f"[{icon}] {res.get('reason')} age={res.get('age_s')}s "
              f"threshold={a.threshold}s src={res.get('newest_src')}")
    return res["rc"]


if __name__ == "__main__":
    sys.exit(main())
