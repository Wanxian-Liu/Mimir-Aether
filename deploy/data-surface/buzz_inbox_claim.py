# -*- coding: utf-8 -*-
"""buzz_inbox_claim.py — Buzz 收件箱「认领即原子推进」（TOCTOU 修复 · 2026-10-07 · T7-F1）

问题（Hermes L2 现场复现）：同一派单行（信箱游标 42）被两个 run 并行消费——
run 9f313cb9（trigger_source=api，02:44:41→03:07:21）与 run 5ee412bb
（trigger_source=buzz-watcher，02:45:01→02:55:56）。根因 = 消费侧「读取」与
「推进游标」之间无原子认领步（watcher 全序列无 flock；唯一"锁"是派发之后才创建
的存在性文件 ⇒ TOCTOU 窗口 = 整段决策+派发耗时）。

本脚本 = 认领的唯一原子出口（flock 关键区内 read → 比对行号 → 原子写回）：
  reserve  认领 [start,end] 并把 dispatched 原子抬到 end（认领即推进）
  abort    派发失败回滚（仅当 dispatched 仍 == 我的 end 且 offset < end ⇒ 无人推进）
  commit   认领落地（清 claim 记录 + 写 claim 台账行）
  check    消费者自检「这一行我能不能碰」：0=可 / 2=他人持有 / 3=已处理
  show     只读三游标 + 当前 claim（零写入）

并发语义：flock 独占（claim 锁，跨进程）；同一行只能被一个 owner 认领。
状态文件默认派生自 dispatched 路径（sandbox 只覆写 DISPATCHED 即全隔离——
避免「整仓 pytest 跑一次把真实派发游标清 0」那一类越界写，见 G2 勘误）。

退出码（三态可判）：
  0 成功   1 reserve 无增量（幂等）   2 被他人持有（HELD）/ owner 不匹配   3 环境错误
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import socket
import sys
import time

# 2026-10-08 修（同类风险全量扫 · 入仓前清理）：默认值不再写死家目录，改 $HOME 相对。
# 本地恒等（开发机家目录不变）；CI 上家目录不同 ⇒ 不再指向不存在的路径。
_OPENCLAW_DATA = os.path.expanduser("~/.openclaw/data")
INBOX = os.environ.get("BUZZ_INBOX_MIMIR", _OPENCLAW_DATA + "/buzz-inbox-mimir.jsonl")
OFFSET = os.environ.get("BUZZ_INBOX_MIMIR_OFFSET", _OPENCLAW_DATA + "/buzz-inbox-mimir.offset")
DISPATCHED = os.environ.get("BUZZ_INBOX_MIMIR_DISPATCHED", _OPENCLAW_DATA + "/buzz-inbox-mimir.dispatched")
CLAIM_FILE = os.environ.get("BUZZ_INBOX_MIMIR_CLAIM_FILE", DISPATCHED + ".claim.json")
CLAIM_LOCK = os.environ.get("BUZZ_INBOX_MIMIR_CLAIM_LOCK", DISPATCHED + ".claim.lock")
CLAIM_LOG = os.environ.get("BUZZ_INBOX_MIMIR_CLAIM_LOG", DISPATCHED + ".claim.log")
# R-1 修（2026-10-07 · 第 2 路唤醒异源 harness Arm1 实测 rc0=2）：认领记录的 pid 是
# **reserve 这个短命 CLI 进程**，reserve 一返回即退出 ⇒ 用 pid 存活当接管闸门 ⇒ 任何
# 后到者都读成 alive=False 并接管**活**认领 = 双进入。存活判据改 TTL（ts 龄），
# pid 仅作诊断字段。TTL 只覆盖 reserve→commit 窗口（秒级），默认 300s。
CLAIM_TTL_SEC = int(os.environ.get("BUZZ_INBOX_MIMIR_CLAIM_TTL_SEC", "300"))


def log_line(msg):
    try:
        os.makedirs(os.path.dirname(CLAIM_LOG) or ".", exist_ok=True)
        with open(CLAIM_LOG, "a") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def count_lines(path):
    n = 0
    try:
        with open(path, "rb") as f:
            for _ in f:
                n += 1
    except OSError:
        return 0
    return n


def read_int(path, default=0):
    try:
        with open(path, "r") as f:
            raw = f.read().strip()
        return int(raw) if raw else default
    except (ValueError, OSError):
        return default


def write_int(path, val):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w") as f:
        f.write("%d\n" % val)
        f.flush()
        os.fsync(f.fileno())


def read_claim():
    try:
        with open(CLAIM_FILE, "r") as f:
            o = json.load(f)
        return o if isinstance(o, dict) else {}
    except (ValueError, OSError):
        return {}


def write_claim(o):
    d = os.path.dirname(CLAIM_FILE)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = CLAIM_FILE + ".tmp.%d" % os.getpid()
    with open(tmp, "w") as f:
        json.dump(o, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, CLAIM_FILE)   # 原子替换：读者永不见半截 JSON


def drop_claim():
    try:
        os.unlink(CLAIM_FILE)
    except OSError:
        pass


def pid_alive(pid, host, myhost):
    """**仅诊断用途，不参与认领闸门**（R-1：reserve 是短命进程，pid 存活非有效活性信号）。

    同宿主才查 pid；跨宿主一律视为存活。"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if not host or host != myhost:
        return True
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def is_open(claim, offset):
    """未闭环 = 有记录 且 区间末端 > offset（尚未处理完）。"""
    if not claim:
        return False
    try:
        return int(claim.get("end", 0)) > offset
    except (TypeError, ValueError):
        return False


