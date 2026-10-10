#!/usr/bin/env python3
"""B3 规则③ · 「产出后即刻补账」可跑检查（rc 语义，不是承诺）。

判据（单一真源）：buzz 收件箱**总行数** vs 补账台账 `inbox-processed.log` 末条 `up to N` 水位。

  rc 0 = lag == 0（账已补齐）
  rc 2 = lag > 0（欠账 —— 打印缺口行号区间；下一轮必须补账）
  rc 3 = 量具不可用（收件箱/台账缺失，或台账无 `up to N` 水位）——**不得读成 lag=0**

用法：
  python3 scripts/check_inbox_ledger_lag.py            # 默认路径
  python3 scripts/check_inbox_ledger_lag.py --json     # 机器可读
  MIMIR_BUZZ_INBOX=... MIMIR_LEDGER=... 覆盖路径
"""
import argparse
import json
import os
import re
import sys

DEFAULT_INBOX = os.path.join(os.path.expanduser("~"), ".openclaw", "data",
                             "buzz-inbox-mimir.jsonl")


def _default_ledger():
    """台账默认路径 —— **HOME 无关**解析。

    2026-10-06 修：裸 `expanduser("~")` 在 HOME != 真实家目录时（如 execute_code 沙箱
    HOME=~/.mimiraether）会拼出 `<home>/.mimiraether/logs/...` 假路径 ⇒ 误报 rc=3
    「量具不可用」（同一命令两种 rc，取决于调用环境）。
    顺序：MIMIR_LEDGER（显式覆盖，原样尊重） → MIMIR_AETHER_HOME/MIMIR_HOME → `~` 候选
    → 绝对兜底；取**第一个存在**者；全不存在 ⇒ 返回绝对兜底（走 rc=3 报缺失）。
    """
    env_ledger = os.environ.get("MIMIR_LEDGER")
    if env_ledger:
        return env_ledger
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


DEFAULT_LEDGER = _default_ledger()
HWM_SUFFIX = ".hwm"
_WM_RE = re.compile(r"up to\s+(\d+)")


def _inbox_lines(path):
    n = 0
    with open(path, "rb") as fh:
        for _ in fh:
            n += 1
    return n


def _ledger_watermark(path):
    """末条 `up to N` 水位（容忍中间行无水位）。"""
    last = None
    hits = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = _WM_RE.search(line)
            if m:
                last = int(m.group(1))
                hits += 1
    return last, hits


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default=os.environ.get("MIMIR_BUZZ_INBOX", DEFAULT_INBOX))
    ap.add_argument("--ledger", default=os.environ.get("MIMIR_LEDGER", DEFAULT_LEDGER))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if not os.path.exists(a.inbox):
        print("[rc=3] 收件箱缺失：" + a.inbox + "（量具不可用，不得读成 lag=0）")
        return 3
    if not os.path.exists(a.ledger):
        print("[rc=3] 台账缺失：" + a.ledger + "（量具不可用）")
        return 3
    total = _inbox_lines(a.inbox)
    wm, hits = _ledger_watermark(a.ledger)
    if wm is None:
        print("[rc=3] 台账无 `up to N` 水位：" + a.ledger + "（量具不可用）")
        return 3
    lag = max(0, total - wm)
    hwm_note = ""
    try:
        hp = a.ledger + HWM_SUFFIX
        if os.path.exists(hp):
            hv = open(hp, encoding="utf-8", errors="replace").read().strip()
            if hv and hv.isdigit() and int(hv) != wm:
                hwm_note = (".hwm=" + hv + " 与台账水位=" + str(wm) + " 不一致"
                            "（.hwm 非权威，以台账末条为准；两读数不可混用）")
    except Exception:
        hwm_note = ""
    if a.json:
        print(json.dumps({"inbox": a.inbox, "ledger": a.ledger, "total_lines": total,
                          "ledger_watermark": wm, "lag": lag,
                          "rc": 0 if lag == 0 else 2,
                          "watermark_entries": hits, "hwm_note": hwm_note},
                         ensure_ascii=False))
    else:
        print("inbox=" + a.inbox + " total_lines=" + str(total))
        print("ledger=" + a.ledger + " watermark=" + str(wm) + "（水位条目 " + str(hits) + " 条）")
        print("lag=" + str(lag) + hwm_note)
    if lag:
        print("[rc=2] 欠账 " + str(lag) + " 行：第 " + str(wm + 1) + "-" + str(total)
              + " 行未补账 ⇒ 处理完必须追加一行 `processed N lines (up to "
              + str(total) + ")` 到 " + a.ledger)
        return 2
    print("[rc=0] lag=0：账已补齐")
    return 0


if __name__ == "__main__":
    sys.exit(main())
