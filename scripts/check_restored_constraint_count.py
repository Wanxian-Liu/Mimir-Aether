#!/usr/bin/env python3
"""E7 · 护栏验收判据（精确版）——只数 behavioral_constraints 内 source=="restored-20261024" 的条数。

为什么换掉旧命令：旧命令 `grep -c '量具存活' persistent.json` 实测 = 4
（同一措辞在 decisions/patterns/其它字段里也有）⇒ 期望 1 的判据**恒不过**或**误判**，
不是量具失灵，是判据错。旧命令**作废**（见 2026-10-24 执行回执 §E7）。

输出：一个整数（期望 1）
用法：~/src/MimirAether/.venv/bin/python3 ~/.mimiraether/scripts/check_restored_constraint_count.py
"""
import json
import os
import sys

DATA = os.environ.get("MIMIR_HOME") or os.path.expanduser("~/.mimiraether")
PATH = os.path.join(DATA, "data", "persistent.json")
WANT_SOURCE = "restored-20261024"


def main() -> int:
    try:
        with open(PATH, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print("ERROR %s" % exc)
        return 2
    items = ((state.get("memory") or {}).get("behavioral_constraints")) or []
    n = sum(
        1
        for it in items
        if isinstance(it, dict) and str(it.get("source") or "") == WANT_SOURCE
    )
    print(n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
