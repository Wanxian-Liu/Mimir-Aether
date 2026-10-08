#!/usr/bin/env python3
"""RS17 探针：只扫 trajectory 的 **首行**（session_start），避免扫到本 run 自己的工具参数。
用法: python3 probe_firstline_wake.py <needle>   → 打印命中文件数
"""
import os
import pathlib
import sys

NEEDLE = sys.argv[1] if len(sys.argv) > 1 else ""
# 2026-10-08 修（同类风险全量扫 · 入仓前清理）：默认根走 $HOME 相对（本地恒等）。
ROOT = pathlib.Path(
    os.environ.get("MIMIR_AETHER_HOME", os.path.expanduser("~/.mimiraether"))
) / "data" / "trajectories" / "2026-09-23"
hits = 0
for f in sorted(ROOT.glob("*.jsonl")):
    try:
        first = f.open(encoding="utf-8", errors="replace").readline()
    except Exception:
        continue
    if NEEDLE and NEEDLE in first:
        hits += 1
print(hits)
