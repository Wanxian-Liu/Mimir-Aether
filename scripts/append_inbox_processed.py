#!/usr/env python3
"""补账单一入口 —— 追加 `processed N lines (up to M)` 并**同步 `.hwm`**（B3 规则③ 缺口的治本件）。

背景（2026-10-06 行 229 实测）：
  巡检 `~/.hermes/scripts/patrol_scan.py` L208-214 的不变量 = `wc -l 台账 == 台账.hwm`
  （`rec = "ok" if (hwm < 0 or led == hwm) else f"⚠陈旧水位(ledger={led} hwm={hwm})"`）。
  而**补账此前无生产者脚本** ⇒ 每次手工 append 只动台账、不动 `.hwm` ⇒ 不变量必漂移
  ⇒ 巡检报「⚠陈旧水位」⇒ 幻影告警再次投回本方（B3 规则③ 要治的正是这类幻影积压）。

用法：
  python3 scripts/append_inbox_processed.py -m "…" --up-to 229
  python3 scripts/append_inbox_processed.py -m "…" --up-to 229 --dry-run
  python3 scripts/append_inbox_processed.py --sync-hwm

rc 语义：
  0 = 已写入（或 dry-run 通过）
  2 = 写入失败（含 flock / .hwm 同步失败）—— **不得当作已补账**
  3 = 参数/量具不可用（台账缺失、--up-to 非整数、缺 -m）
"""
from __future__ import annotations

import argparse
import fcntl
import os
import re
import sys
import time


def _default_ledger() -> str:
    """台账路径 —— HOME 无关解析（与 check_inbox_ledger_lag.py 同序，避免沙箱假路径）。"""
    env = os.environ.get("MIMIR_LEDGER")
    if env:
        return env
    cands = []
    for k in ("MIMIR_AETHER_HOME", "MIMIR_HOME"):
        v = os.environ.get(k)
        if v:
            cands.append(os.path.join(v, "logs", "inbox-processed.log"))
    cands.append(os.path.expanduser("~/.mimiraether/logs/inbox-processed.log"))
    cands.append(os.path.join(os.path.expanduser("~"), ".mimiraether",
                             "logs", "inbox-processed.log"))
    for c in cands:
        if os.path.exists(c):
            return c
    return cands[-1]


def _count_lines(p: str) -> int:
    with open(p, "rb") as fh:
        return sum(1 for _ in fh)


def _last_watermark(ledger: str) -> int:
    last = 0
    try:
        with open(ledger, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.search(r"up to\s+(\d+)", line)
                if m:
                    last = int(m.group(1))
    except Exception:
        return 0
    return last


def sync_hwm(ledger: str, dry_run: bool = False):
    """把 `<ledger>.hwm` 对齐为台账当前行数。返回 (行数, 旧 hwm)。"""
    n = _count_lines(ledger)
    hwm_path = ledger + ".hwm"
    old = -1
    if os.path.exists(hwm_path):
        try:
            old = int(open(hwm_path, encoding="utf-8").read().strip())
        except Exception:
            old = -1
    if not dry_run:
        tmp = hwm_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(str(n) + chr(10))
        os.replace(tmp, hwm_path)
    return n, old


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message", default="", help="台账行正文（禁含换行）")
    ap.add_argument("--up-to", default=None, help="收件箱游标（写入 up to N）")
    ap.add_argument("--ledger", default=_default_ledger())
    ap.add_argument("--sync-hwm", action="store_true", help="只对齐 .hwm，不追加行")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    if not os.path.exists(a.ledger):
        print("[rc=3] 台账缺失：" + a.ledger)
        return 3

    if a.sync_hwm:
        n, old = sync_hwm(a.ledger, a.dry_run)
        print("hwm: %s -> %s (dry_run=%s)" % (old, n, a.dry_run))
        return 0

    if not a.message.strip():
        print("[rc=3] 缺 -m/--message")
        return 3
    if chr(10) in a.message or chr(13) in a.message:
        print("[rc=3] message 不得含换行（台账一行一条）")
        return 3
    if a.up_to is None or not re.fullmatch(r"\d+", str(a.up_to)):
        print("[rc=3] --up-to 必须是非负整数")
        return 3

    up = int(a.up_to)
    delta = up - _last_watermark(a.ledger)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    line = "%s processed %d lines (up to %d) %s%s" % (stamp, delta, up, a.message, chr(10))

    if a.dry_run:
        n, old = sync_hwm(a.ledger, True)
        print("[dry-run] 将追加：" + line.strip()[:200])
        print("[dry-run] hwm: %s -> %s" % (old, n + 1))
        return 0

    try:
        with open(a.ledger, "a", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)      # 单写窗口（跨进程）
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception as e:                                # 出声，不静默
        print("[rc=2] 追加失败：" + type(e).__name__ + ": " + str(e))
        return 2

    try:
        n, old = sync_hwm(a.ledger, False)
    except Exception as e:
        print("[rc=2] .hwm 同步失败：" + type(e).__name__ + ": " + str(e)
              + " ⇒ 台账已追加但 hwm 未对齐，下一次巡检会报「陈旧水位」")
        return 2
    print("[rc=0] 已追加（台账 %d 行）· hwm: %s -> %d" % (n, old, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
