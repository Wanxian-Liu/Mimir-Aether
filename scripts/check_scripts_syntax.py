#!/usr/bin/env python3
"""scripts/ 整树语法闸（A8 · 2026-09-18 Mimir）。

为什么：Ralph Tier-0 Gate1 此前只 py_compile 一份 TARGET_FILES 清单（cli.py / agent/*），
  scripts/ 整树不在门禁视野内 ⇒ 提交级语法死不可见。
  盘上实证（A8）：scripts/signal-deliver.py 第 28 行把行内注释写进
  os.environ.get(...) 调用内（引入者 commit 6b762b2），该文件任何调用立即
  SyntaxError: '(' was never closed —— 而同一 commit 的 tier0 仍报 PASS。

做法：ast.parse 全树扫描（**不执行、不 import** —— 本仓 scripts/ 里存在会写盘的脚本，
  import 会有副作用），任一文件语法死即 rc=1。

用法：
  python3 scripts/check_scripts_syntax.py [--root <目录>]

输出契约（供门禁与测试消费）：
  每个坏文件一行  SYNTAX-FAIL <path>:<lineno>: <msg>
  末行            SYNTAX-GATE scanned=<N> ok=<N> fail=<N> root=<root>
  退出码          0 = 全树语法 OK / 1 = 至少一处语法死 / 2 = 根目录不存在
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def iter_py(root: Path):
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        yield p


def check(root: Path) -> int:
    if not root.is_dir():
        print(f"SYNTAX-GATE root 不存在: {root}", file=sys.stderr)
        return 2

    scanned = 0
    ok = 0
    failed: list[tuple[Path, int | None, str]] = []

    for p in iter_py(root):
        scanned += 1
        try:
            ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            failed.append((p, e.lineno, e.msg))
            print(f"SYNTAX-FAIL {p}:{e.lineno}: {e.msg}")
        except UnicodeDecodeError as e:
            failed.append((p, None, f"非 UTF-8 文本: {e}"))
            print(f"SYNTAX-FAIL {p}: 非 UTF-8 文本")
        else:
            ok += 1

    print(f"SYNTAX-GATE scanned={scanned} ok={ok} fail={len(failed)} root={root}")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="scripts/ 整树语法闸（ast.parse，不执行）")
    ap.add_argument("--root", default=None, help="默认 = 本脚本所在仓的 scripts/")
    a = ap.parse_args()
    root = Path(a.root).resolve() if a.root else Path(__file__).resolve().parent
    return check(root)


if __name__ == "__main__":
    raise SystemExit(main())