def readings():
    return {"total": count_lines(INBOX), "offset": read_int(OFFSET),
            "dispatched": read_int(DISPATCHED)}


def fmt(r):
    return "total=%d offset=%d dispatched=%d lag=%d" % (
        r["total"], r["offset"], r["dispatched"], r["total"] - r["offset"])


class Lock:
    """跨进程互斥（flock 独占）——所有状态读写都在关键区内。"""

    def __init__(self, path):
        self.path = path
        self.fh = None

    def __enter__(self):
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.fh = open(self.path, "a+")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        try:
            fcntl.flock(self.fh, fcntl.LOCK_UN)
        finally:
            self.fh.close()
        return False


def cmd_reserve(a):
    myhost = socket.gethostname()
    with Lock(CLAIM_LOCK):
        r = readings()
        # -- 轮转/截断：旧游标 > 新总行数 ⇒ 行号纪元重置（出声，毋静默）--
        max_old = max(r["offset"], r["dispatched"])
        if r["total"] < max_old:
            print("ROTATION/TRUNCATION: total %d < max(offset=%d, dispatched=%d) ⇒ 双游标归零"
                  % (r["total"], r["offset"], r["dispatched"]), file=sys.stderr)
            write_int(OFFSET, 0)
            write_int(DISPATCHED, 0)
            drop_claim()
            log_line("ROTATION total=%d max_old=%d owner=%s" % (r["total"], max_old, a.owner))
            r = readings()

        # 顺序关键（2026-10-07 差分实测）：先判「他人持有」再判「无增量」——
        # 反过来的话，第二个消费者会被读成 rc=1「无增量」，把 HELD 吞成静默
        # （可观测性缺口：无人知道有兄弟 run 正在处理同一区间）。
        claim = read_claim()
        if is_open(claim, r["offset"]):
            other = str(claim.get("owner", "?"))
            if other != a.owner:
                age = int(time.time() - float(claim.get("ts", 0) or 0))
                if age < CLAIM_TTL_SEC:
                    print("HELD by %s (age=%ds < ttl=%ds pid=%s) 区间 %s..%s ⇒ 不重复认领"
                          % (other, age, CLAIM_TTL_SEC, claim.get("pid"),
                             claim.get("start"), claim.get("end")))
                    log_line("HELD owner=%s holder=%s range=%s..%s age=%ds"
                             % (a.owner, other, claim.get("start"), claim.get("end"), age))
                    return 2
                # F-A 修（2026-10-07 · 第 2 路唤醒复核 Arm4）：**TTL 过期**的认领 ⇒ 真接管
                # 同一区间。原实现只打印「视为死认领」却继续走到 NOTHING 分支 ⇒ reserve
                # 已把 dispatched 抬到 end，start=end+1 ⇒ rc=1「无增量」，接管分支**不可达**
                # ⇒ 调用方在派发前崩溃（SIGKILL 不跑 abort）的区间**无自动出路（死信窗口）**。
                # 判据：age >= CLAIM_TTL_SEC（**不用 pid 存活**——见文件头 R-1 说明）。
                try:
                    t_start, t_end = int(claim.get("start", 0)), int(claim.get("end", 0))
                except (TypeError, ValueError):
                    print("STALE-MISMATCH rc=2: 认领记录区间不可解析（不假装接管）: %r"
                          % (claim,), file=sys.stderr)
                    return 2
                rec = {"owner": a.owner, "start": t_start, "end": t_end, "pid": os.getpid(),
                       "host": myhost, "ts": time.time(), "prev_dispatched": r["dispatched"],
                       "phase": "reserved", "takeover_from": other,
                       "takeover_reason": "ttl-expired"}
                write_claim(rec)
                write_int(DISPATCHED, t_end)
                print("TAKEOVER %s %d %d (from=%s age=%ds >= ttl=%ds)"
                      % (a.owner, t_start, t_end, other, age, CLAIM_TTL_SEC))
                log_line("TAKEOVER owner=%s from=%s range=%d..%d age=%ds ttl=%ds"
                         % (a.owner, other, t_start, t_end, age, CLAIM_TTL_SEC))
                return 0
            else:
                claim["pid"] = os.getpid()
                claim["ts"] = time.time()
                write_claim(claim)
                print("CLAIMED %s %s %s (re-entry)" % (a.owner, claim.get("start"), claim.get("end")))
                return 0

        start = max(r["offset"], r["dispatched"]) + 1
        end = r["total"]
        if end < start:
            if not a.quiet:
                print("NOTHING 无增量: %s" % fmt(r))
            return 1

        rec = {"owner": a.owner, "start": start, "end": end, "pid": os.getpid(),
               "host": myhost, "ts": time.time(),
               "prev_dispatched": r["dispatched"], "phase": "reserved"}
        write_claim(rec)               # ---- 关键区：原子写回（认领即推进）----
        write_int(DISPATCHED, end)
        log_line("RESERVE owner=%s range=%d..%d prev_dispatched=%d"
                 % (a.owner, start, end, r["dispatched"]))
        if not a.quiet:
            print("CLAIMED %s %d %d prev_dispatched=%d | %s"
                  % (a.owner, start, end, r["dispatched"], fmt(r)))
        return 0


