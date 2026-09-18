#!/usr/bin/env python3
"""全仓语法闸 + 归档域闸（A8 一代 · 2026-09-18 Mimir；批4 二代扩全仓/归档域 · 2026-09-18 Mimir）。

为什么（两代病灶，同一根因 = **扫描面 < 问题面**）：
  A8（一代）：Ralph Tier-0 Gate1 此前只 py_compile 一份 TARGET_FILES 清单（cli.py / agent/*），
    scripts/ 整树不在门禁视野内 ⇒ 提交级语法死不可见。
    实证：scripts/signal-deliver.py 第 28 行把行内注释写进 os.environ.get(...) 调用内
    （引入者 6b762b2），该文件任何调用立即 SyntaxError: '(' was never closed ——
    而同一 commit 的 tier0 仍报 PASS。
  批4（二代，两道缺口一次补）：
    ① **空转绿盲区**：`--root` 默认只扫 `scripts/`（93 个文件）⇒ 全绿读数「非空转」无从判
       —— 仓库其余 800+ 个 .py 文件在视野外。
       实证（批4 首次真全仓扫的当场读数）：agent/auto_retrospective.py 第 5 行残留孤儿
       `\"\"\"`（OC-01 归档 a07c73a 插入 banner 时未删净）⇒ 该文件**无法 ast.parse**
       （tokenize: EOF in multi-line string），而 tier0 一直 PASS —— 因为它在 scripts/ 之外。
    ② **归档域复活无闸**：mimicore 域已归档（tag mimicore-archived-20260918），
       但活树里再写 `from mimicore... import ...` 没有任何门禁会红。

做法：
  ① 一次 `rglob("*.py")` 全仓扫描（默认 `--root` = 本仓根），`ast.parse` ——
     **不执行、不 import**（本仓 scripts/ 里有会写盘的脚本，import 有副作用）。
  ② 同一趟遍历里做归档域检查：`Import` / `ImportFrom` 的模块名命中归档清单前缀
     ⇒ `ARCHIVED-IMPORT-FAIL`。前缀按**组件边界**匹配（`mimicore` 命中 `mimicore` /
     `mimicore.x`，**不**命中 `mimicorex` / `mimicore_extra`）。
  ③ 排除面**显式声明在常量里**（EXCLUDED_SEGMENTS / EXCLUDED_PREFIXES）——
     既排除又声称「全仓」是本闸要防的那类谎；排除面必须可读、可审计。

单一真源：
  归档域清单 `.mimir-archived-domains.txt`（本仓根，一行一个 import 前缀，`#` 注释）。
  **加新归档 = 加一行，不改码。**

输出契约（供门禁与测试消费）：
  每个坏文件一行    SYNTAX-FAIL <path>:<lineno>: <msg>
  每条归档命中一行  ARCHIVED-IMPORT-FAIL <path>:<lineno>: import '<mod>' matches archived domain '<prefix>'
  SYNTAX-GATE       scanned=<N> ok=<N> fail=<N> root=<root>      （fail = **语法**失败数）
  ARCHIVED-GATE     scanned=<N> prefixes=<K> hits=<M> root=<root>
  退出码            0 = 全绿 / 1 = 至少一处语法死或归档域 import / 2 = 根目录不存在
  清单缺失          ARCHIVED-GATE DISABLED (list not found: <path>)  —— 显式可见，不静默

用法：
  python3 scripts/check_scripts_syntax.py                       # 全仓（默认）
  python3 scripts/check_scripts_syntax.py --root scripts        # 一代行为（仅 scripts/）
  python3 scripts/check_scripts_syntax.py --archived-domains X  # 换清单（测试用）
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path

# --- 排除面（显式、可审计）-----------------------------------------------------------
# 目录段名精确匹配：这些子树不属于「活树」，且历史上就带归档物/第三方物。
EXCLUDED_SEGMENTS = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "archive",        # 仓内 archive/ 与 docs/archive/ —— 归档物本体（批5 也会往这里放）
        ".worktrees",     # 并存工作树（例：p2-long-indep-night1，保留分支，合并前另处理）
        "build",
        "dist",
    }
)
# 相对仓根的前缀匹配（比段名更窄的排除，用于「同一目录名但位置不同」的场景）。
EXCLUDED_PREFIXES = ("docs/legacy", "scripts/legacy")
# 段名前缀匹配（venv 变体：.venv / .venv.bak-3.11.15 …）。
EXCLUDED_SEGMENT_PREFIXES = (".venv",)

ARCHIVED_LIST_ENV = "MIMIR_ARCHIVED_DOMAINS_FILE"
ARCHIVED_LIST_NAME = ".mimir-archived-domains.txt"


def repo_root() -> Path:
    """本脚本所在仓的根（scripts/check_scripts_syntax.py → 仓根）。"""
    return Path(__file__).resolve().parent.parent


def load_archived_prefixes(path: Path) -> list[str] | None:
    """读归档域清单；文件不存在 → None（闸显式 DISABLED，不静默）。"""
    if not path.is_file():
        return None
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.rstrip("."))
    return out


def match_archived(module: str, prefixes: list[str]) -> str | None:
    """模块名按**组件边界**命中归档前缀。mimicore → mimicore.x 命中；mimicorex 不命中。"""
    if not module:
        return None
    for p in prefixes:
        if module == p or module.startswith(p + "."):
            return p
    return None


def _excluded(rel: str, parts: tuple[str, ...], root: Path) -> bool:
    for seg in parts:
        if seg in EXCLUDED_SEGMENTS:
            return True
        if any(seg.startswith(p) for p in EXCLUDED_SEGMENT_PREFIXES):
            return True
    return rel.startswith(EXCLUDED_PREFIXES)


def iter_py(root: Path):
    """全仓 .py（字典序，稳定输出）；排除面见上方常量。"""
    for p in sorted(root.rglob("*.py")):
        try:
            rel = p.relative_to(root).as_posix()
        except ValueError:
            continue
        if _excluded(rel, p.parts, root):
            continue
        yield p, rel


def _archived_imports(tree: ast.AST, prefixes: list[str]) -> list[tuple[int, str, str]]:
    """返回 [(lineno, module, matched_prefix)]；只认**静态** import（相对 import 跳过）。"""
    hits: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                m = match_archived(alias.name, prefixes)
                if m:
                    hits.append((node.lineno, alias.name, m))
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import（from . import x）
                continue
            m = match_archived(node.module or "", prefixes)
            if m:
                hits.append((node.lineno, node.module or "", m))
    return hits


def check(root: Path, archived_list: Path) -> int:
    if not root.is_dir():
        print(f"SYNTAX-GATE root 不存在: {root}", file=sys.stderr)
        return 2

    prefixes = load_archived_prefixes(archived_list)
    if prefixes is None:
        print(f"ARCHIVED-GATE DISABLED (list not found: {archived_list})")

    scanned = 0
    ok = 0
    failed: list[tuple[Path, int | None, str]] = []
    archived_hits: list[tuple[str, int, str, str]] = []

    for p, rel in iter_py(root):
        scanned += 1
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            failed.append((p, None, f"非 UTF-8 文本: {e}"))
            print(f"SYNTAX-FAIL {rel}: 非 UTF-8 文本")
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            failed.append((p, e.lineno, e.msg))
            print(f"SYNTAX-FAIL {rel}:{e.lineno}: {e.msg}")
            continue
        ok += 1
        if prefixes:
            for lineno, mod, pref in _archived_imports(tree, prefixes):
                archived_hits.append((rel, lineno, mod, pref))
                print(
                    f"ARCHIVED-IMPORT-FAIL {rel}:{lineno}: "
                    f"import '{mod}' matches archived domain '{pref}'"
                )

    print(f"SYNTAX-GATE scanned={scanned} ok={ok} fail={len(failed)} root={root}")
    if prefixes is not None:
        print(
            f"ARCHIVED-GATE scanned={scanned} prefixes={len(prefixes)} "
            f"hits={len(archived_hits)} root={root}"
        )
    return 1 if (failed or archived_hits) else 0


def _default_archived_list(root: Path) -> Path:
    env = os.environ.get(ARCHIVED_LIST_ENV)
    if env:
        return Path(env).expanduser().resolve()
    return (root / ARCHIVED_LIST_NAME) if (root / ARCHIVED_LIST_NAME).is_file() else (
        repo_root() / ARCHIVED_LIST_NAME
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="全仓语法闸 + 归档域闸（ast.parse，不执行）")
    ap.add_argument(
        "--root",
        default=None,
        help=f"默认 = 本仓根（全仓扫）；旧行为传 --root <仓>/scripts",
    )
    ap.add_argument(
        "--archived-domains",
        default=None,
        help=f"归档域清单路径（默认 {ARCHIVED_LIST_NAME} 于 --root 或本仓根；env {ARCHIVED_LIST_ENV}）",
    )
    a = ap.parse_args()
    root = Path(a.root).resolve() if a.root else repo_root()
    archived_list = (
        Path(a.archived_domains).expanduser().resolve()
        if a.archived_domains
        else _default_archived_list(root)
    )
    return check(root, archived_list)


if __name__ == "__main__":
    raise SystemExit(main())
