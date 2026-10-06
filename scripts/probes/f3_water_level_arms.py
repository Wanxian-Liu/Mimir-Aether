#!/usr/bin/env python3
"""F3 · 水位阈值出声 · 两臂复现探针（第 9 单 · A 档 #4 · 2026-10-07）。

只做一件事：用**合成 home** 复现回执里的两臂读数（不碰真记忆 / 真台账）：
  臂 A 越阈：记忆 7100/8000 = 88.8% > 85%  => rc=2 · 首行 `WATER_LEVEL: OVER over=1`
           连跑两次 => 台账行数 1 -> 2（append-only，不是覆盖改写）
  臂 B 未越阈：记忆 100/8000 = 1.3%       => rc=0 · 首行 `WATER_LEVEL: OK over=0` · 不写台账

用法（两环境各跑一遍）：
    env HOME=/home/rayliu python3 scripts/probes/f3_water_level_arms.py
    env HOME=/home/rayliu TMPDIR=/tmp python3 scripts/probes/f3_water_level_arms.py
rc：0 = 两臂全部符合预期；1 = 有臂不符（打印逐臂读数）。
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_water_level.py"
LEDGER = "water_level_events.jsonl"


def make_home(root, mem_chars, total, threshold=300000):
    root.mkdir(parents=True, exist_ok=True)
    (root / "memories").mkdir(exist_ok=True)
    (root / "data" / "ops").mkdir(parents=True, exist_ok=True)
    (root / "memories" / "MEMORY.md").write_text("x" * mem_chars, encoding="utf-8")
    (root / "data" / "ops" / "last_context_usage.json").write_text(
        json.dumps({"total_tokens": total, "threshold_tokens": threshold,
                    "caliber": "synth@1M/thr=%d" % threshold, "writer_kind": "main"}),
        encoding="utf-8")
    return root


def run(home):
    env = dict(os.environ)
    env.setdefault("HOME", str(pathlib.Path.home()))
    return subprocess.run([sys.executable, str(SCRIPT), "--home", str(home)],
                          capture_output=True, text=True, env=env)


def ledger_lines(home):
    f = home / "data" / "ops" / LEDGER
    return len([ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]) if f.exists() else 0



def main():
    tmpdir = os.environ.get("TMPDIR") or None
    results = []

    def rec(label, want, got):
        ok = want == got
        results.append(ok)
        print("ARM %s %s: 期望 %s / 实得 %s" % ("PASS" if ok else "FAIL", label, want, got))

    with tempfile.TemporaryDirectory(prefix="f3_arms_", dir=tmpdir) as td:
        base = pathlib.Path(td)
        # ---- 臂 A：越阈 ----
        a = make_home(base / "a", mem_chars=7100, total=1000)
        r1 = run(a)
        a_first = r1.stdout.splitlines()[0].strip() if r1.stdout.strip() else ""
        rec("A1 越阈 rc", 2, r1.returncode)
        rec("A2 首行明示 OVER", "WATER_LEVEL: OVER over=1", a_first)
        n1 = ledger_lines(a)
        rec("A3 台账新行 1", 1, n1)
        r2 = run(a)
        n2 = ledger_lines(a)
        rec("A4 连跑两次 => 行数 +1（append-only）", "1->2", "%d->%d" % (n1, n2))
        rec("A5 第二次 rc", 2, r2.returncode)
        # ---- 臂 B：未越阈（孪生对照 · 防恒真）----
        b = make_home(base / "b", mem_chars=100, total=1000)
        rb = run(b)
        b_first = rb.stdout.splitlines()[0].strip() if rb.stdout.strip() else ""
        rec("B1 未越阈 rc", 0, rb.returncode)
        rec("B2 首行明示 OK", "WATER_LEVEL: OK over=0", b_first)
        rec("B3 未越阈不写台账", 0, ledger_lines(b))

    ok = all(results)
    print("F3_ARMS: %s (%d/%d)" % ("ALL PASS" if ok else "HAS FAILURE", sum(results), len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