def cmd_abort(a):
    with Lock(CLAIM_LOCK):
        claim = read_claim()
        if claim.get("owner") != a.owner:
            print("ABORT-REFUSED rc=2 owner 不匹配: claim=%s caller=%s"
                  % (claim.get("owner"), a.owner), file=sys.stderr)
            return 2
        end = int(claim.get("end", 0) or 0)
        prev = int(claim.get("prev_dispatched", 0) or 0)
        r = readings()
        if r["dispatched"] == end and r["offset"] < end:
            write_int(DISPATCHED, prev)      # 无人推进 ⇒ 安全回滚，下次重试
            drop_claim()
            log_line("ABORT-ROLLBACK owner=%s range=%s..%d dispatched=%d->%d"
                     % (a.owner, claim.get("start"), end, end, prev))
            print("ROLLED-BACK %s dispatched %d->%d（未派发，下次重试）" % (a.owner, end, prev))
        else:
            drop_claim()
            log_line("ABORT-KEEP owner=%s range=%s..%d dispatched=%d offset=%d（他人已推进）"
                     % (a.owner, claim.get("start"), end, r["dispatched"], r["offset"]))
            print("KEPT-PROGRESS %s（dispatched=%d offset=%d 已推进 ⇒ 不回滚）"
                  % (a.owner, r["dispatched"], r["offset"]))
        return 0


