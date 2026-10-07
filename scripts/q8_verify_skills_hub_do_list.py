#!/usr/bin/env python3
"""Q8 判据 · 可复跑（复核方原样粘贴即得读数）

对象：mimir_cli/skills_hub.py::do_list()（Q8 断链修复）
读数：汇总行三分类计数 + 表格行数 + ast.parse + hub 分支正控
rc  ：0 = 判据全过；1 = 有判据不过（打印 FAIL 行）

背景见 commit e8f8c55。
"""

import ast
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/home/rayliu/src/MimirAether")
from rich.console import Console

from mimir_cli.skills_hub import do_list

ROW = re.compile(r"^\u2502\s+(\S+)\s+\u2502")


def run(src):
    c = Console(record=True, width=220, force_terminal=False)
    do_list(source_filter=src, console=c)
    txt = c.export_text()
    rows = [m.group(1) for m in (ROW.match(ln) for ln in txt.splitlines()) if m]
    summ = re.search(r"(\d+) hub-installed, (\d+) builtin, (\d+) local", txt)
    return rows, (summ.group(0) if summ else "NO SUMMARY"), txt


print("========== [1] 真跑 do_list(source_filter='all') ==========")
rows, summ, _ = run("all")
print("汇总行 :", summ)
print("表格行数:", len(rows))
print("清单非空:", bool(rows))
print()
print("========== [2] 逐分类抽查（各举实例名）==========")
for src in ("builtin", "local"):
    r, s, _ = run(src)
    print(f"--source {src}: 项数={len(r)}  汇总=({s})  实例={r[:3]}")
print()
print("========== [3] hub 分支正控（临时 lock，不碰真实状态）==========")
from tools.skills_hub import HubLockFile, hub_dir, _lock_file

tmp = Path(tempfile.mkdtemp()) / "lock.json"
tmp.write_text(json.dumps({"version": 1, "installed": {
    "delegate-subagent": {"source": "official", "trust_level": "trusted",
                          "identifier": "x/y", "install_path": "/tmp/x"}}}), encoding="utf-8")
lock = HubLockFile(path=tmp)
inst = lock.list_installed()
print("正控 lock 解析 list_installed n =", len(inst), "->", [e["name"] for e in inst])
print("正控 source/trust =", inst[0].get("source"), "/", inst[0].get("trust_level"))
print("真源 lock 路径 =", _lock_file(), "存在?", _lock_file().exists())
print("真源 lock 读数 n =", len(HubLockFile().list_installed()))
print("hub 目录 =", hub_dir(), "存在?", hub_dir().is_dir())
print()
print("========== [4] ast.parse 判据 ==========")
for f in ("mimir_cli/skills_hub.py", "tools/skills_hub.py"):
    ast.parse(open(f, encoding="utf-8").read())
    print(f + " : ast.parse OK")
print()
print("========== [5] 断链残留扫描：do_list 内是否还有幻影 import ==========")
src_txt = open("mimir_cli/skills_hub.py", encoding="utf-8").read()
seg = src_txt.split("def do_list(")[1].split("\n\n    table =")[0]
print(seg.strip())


print()
print("========== [6] rc 判定 ==========")
checks = []
checks.append(("do_list 输出清单非空", len(rows) > 0))
checks.append(("表格行数 = 49", len(rows) == 49))
checks.append(("汇总行 = 0 hub-installed, 21 builtin, 28 local",
               "0 hub-installed, 21 builtin, 28 local" in summ))
checks.append(("ast.parse x2 OK", True))
checks.append(("hub 正控 list_installed n = 1", len(inst) == 1))
for name, ok in checks:
    print(("  [OK]   " if ok else "  [FAIL] ") + name)
rc = 0 if all(ok for _, ok in checks) else 1
print("rc =", rc)
sys.exit(rc)
