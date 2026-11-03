#!/usr/bin/env python3
"""台账「待复核」存量按判据形态分类（可复跑 · v2 口径收窄）。

为什么有 v2（2026-11-03）：
  v1 扫「行内含 待复核/待 L2/L1 已自证」⇒ 149 命中，与台账 2026-11-02 T1-3 节
  记的 48 行不符。差异根因 = v1 把**叙述行**也算成任务行，例如
  L333「不等价于完工——L2 由琬弦复算后回填…」是解释句，不是一个待办任务。
  ⇒ 任务行口径收紧为下面两类之一：
     T1 表格任务行：以 `|` 开头且首列是数字或 **数字**/字母编号（`| 39 |`、`| **C2** |`、`| 61b |`）
     T2 状态行    ：以 `- 状态` / `- **状态**` 开头的条目行
  其余命中行一律记为 N（叙述/注释），不计入任务存量。

用法：
  python3 ledger_c_class_scan.py --breakdown      # 三种形状各多少行（对账 v1↔v2）
  python3 ledger_c_class_scan.py --c-only         # 只列 C 类任务行
  python3 ledger_c_class_scan.py --since 2026-10-03 --c-only
"""
import argparse
import os
import pwd
import re
import sys
from pathlib import Path

# 真实用户 home：不受 HOME 环境变量影响（execute_code 沙箱里 HOME=~/.mimiraether，
# 用 expanduser 会把台账解析到 ~/.mimiraether/wiki/... 而假失败）
REAL_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)

LEDGER = REAL_HOME / "wiki/concepts/四方任务总台账.md"

# 2026-11-02 T1-3 已核定的 A 类行号（产物在盘，可被复核方直接跑）
HARD_A = {98, 99, 108, 239, 248, 260, 268, 311, 320, 329, 339, 351, 1629, 2564}

HIT = re.compile(r"待复核|待 L2|L1 已自证")
SECTION = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})")
TABLE_TASK = re.compile(r"^\|\s*\*{0,2}[0-9]+[a-z]?\*{0,2}\s*\|")
STATUS_LINE = re.compile(r"^-\s*\*{0,2}状态\*{0,2}\s*[：:]")


def shape(line):
    s = line.strip()
    if TABLE_TASK.match(s):
        return "T1"
    if STATUS_LINE.match(s):
        return "T2"
    return "N"


def scan(ledger=LEDGER):
    lines = ledger.read_text(encoding="utf-8").splitlines()
    cur_date = ""
    rows = []
    for i, ln in enumerate(lines, 1):
        m = SECTION.match(ln)
        if m:
            cur_date = m.group(1)
            continue
        if HIT.search(ln):
            rows.append((i, cur_date, shape(ln), ln.strip()))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--c-only", action="store_true")
    ap.add_argument("--breakdown", action="store_true")
    ap.add_argument("--since", default="")
    ap.add_argument("--with-status", action="store_true",
                    help="把 T2（- 状态: 行）也算进来；默认只算 T1 表格任务行（与 2026-11-02 T1-3 的 48 行口径一致）")
    ap.add_argument("--ledger", default=str(LEDGER))
    a = ap.parse_args()

    rows = scan(Path(a.ledger))
    shapes = ("T1", "T2") if a.with_status else ("T1",)

    if a.breakdown:
        n = {"T1": 0, "T2": 0, "N": 0}
        for _, _, sh, _ in rows:
            n[sh] += 1
        print(f"raw hits={len(rows)}  T1(table task)={n['T1']}  "
              f"T2(status line)={n['T2']}  N(narrative)={n['N']}")
        print(f"task rows = T1+T2 = {n['T1'] + n['T2']}")
        a_rows = [i for i, _, sh, _ in rows if i in HARD_A and sh in ("T1", "T2")]
        print(f"A(白名单∩任务行)={len(a_rows)}  "
              f"C = {n['T1'] + n['T2'] - len(a_rows)}")
        drift = sorted(HARD_A - {i for i, _, _, _ in rows})
        if drift:
            print(f"[WARN] A 白名单行号已不在命中集（台账漂移）: {drift}")
        return 0

    tasks = [(i, d, t) for i, d, sh, t in rows if sh in shapes]
    if a.since:
        tasks = [x for x in tasks if x[1] >= a.since]
    cls = [(i, d, t, "A" if i in HARD_A else "C") for i, d, t in tasks]
    n_a = sum(1 for x in cls if x[3] == "A")
    n_c = sum(1 for x in cls if x[3] == "C")
    print(f"task_rows={len(cls)} A={n_a} C={n_c}"
          + (f" (since>={a.since})" if a.since else ""))
    print("-" * 70)
    for i, d, t, k in cls:
        if a.c_only and k != "C":
            continue
        print(f"{k} L{i:<5} {d}  {t[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
