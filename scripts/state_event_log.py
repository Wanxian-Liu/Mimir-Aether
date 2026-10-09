#!/usr/bin/env python3
"""N13 段1 · 事件流 state-events.jsonl（append-only · 幂等 · 可回放）

真源（唯一权威）= 卡内 `state` 字段（会议卡 L755）。本模块**不读卡、不改卡**，
只负责把「状态转移」写成可回放事件流（L756）。

字段（逐字 · L756）：{ts, card_id, from, to, event, actor, trace_id}
  ts        epoch 秒（float）
  card_id   卡 id（如 N9）
  from/to   转移前后状态
  event     事件名（T 表用词：card.created / deps_all_closed / produces_persisted /
            L2_passed / L2_failed / deadline_exceeded / ack_received / ...）
  actor     执行者（hermes / mimir / loki / openclaw / human / watchdog）
  trace_id  同一 run 的关联 id（可空字符串，但键必须存在）

幂等：event_id = sha1(card_id|from|to|event|actor|trace_id) —— **ts 不入标识**，
     因此「同一件事重放（哪怕换了 ts）」不会新增行。连跑两遍 ⇒ 行数不涨。
可回放：replay() 逐行 yield；last_event_at() 取某卡最后一条事件的 ts（T8 deadline
     判定直接读它，**无需额外计时器** —— L756）。

单写窗口：所有 append 走 fcntl.flock(<path>.lock)，跨进程串行（防两个写者写坏库）。
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager

FIELDS = ("ts", "card_id", "from", "to", "event", "actor", "trace_id")
DEFAULT_PATH = os.path.expanduser("~/.mimiraether/data/state-events.jsonl")


def event_id(rec) -> str:
    """标识键 = sha1(身份字段)；ts 不参与（幂等的关键）。"""
    payload = "\x1f".join(
        str(rec.get(k, "") or "")
        for k in ("card_id", "from", "to", "event", "actor", "trace_id")
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def replay(path=None):
    """可回放：逐行 yield 合法记录；坏行跳过（不吞掉整文件）。"""
    path = path or DEFAULT_PATH
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict) and rec.get("card_id"):
                yield rec


def seen_ids(path=None) -> set:
    return {event_id(r) for r in replay(path)}


@contextmanager
def _lock(path):
    lockp = path + ".lock"
    d = os.path.dirname(lockp)
    if d:
        os.makedirs(d, exist_ok=True)
    fh = open(lockp, "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()


def append_event(rec, path=None, ts=None) -> str:
    """返回 'appended' | 'duplicate'。幂等：同 event_id 已存在 ⇒ 不落行。"""
    path = path or DEFAULT_PATH
    rec = dict(rec)
    for k in FIELDS:
        rec.setdefault(k, "")
    if ts is not None:
        rec["ts"] = ts
    if not rec.get("ts"):
        rec["ts"] = time.time()
    if not rec.get("card_id") or not rec.get("to"):
        raise ValueError("append_event: card_id / to 必填")
    eid = event_id(rec)
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with _lock(path):
        if eid in seen_ids(path):
            return "duplicate"
        line = json.dumps({k: rec[k] for k in FIELDS}, ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    return "appended"


def last_event_at(card_id, path=None):
    """某卡最后一条事件的 ts（None = 该卡无事件基线）。"""
    best = None
    for rec in replay(path):
        if rec.get("card_id") == card_id:
            try:
                t = float(rec.get("ts"))
            except (TypeError, ValueError):
                continue
            if best is None or t > best:
                best = t
    return best


def last_event_map(path=None) -> dict:
    out = {}
    for rec in replay(path):
        try:
            t = float(rec.get("ts"))
        except (TypeError, ValueError):
            continue
        cid = rec["card_id"]
        if cid not in out or t > out[cid]:
            out[cid] = t
    return out


def line_count(path=None) -> int:
    path = path or DEFAULT_PATH
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as fh:
        return sum(1 for ln in fh if ln.strip())


def _selftest() -> int:
    import tempfile

    ok = True
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "state-events.jsonl")
        base = dict(card_id="NMOCK", **{"from": "pending"}, to="in_progress",
                    event="deps_all_closed", actor="hermes", trace_id="t-mock")
        r1 = append_event(dict(base), path=p, ts=1000.0)
        r2 = append_event(dict(base), path=p, ts=2000.0)      # 同一件事 · 换 ts
        n = line_count(p)
        good = (r1 == "appended" and r2 == "duplicate" and n == 1)
        print("[selftest] idempotency(同事件重放): r1=%s r2=%s lines=%d -> %s"
              % (r1, r2, n, "PASS" if good else "FAIL"))
        ok = ok and good
        r3 = append_event(dict(base, event="produces_persisted", **{"to": "awaiting_verify"}),
                          path=p, ts=3000.0)
        lea = last_event_at("NMOCK", p)
        good = (r3 == "appended" and line_count(p) == 2 and lea == 3000.0)
        print("[selftest] replay/last_event_at: r3=%s lines=%d last_event_at=%s -> %s"
              % (r3, line_count(p), lea, "PASS" if good else "FAIL"))
        ok = ok and good
        keys = set()
        for rec in replay(p):
            keys |= set(rec.keys())
        good = keys == set(FIELDS)
        print("[selftest] 字段契约 %s -> %s" % (sorted(keys), "PASS" if good else "FAIL"))
        ok = ok and good
    print("[selftest] rc=%d" % (0 if ok else 1))
    return 0 if ok else 1


def _main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="N13 事件流（append-only · 幂等 · 可回放）")
    ap.add_argument("--path", default=DEFAULT_PATH)
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("append")
    a.add_argument("--card-id", required=True)
    a.add_argument("--from", dest="from_", default="")
    a.add_argument("--to", required=True)
    a.add_argument("--event", required=True)
    a.add_argument("--actor", required=True)
    a.add_argument("--trace-id", default="")
    a.add_argument("--ts", type=float, default=None)
    b = sub.add_parser("replay")
    c = sub.add_parser("last-event-at")
    c.add_argument("--card-id", required=True)
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if args.cmd == "append":
        verdict = append_event(
            {"card_id": args.card_id, "from": args.from_, "to": args.to,
             "event": args.event, "actor": args.actor, "trace_id": args.trace_id},
            path=args.path, ts=args.ts)
        print("append card_id=%s event=%s -> %s" % (args.card_id, args.event, verdict))
        return 0
    if args.cmd == "replay":
        for rec in replay(args.path):
            print(json.dumps(rec, ensure_ascii=False))
        print("lines=%d" % line_count(args.path))
        return 0
    if args.cmd == "last-event-at":
        v = last_event_at(args.card_id, args.path)
        print("card_id=%s last_event_at=%s" % (args.card_id, v))
        return 0 if v is not None else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(_main())
