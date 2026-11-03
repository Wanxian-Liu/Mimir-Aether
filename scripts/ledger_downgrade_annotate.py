"""给台账 C 类「我方行」追加降级标注（**不改原状态值**，只在行尾追加可审计标注）。

设计取舍（2026-11-03）：
  为什么追加而不是覆盖状态值：
    覆盖 = 抹掉「当年写过什么」，台账可追溯性就断了（AGENTS §5.5 审计留痕不可裁剪）。
    追加 = 原文保留 + 处置可见，任何人可看出「原态 → 何日 → 何处置 → 依据」。
  为什么只动我方行：
    台账明令「禁自判他方历史有效性」。owner 非 Mimir 的行只登记、不动。

判定：
  目标行 = ledger_c_class_scan.py 报的 C 类行 ∩ 行内含 "Mimir"
  幂等   = 行内已含 MARK 则跳过（重复跑 changed=0）

两向自检（--selftest）：
  正控：未标注的我方行 → 必须追加
  负控 A：已标注行 → 必须跳过（幂等）；负控 B：他席行 → 必须跳过

用法：
  python3 ledger_downgrade_annotate.py --selftest
  python3 ledger_downgrade_annotate.py            # dry-run
  python3 ledger_downgrade_annotate.py --apply    # 真写
"""
import argparse
import os
import pwd
import re
import subprocess
import sys
from pathlib import Path

REAL_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)
LEDGER = REAL_HOME / "wiki/concepts/四方任务总台账.md"
SCAN = REAL_HOME / ".mimiraether/scripts/ledger_c_class_scan.py"
PY = str(REAL_HOME / "src/MimirAether/.venv/bin/python3")

MARK = "2026-11-03 降级：无 L2 通道"
SUFFIX = (" " + MARK + "（依据：scripts/ledger_receipt_backfill.py 实测行内证据 0 条 /"
          " 锁版 sha 已不可解析 ⇒ 该行待复核状态永不可被复算通过）")


def c_line_numbers():
    out = subprocess.run([PY, str(SCAN), "--c-only"],
                         capture_output=True, text=True, timeout=180).stdout
    nums = []
    for ln in out.splitlines():
        m = re.match(r"^C L(\d+)\s", ln)
        if m:
            nums.append(int(m.group(1)))
    return nums


def annotate_line(line):
    """返回 (new_line, action)。action ∈ {append, skip_marked, skip_foreign}"""
    if MARK in line:
        return line, "skip_marked"
    if "Mimir" not in line:
        return line, "skip_foreign"
    if "待复核" not in line and "待 L2" not in line and "L1 已自证" not in line:
        return line, "skip_foreign"
    return line.rstrip() + SUFFIX, "append"


def run(apply=False, lines_override=None):
    lines = (lines_override if lines_override is not None
             else LEDGER.read_text(encoding="utf-8").splitlines())
    nums = c_line_numbers() if lines_override is None else range(1, len(lines) + 1)
    changed = 0
    stats = {"append": 0, "skip_marked": 0, "skip_foreign": 0}
    samples = []
    for n in nums:
        if not (0 < n <= len(lines)):
            continue
        new, act = annotate_line(lines[n - 1])
        stats[act] += 1
        if act == "append":
            if len(samples) < 3:
                samples.append(n)
            lines[n - 1] = new
            changed += 1
    if apply and lines_override is None and changed:
        LEDGER.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed, stats, samples


def selftest():
    s_pos = "- 状态：L1 已自证 · 待异源复核（Mimir 执行）"
    n_pos, a_pos = annotate_line(s_pos)
    s_dup = s_pos + SUFFIX
    n_dup, a_dup = annotate_line(s_dup)
    s_for = "- 状态：L1 已自证 · 待异源复核（Hermes 执行）"
    n_for, a_for = annotate_line(s_for)
    ok = (a_pos == "append" and a_dup == "skip_marked"
          and a_for == "skip_foreign" and n_dup == s_dup and n_for == s_for)
    print("正控（我方未标注）:", a_pos, "追加", len(n_pos) - len(s_pos), "字符")
    print("负控A（已标注·幂等）:", a_dup)
    print("负控B（他席行）:", a_for)
    print("VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    changed, stats, samples = run(apply=a.apply)
    print(f"{'APPLIED' if a.apply else 'DRY-RUN'} changed={changed} "
          f"append={stats['append']} skip_foreign={stats['skip_foreign']} "
          f"skip_marked={stats['skip_marked']}")
    print("样例行号:", samples)
    if not a.apply:
        print("（未写盘；确认后加 --apply）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
