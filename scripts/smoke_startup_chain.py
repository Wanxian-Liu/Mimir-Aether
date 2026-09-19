"""S1 启动链冒烟（2026-09-19 · 刘哥批）—— 真重启**之前**在干净子进程里验启动链。

为什么要单独一个冒烟：
    盘上读数（09-19）：gateway `MainPID` 启动 `09-18 13:11:23` < repo HEAD `09-18 22:30:07`
    ⇒ **17 个 commit 未加载**，其中含断管批1（`mimicore.config` → `mimir_cli.model_config`）。
    运行进程内存里还持有旧模块，所以「现在没事」；**下一次重启才是断管后启动链的首个真实
    检验** —— 「上次能跑」不能作为判据（旧路径在盘上已不存在）。

本脚本只读：不绑端口、不起服务、不写运行态（仅 import + find_spec）。
在**独立子进程**里跑（不 import 运行中的 gateway 对象），失败即 exit 1。

用法：
    .venv/bin/python3 scripts/smoke_startup_chain.py
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 迁移后的正路（断管批1 的目标）
MUST_IMPORT = [
    "mimir_cli.model_config",
    "agent.core_loop",
    "agent.context_compressor",
    "tools.memory_tool",
    "gateway.run",
]

# 已解绑的旧域（批1/批3）：盘上应已不存在（find_spec -> None）
MUST_BE_GONE = [
    "mimicore.config",
]


def _check_imports(mods: List[str]) -> List[Tuple[str, bool, str]]:
    out: List[Tuple[str, bool, str]] = []
    for name in mods:
        try:
            importlib.import_module(name)
            out.append((name, True, "imported"))
        except Exception as exc:  # noqa: BLE001 - 冒烟要如实报告任意异常
            out.append((name, False, f"{type(exc).__name__}: {exc}"))
    return out


def _check_gone(mods: List[str]) -> List[Tuple[str, bool, str]]:
    out: List[Tuple[str, bool, str]] = []
    for name in mods:
        try:
            spec = importlib.util.find_spec(name)
        except Exception as exc:  # noqa: BLE001
            out.append((name, True, f"find_spec raised {type(exc).__name__} (treated as gone)"))
            continue
        out.append((name, spec is None, "gone" if spec is None else f"STILL RESOLVES -> {spec.origin}"))
    return out


def main(argv: List[str] | None = None) -> int:
    argparse.ArgumentParser(description="S1 启动链冒烟（只读）").parse_args(argv)
    results = _check_imports(MUST_IMPORT) + _check_gone(MUST_BE_GONE)
    failed = 0
    for name, ok, detail in results:
        flag = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[startup-smoke] {flag} {name}: {detail}")
    verdict = "PASS" if failed == 0 else f"FAIL({failed})"
    print(f"[startup-smoke] {verdict} checks={len(results)} python={sys.version.split()[0]}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
