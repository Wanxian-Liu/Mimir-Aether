#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cron_chain_health.py — 「索引 cron 链」健康判据（S4′ 能红判据 ①）

判据（逐字对齐会议卡 2026-10-13 L920）：
    连续 2 次 scheduled run `status=completed` ∧ `finished_at - started_at < 3000s`
    ⇒ rc=0；否则 rc=1；**源缺失** ⇒ rc=2。

设计要点（防「缺列当绿」）：
  * 分母必打印：`scanned_n=<N>`（该 job 在 executions 表里的现存行数）。
    行数 < 2 ⇒ 判 `UNKNOWN`（**不得**判 PASS）。注：executions 是**滚动窗口表**
    （实测全表恰好 1000 行 / 跨度约 16h）⇒ 老行会被滚掉，行数不足时「通过」是假绿。
  * `finished_at` 为空/NULL ⇒ 该轮判 `unknown`（**不得**判 completed）。
  * 时间戳带 +08:00 偏移 ⇒ 用 datetime.fromisoformat 解析（禁字符串截取）。

用法：
  ~/src/MimirAether/.venv/bin/python3 scripts/cron_chain_health.py            # 默认 job/DB
  ~/src/MimirAether/.venv/bin/python3 scripts/cron_chain_health.py --db <副本> --job-id <id>
  ~/src/MimirAether/.venv/bin/python3 scripts/cron_chain_health.py --selftest  # 档位④ 两向自检

退出码：0=PASS / 1=FAIL / 2=源缺失（DB 或表不存在）
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
from datetime import datetime

DEFAULT_DB = os.path.expanduser("~/.hermes/cron/executions.db")
DEFAULT_JOB = "0d19ebdcab46"          # name=wiki语义索引增量 · script=wiki-index-cron.sh
THRESHOLD_S = 3000.0
WINDOW_N = 2

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


def _parse(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def load_runs(db_path, job_id, n=WINDOW_N):
    """返回 (runs, total_scanned, err)。err 非空 ⇒ 调用方按 rc=2 处理。"""
    if not os.path.exists(db_path):
        return [], 0, "DB 不存在: %s" % db_path
    con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    try:
        has = cur.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='executions'"
        ).fetchone()[0]
        if not has:
            return [], 0, "表 executions 不存在于 %s" % db_path
        total = cur.execute(
            "SELECT COUNT(*) FROM executions WHERE job_id=?", (job_id,)
        ).fetchone()[0]
        rows = [
            dict(r)
            for r in cur.execute(
                "SELECT id, job_id, source, status, started_at, finished_at, error "
                "FROM executions WHERE job_id=? ORDER BY claimed_at DESC, id DESC LIMIT ?",
                (job_id, n),
            )
        ]
        return rows, total, ""
    except sqlite3.DatabaseError as exc:                       # 非 sqlite 文件等
        return [], 0, "DB 读取失败: %s" % exc
    finally:
        con.close()


def judge(runs, total):
    """返回 (verdict, lines)。每轮 verdict = ok / fail(status) / fail(duration) / unknown。"""
    lines = []
    if len(runs) < WINDOW_N:
        lines.append(
            "scanned_n=%d 行数不足（需 %d 轮）⇒ UNKNOWN（缺列/缺行**不当绿**）"
            % (total, WINDOW_N)
        )
        return UNKNOWN, lines
    lines.append("scanned_n=%d" % total)
    ok = True
    for i, r in enumerate(reversed(runs), 1):                  # 按时间正序展示
        started, finished = _parse(r.get("started_at")), _parse(r.get("finished_at"))
        if finished is None or started is None:
            dur, v = None, "unknown"
            ok = False
        else:
            dur = (finished - started).total_seconds()
            if r.get("status") != "completed":
                v = "fail(status)"
            elif dur >= THRESHOLD_S:
                v = "fail(duration)"
            else:
                v = "ok"
            ok = ok and (v == "ok")
        lines.append(
            "  run[%d] status=%s started=%s finished=%s dur=%s verdict=%s"
            % (i, r.get("status"), r.get("started_at"), r.get("finished_at"),
               "None" if dur is None else "%.2fs" % dur, v)
        )
    return (PASS if ok else FAIL), lines


def run(db_path, job_id):
    runs, total, err = load_runs(db_path, job_id)
    if err:
        print("VERDICT: UNKNOWN  source=%s job=%s" % (db_path, job_id))
        print("  reason: %s" % err)
        print("  ⇒ rc=2（源缺失 = 空跑读数，比「通过」更红）")
        return 2
    verdict, lines = judge(runs, total)
    print("VERDICT: %s  source=%s job=%s" % (verdict, db_path, job_id))
    for line in lines:
        print(line)
    if verdict == PASS:
        print("  ⇒ rc=0（连续 %d 轮 completed 且各轮 < %ds）" % (WINDOW_N, int(THRESHOLD_S)))
        return 0
    if verdict == UNKNOWN:
        print("  ⇒ rc=1（行数不足 ⇒ 不得判通过；补足轮次后重跑）")
        return 1
    print("  ⇒ rc=1（存在未达标轮次）")
    return 1