def cmd_commit(a):
    with Lock(CLAIM_LOCK):
        claim = read_claim()
        if claim and claim.get("owner") != a.owner:
            print("COMMIT-REFUSED rc=2 owner 不匹配: claim=%s caller=%s"
                  % (claim.get("owner"), a.owner), file=sys.stderr)
            return 2
        drop_claim()
        log_line("COMMIT owner=%s range=%s..%s" % (a.owner, claim.get("start"), claim.get("end")))
        print("COMMITTED %s %s..%s | %s" % (a.owner, claim.get("start"), claim.get("end"), fmt(readings())))
        return 0


def cmd_check(a):
    """消费者自检：这一行我能不能碰。0=可 / 2=已被派发或他人持有 / 3=已处理（跳过）。

    F-B 修（2026-10-07 · 第 2 路唤醒复核）：原判据只看 offset ⇒ claim 已 commit、
    dispatched=5、offset=0 时对行 5 返 rc=0「OK」⇒ 被 API 直连唤醒的 run 若用 check
    自检，仍会重复处理 watcher 已派出的行（跨通道覆盖不完整）。现补 dispatched 门：
    行号 ≤ dispatched 且非本 owner 持有 ⇒ rc=2（该行已被派发给别的消费者）。
    """
    with Lock(CLAIM_LOCK):
        r = readings()
        claim = read_claim()
        line = a.line
        holder = str(claim.get("owner", "")) if claim else ""
        try:
            c_start, c_end = int(claim.get("start", 0)), int(claim.get("end", 0))
        except (TypeError, ValueError):
            c_start, c_end = 0, 0
        mine = (holder == a.owner and c_start <= (line or 0) <= c_end)
        if line is not None:
            if line <= r["offset"]:
                print("ALREADY-PROCESSED line=%d offset=%d ⇒ 跳过" % (line, r["offset"]))
                return 3
            if line <= r["dispatched"] and not mine:
                print("LINE-DISPATCHED line=%d dispatched=%d holder=%s ⇒ 跳过（已被派发未处理）"
                      % (line, r["dispatched"], holder or "unknown"))
                return 2
        if is_open(claim, r["offset"]) and holder != a.owner:
            if line is None or c_start <= line <= c_end:
                print("LINE-HELD line=%s holder=%s range=%s..%s ⇒ 跳过"
                      % (line, holder, c_start, c_end))
                return 2
        print("OK line=%s | %s" % (line, fmt(r)))
        return 0


def cmd_show(a):
    r = readings()
    claim = read_claim()
    print(fmt(r))
    print("claim=%s" % (json.dumps(claim, ensure_ascii=False) if claim else "(none)"))
    print("重跑命令: python3 " + os.path.abspath(__file__) + " show")
    print("复算数字: total=%d offset=%d dispatched=%d claim=%s"
          % (r["total"], r["offset"], r["dispatched"], claim.get("owner", "none")))
    return 0


def main():
    ap = argparse.ArgumentParser(description="Buzz 收件箱原子认领")
    ap.add_argument("cmd", choices=["reserve", "abort", "commit", "check", "show"])
    ap.add_argument("--owner", default="")
    ap.add_argument("--line", type=int, default=None)
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args()
    if a.cmd != "show" and not a.owner:
        print("rc=3 --owner 必填（认领必须有主）", file=sys.stderr)
        return 3
    if a.cmd == "reserve":
        return cmd_reserve(a)
    if a.cmd == "abort":
        return cmd_abort(a)
    if a.cmd == "commit":
        return cmd_commit(a)
    if a.cmd == "check":
        return cmd_check(a)
    return cmd_show(a)


if __name__ == "__main__":
    sys.exit(main())
