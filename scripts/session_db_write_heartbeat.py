#!/usr/bin/env python3
"""P1 · 会话库写入心跳量具（只读）。

背景（2026-10-20 实证）：
    sessions_search.db 的写路径可以**静默死亡**——实测停写 19h31m，
    期间 gateway 进程存活（MainPID 未变、NRestarts=0）、无 ERROR 日志、
    chroma 侧也照常"看起来健康"。既有的 F6 修的是"检测层崩溃被吞"，
    修不了"写入根本没发生"——因为没有「写入是否还活着」这个判据。

本量具补的正是这一个缺口：把「静默 19.5 小时」变成「超过阈值必红」。

2026-11-14 修（假阳性 · 判据缺输入侧）：
    sessions_search.db 是**派生索引**——只在新消息 append 时才写
    （gateway/session.py:1253 → _append_to_sessions_search_index）。
    零入站消息 ⇒ 零写入是**正确行为**，而旧判据只看库 mtime age，
    于是把「没人在说话」判成「管道死了」：实测 11.2h 无入站（feishu
    只有 token 刷新日志）却连发 rc=1 告警，真停写会淹没在噪声里。
    本修引入**输入侧独立信号**（agent.log 的 `response ready` 行）：
    库落后于「最近一次完成的交互轮」才算真停写；无新轮回 ⇒ idle_no_input。

判据（库侧取较新者；输入侧决定 stale 是否算故障）：
    S1  库文件 mtime（journal_mode=delete 时即最后提交时刻；若库切到 WAL，
        则同时看 -wal 的 mtime，取较新者）
    S2  messages 表 max(timestamp)（注意：回填导致 rowid 与时序脱挂，
        故 S2 只作辅证，不单独作判据）
    S3  agent.log 最近 `response ready: platform=…` 时间戳（独立输入信号）

退出码：
    rc=0  新鲜（age <= threshold）**或** 陈旧但无新输入（idle_no_input）
    rc=1  停写（age > threshold **且** S3 有更新的交互轮 = 该写没写）← 应告警
    rc=2  库缺失 / 不可读

用法：
    python3 scripts/session_db_write_heartbeat.py
    python3 scripts/session_db_write_heartbeat.py --threshold 1800 --json
    python3 scripts/session_db_write_heartbeat.py --selftest      # 两向自检
    python3 scripts/session_db_write_heartbeat.py --no-input-gate # 旧语义（纯 mtime）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# 2026-10-20 修：不再依赖 HOME 环境（Path.home() 在沙箱/cron 下可被改写
# ⇒ 曾报假 [MISSING] db_missing，而库实际健康）。改用 getpwuid 的真实家目录，
# 并保留 MIMIR_AETHER_HOME 覆盖。
def _resolve_data_root() -> Path:
    env = os.environ.get("MIMIR_AETHER_HOME")
    if env:
        return Path(env)
    try:
        import pwd as _pwd
        return Path(_pwd.getpwuid(os.getuid()).pw_dir) / ".mimiraether"
    except Exception:
        return Path.home() / ".mimiraether"


DEFAULT_DB = _resolve_data_root() / "data" / "sessions_search.db"
DEFAULT_SOURCE_LOG = _resolve_data_root() / "logs" / "agent.log"
DEFAULT_THRESHOLD = 1800  # 30 min

# `2026-11-14 10:40:28,705 INFO …: response ready: platform=feishu chat=…`
_TURN_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s.*?"
    r"response ready: platform=(?P<plat>[A-Za-z0-9_-]+)"
)


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


def _newest_turn_ts(log_path: Path, tail_bytes: int = 4 * 1024 * 1024) -> tuple[float, str, int]:
    """从 agent.log 尾部取「最近一次完成的交互轮」——**独立输入信号**（S3）。

    为什么必须有它（2026-11-14 实证）：派生索引零写入既可能是「管道死了」，
    也可能是「根本没人说话」。只看库 mtime 分不开这两种 ⇒ 必然假红。

    返回 (timestamp, platform, 命中条数)；读不到/无命中返回 (0.0, "", 0)。
    """
    if not log_path.exists():
        return 0.0, "", 0
    try:
        size = log_path.stat().st_size
        with log_path.open("rb") as fh:
            if size > tail_bytes:
                fh.seek(size - tail_bytes)
                fh.readline()  # 丢掉被切断的首行
            raw = fh.read()
    except OSError:
        return 0.0, "", 0

    best_ts, best_plat, hits = 0.0, "", 0
    for line in raw.decode("utf-8", "replace").splitlines():
        m = _TURN_RE.match(line)
        if not m:
            continue
        hits += 1
        try:
            ts = datetime.strptime(m.group("ts"), "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            continue
        if ts >= best_ts:
            best_ts, best_plat = ts, m.group("plat")
    return best_ts, best_plat, hits


def evaluate(db: Path, threshold: int, source_log: Path | None = None) -> dict:
    if not db.exists():
        return {"rc": 2, "reason": "db_missing", "db": str(db)}
    mtime, files = _newest_mtime(db)
    if mtime <= 0:
        return {"rc": 2, "reason": "db_unreadable", "db": str(db)}
    ts = _max_ts(db)
    newest = max(mtime, ts)
    age = time.time() - newest
    stale = age > threshold

    turn_ts, turn_plat, turn_hits = (0.0, "", 0)
    if source_log is not None:
        turn_ts, turn_plat, turn_hits = _newest_turn_ts(Path(source_log))

    # 输入侧判定：库落后于最近一次完成的交互轮 > 1s ⇒「该写没写」= 真停写。
    # 无输入信号（source_log=None）⇒ 退回旧语义，只报 stale。
    pending_input = bool(turn_ts and turn_ts > newest + 1.0)

    # 输入侧闸门关闭（source_log=None）⇒ 退回旧语义：陈旧即红。
    if stale and (source_log is None or pending_input):
        rc, reason = 1, "write_stalled"
    elif stale:
        rc, reason = 0, "idle_no_input"
    else:
        rc, reason = 0, "write_alive"

    return {
        "rc": rc,
        "reason": reason,
        "db": str(db),
        "threshold_s": threshold,
        "age_s": round(age, 1),
        "files": files,
        "mtime": int(mtime),
        "max_timestamp": int(ts),
        "newest_src": "mtime" if mtime >= ts else "max_timestamp",
        "newest_turn_at": int(turn_ts),
        "newest_turn_platform": turn_plat,
        "turns_in_log_tail": turn_hits,
        "pending_input": pending_input,
        "input_gate": source_log is not None,
    }


def _selftest() -> int:
    """两向自检：该红必红（rc=1）· 该绿必绿（rc=0）· 缺库 rc=2。

    正控与负控用**不同**的临时库/日志与**不同**的期望值——防空洞控制组。
    2026-11-14 增：输入侧两向（陈旧+有新轮 ⇒ 红；陈旧+无新轮 ⇒ idle 绿）。
    """
    fails = []
    log_fmt = "%Y-%m-%d %H:%M:%S,000 INFO gateway.router.agent_route_mixin: response ready: platform=feishu chat=oc_x time=1.0s api_calls=1"
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)

        def _mkdb(name: str, age_s: float) -> Path:
            p = td / name
            con = sqlite3.connect(p)
            con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, timestamp REAL)")
            con.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES ('s','user','x',?)", (time.time() - age_s,))
            con.commit()
            con.close()
            old = time.time() - age_s
            os.utime(p, (old, old))
            return p

        def _mklog(name: str, turn_age_s: float | None) -> Path:
            p = td / name
            if turn_age_s is None:
                p.write_text("", encoding="utf-8")
            else:
                stamp = datetime.fromtimestamp(time.time() - turn_age_s).strftime(log_fmt)
                p.write_text(stamp + "\n", encoding="utf-8")
            return p

        # NEG1（该红）：陈旧库 + 无输入信号（旧语义基线，保证不回归）
        r = evaluate(_mkdb("neg1.db", 7200), 1800, None)
        if r["rc"] != 1 or r["reason"] != "write_stalled":
            fails.append(f"NEG1: expected rc=1/write_stalled got {r['rc']}/{r['reason']}")

        # NEG2（该红）：陈旧库 + 日志里有更新的交互轮 ⇒ 该写没写（本次新增的死法）
        r = evaluate(_mkdb("neg2.db", 7200), 1800, _mklog("neg2.log", 60))
        if r["rc"] != 1 or r["reason"] != "write_stalled" or not r["pending_input"]:
            fails.append(
                f"NEG2: expected rc=1/write_stalled+pending got {r['rc']}/{r['reason']}/pending={r['pending_input']}"
            )

        # POS1（该绿）：陈旧库 + 日志里最后一轮比库更旧 ⇒ 无输入，idle
        r = evaluate(_mkdb("pos1.db", 7200), 1800, _mklog("pos1.log", 10800))
        if r["rc"] != 0 or r["reason"] != "idle_no_input" or r["pending_input"]:
            fails.append(
                f"POS1: expected rc=0/idle_no_input got {r['rc']}/{r['reason']}/pending={r['pending_input']}"
            )

        # POS2（该绿）：新库 + 新轮 ⇒ write_alive
        r = evaluate(_mkdb("pos2.db", 10), 1800, _mklog("pos2.log", 60))
        if r["rc"] != 0 or r["reason"] != "write_alive":
            fails.append(f"POS2: expected rc=0/write_alive got {r['rc']}/{r['reason']}")

        # POS3（该绿）：陈旧库 + 日志文件不存在 ⇒ 不得因读不到日志而假红
        r = evaluate(_mkdb("pos3.db", 7200), 1800, td / "nope.log")
        if r["rc"] != 0 or r["reason"] != "idle_no_input":
            fails.append(f"POS3: expected rc=0/idle_no_input got {r['rc']}/{r['reason']}")

        # MISS（该 rc=2）
        r_miss = evaluate(td / "nope.db", 1800, None)
        if r_miss["rc"] != 2:
            fails.append(f"MISS: expected rc=2 got {r_miss['rc']}")

    if fails:
        for f in fails:
            print(f"SELFTEST FAIL {f}")
        print("selftest: FAILED")
        return 1
    print("selftest: OK (neg1 rc=1 / neg2 rc=1+pending / pos1 idle / pos2 alive / pos3 no-log / miss rc=2)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    ap.add_argument("--source-log", default=str(DEFAULT_SOURCE_LOG))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument(
        "--no-input-gate",
        action="store_true",
        help="关闭输入侧闸门（退回 2026-10-20 旧语义：只看库 mtime age）",
    )
    a = ap.parse_args()

    if a.selftest:
        return _selftest()

    src = None if a.no_input_gate else Path(a.source_log)
    res = evaluate(Path(a.db), a.threshold, src)
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        icon = {0: "OK", 1: "STALLED", 2: "MISSING"}[res["rc"]]
        print(
            f"[{icon}] {res.get('reason')} age={res.get('age_s')}s "
            f"threshold={a.threshold}s src={res.get('newest_src')} "
            f"pending_input={res.get('pending_input')}"
        )
    return res["rc"]


if __name__ == "__main__":
    sys.exit(main())