# ── 自检（档位④：正控 + 负控，一次跑全）────────────────────────────
def _mk(db_path, rows, with_table=True):
    con = sqlite3.connect(db_path)
    if with_table:
        con.execute(
            "CREATE TABLE executions (id TEXT PRIMARY KEY, job_id TEXT, source TEXT, "
            "status TEXT, claimed_at TEXT, started_at TEXT, finished_at TEXT, error TEXT)"
        )
        con.executemany("INSERT INTO executions VALUES (?,?,?,?,?,?,?,?)", rows)
    else:
        con.execute("CREATE TABLE other (a TEXT)")
    con.commit()
    con.close()


def selftest():
    tmp = tempfile.mkdtemp(prefix="chain-health-selftest-")
    J = "jobA"
    cases = []

    # 正控 ①：连续 2 轮 completed 且都 < 3000s ⇒ PASS(rc 0)
    d1 = os.path.join(tmp, "ok.db")
    _mk(d1, [
        ("a1", J, "builtin", "completed", "2026-10-13T08:00:23", "2026-10-13T08:00:24", "2026-10-13T08:06:55", None),
        ("a0", J, "builtin", "completed", "2026-10-13T02:00:23", "2026-10-13T02:00:24", "2026-10-13T02:06:00", None),
    ])
    cases.append(("正控①连续2轮绿", d1, 0))

    # 负控 ①：最近一轮 failed（超时 3602s）⇒ 不得 PASS ⇒ rc 1
    d2 = os.path.join(tmp, "fail.db")
    _mk(d2, [
        ("b1", J, "builtin", "completed", "2026-10-13T08:00:23", "2026-10-13T08:00:24", "2026-10-13T08:06:55", None),
        ("b0", J, "builtin", "failed",    "2026-10-13T00:00:23", "2026-10-13T00:00:24", "2026-10-13T01:00:26", "Script timed out after 3600s"),
    ])
    cases.append(("负控①一轮 failed", d2, 1))

    # 负控 ②：finished_at 置空 ⇒ 必须 unknown（**核心负控**·防「缺列当绿」）⇒ rc 1
    d3 = os.path.join(tmp, "nullfin.db")
    _mk(d3, [
        ("c1", J, "builtin", "completed", "2026-10-13T08:00:23", "2026-10-13T08:00:24", None, None),
        ("c0", J, "builtin", "completed", "2026-10-13T02:00:23", "2026-10-13T02:00:24", "2026-10-13T02:06:00", None),
    ])
    cases.append(("负控②finished_at=NULL", d3, 1))

    # 负控 ③：completed 但耗时 ≥ 阈值（3302s）⇒ FAIL ⇒ rc 1
    d4 = os.path.join(tmp, "slow.db")
    _mk(d4, [
        ("e1", J, "builtin", "completed", "2026-10-12T18:00:57", "2026-10-12T18:00:58", "2026-10-12T18:56:00", None),
        ("e0", J, "builtin", "completed", "2026-10-12T12:00:57", "2026-10-12T12:00:58", "2026-10-12T12:06:00", None),
    ])
    cases.append(("负控③耗时超阈", d4, 1))

    # 负控 ④：DB 不存在 ⇒ rc 2
    cases.append(("负控④DB缺失", os.path.join(tmp, "nope.db"), 2))

    # 负控 ⑤：表不存在 ⇒ rc 2
    d5 = os.path.join(tmp, "notable.db")
    _mk(d5, [], with_table=False)
    cases.append(("负控⑤表缺失", d5, 2))

    # 负控 ⑥：只有 1 行 ⇒ UNKNOWN（行数不足不当绿）⇒ rc 1
    d6 = os.path.join(tmp, "one.db")
    _mk(d6, [("f0", J, "builtin", "completed", "2026-10-13T08:00:23", "2026-10-13T08:00:24", "2026-10-13T08:06:55", None)])
    cases.append(("负控⑥仅1行", d6, 1))

    bad = 0
    for name, db, want in cases:
        print("=" * 12, name, "expect rc=%d" % want)
        got = run(db, J)
        flag = "OK" if got == want else "MISMATCH"
        if got != want:
            bad += 1
        print("  -> rc=%d %s" % (got, flag))
    print("=" * 12)
    print("SELFTEST %s  (%d/%d)" % ("PASS" if bad == 0 else "FAIL", len(cases) - bad, len(cases)))
    return 0 if bad == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--job-id", default=DEFAULT_JOB)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return run(args.db, args.job_id)


if __name__ == "__main__":
    sys.exit(main())
