#!/usr/bin/env python3
"""b7_index_check.py — mechanical coverage checker for `notes/INDEX.md` (B7).

B7 acceptance (§4.2): "`notes/INDEX.md` 覆盖全部 notes 且带生命周期字段".
Turns that into a reproducible command instead of a hand count:

  * coverage  : every file on disk must appear somewhere in INDEX.md
  * lifecycle : every registered file must sit under one of 活 / 冻 / 归档
  * staleness : every `*.md` referenced by INDEX.md must exist on disk
Exit code 0 = all three pass.

--------------------------------------------------------------------------
2026-09-17 修复（决定5 · 假绿族 · 同一工具里两处死度量）
--------------------------------------------------------------------------
旧版（65 行 · sha8 25c941dc）有 **两处结构性假绿**：

(1) L25 `ND.iterdir()` **非递归** + 键 = **basename**
    => 归档进子目录的文件**根本不在 files 集合里**，无论登记与否都不会报 UNLISTED
    => 得到「报 PASS 的假绿」。
    盘上实证：工具报 `disk=164`，真文件数（除 INDEX.md）应 = **165**，
    恰好少掉子目录文件 `evidence/e3_os_level_snapshot.txt`。
    副产物：不同子目录的同名文件互相覆盖（dict 键碰撞）。

(2) L43 + L48 `listed` 只收录「已在 files 里」的 token，
    而 `stale = listed - set(files)` => **恒为空集** = 死度量
    （`staleness: ... = 0 []` 永远成立，不是健康信号）。

本版：
  * `rglob` 递归；键 = **相对路径**（posix）。
  * 顶层文件仍可用 basename 登记（向后兼容）；
    **同名歧义（>1 处）必须写相对路径**，否则报 AMBIGUOUS 而非静默算过。
  * `staleness` 改为对**全篇** `*.md` token 求「盘上是否存在」，不再是 listed 的子集。

路径参数化（`--notes-dir` / `--index`）=> 回归套件可对 **fixture 树**跑受控探针，
不必只依赖真实 notes 目录。
--------------------------------------------------------------------------
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

def _mimir_home() -> Path:
    """单一真源：仓库根 ``mimir_constants.get_mimir_home()``（env 优先，回退约定路径）。

    历史：此处曾硬编码 ``/home/<user>/.mimiraether``（会把 OS 用户名写进公开仓）。
    改为调用真源后**行为等价**（本机 ``MIMIR_AETHER_HOME`` 已设 ⇒ 解析同一路径）。
    """
    try:
        _root = Path(__file__).resolve().parents[1]
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
        from mimir_constants import get_mimir_home  # type: ignore

        return get_mimir_home()
    except Exception:
        return Path.home() / ".mimiraether"


ND = _mimir_home() / "notes"
IDX_NAME = "INDEX.md"
LIFECYCLE = ("## 活", "## 冻", "## 归档")


def collect(nd: Path) -> dict[str, int]:
    """递归收集：relpath(posix) -> size。排除 INDEX.md 本身。"""
    out: dict[str, int] = {}
    for p in sorted(nd.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(nd).as_posix()
        if rel == IDX_NAME:
            continue
        try:
            out[rel] = p.stat().st_size
        except OSError:
            continue
    return out


def _norm(tok: str) -> str:
    t = tok.strip()
    while t.startswith("./"):
        t = t[2:]
    return t.strip("/")


def resolve(tok: str, keys: set[str], by_name: dict[str, list[str]]):
    """token -> (命中的 relpath | None, 是否歧义)。

    ⚠️ 判定顺序是**契约的一部分**（2026-09-17 由本仓闸测试 `test_b7_index_check.py`
    抓出的真 bug）：**歧义必须先于精确键命中判定**。
    反例（修前）：顶层 `same.md` + `x/same.md` + `y/same.md`，INDEX 只写 `same.md`
    ⇒ 旧序先命中顶层键并返回 ⇒ 另两件只以 UNLISTED 形式出现，**歧义被吞**
    ⇒ 读者仍无法判断登记的是哪一个。故：**裸 basename 在盘上 >1 处 = 歧义**，
    必须写相对路径（含 `/` 的 token 才走精确匹配）。
    """
    t = _norm(tok)
    if "/" in t:
        return (t, False) if t in keys else (None, False)
    cands = by_name.get(t, [])
    if len(cands) > 1:
        return None, True
    if len(cands) == 1:
        return cands[0], False
    return None, False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="B7 INDEX.md coverage checker")
    ap.add_argument("--notes-dir", default=str(ND))
    ap.add_argument("--index", default=None, help="默认 <notes-dir>/INDEX.md")
    a = ap.parse_args(argv)

    nd = Path(a.notes_dir)
    idx = Path(a.index) if a.index else nd / IDX_NAME
    if not idx.exists():
        print(f"FAIL index not found: {idx}")
        return 2
    if not nd.is_dir():
        print(f"FAIL notes dir not found: {nd}")
        return 2

    text = idx.read_text(encoding="utf-8", errors="replace")
    files = collect(nd)
    keys = set(files)
    by_name: dict[str, list[str]] = defaultdict(list)
    for k in keys:
        by_name[k.split("/")[-1]].append(k)

    # lifecycle 分节边界（缺失即硬失败，不做静默降级）
    marks: list[tuple[str, int]] = []
    for h in LIFECYCLE:
        i = text.find(h)
        if i < 0:
            print(f"FAIL missing lifecycle heading {h!r}")
            return 2
        marks.append((h, i))
    marks.append(("__end__", len(text)))

    listed: set[str] = set()
    section_of: dict[str, str] = {}
    ambiguous: set[str] = set()
    for (h, x), (_, y) in zip(marks, marks[1:]):
        for tok in re.findall(r"`([^`\n]+)`", text[x:y]):
            hit, amb = resolve(tok, keys, by_name)
            if amb:
                ambiguous.add(_norm(tok))
            elif hit:
                listed.add(hit)
                section_of.setdefault(hit, h[3:])

    unlisted = sorted(keys - listed)

    # staleness：**登记位** = 表格行里「整格就是一个反引号 token」的格子。
    # 为什么不扫全篇：盘上实证「全篇」口径 8 条命中里 7 条是行文内引用
    # （wiki 卡 / repo 文档 / 带省略号的截断名），只有登记位才代表
    # 「INDEX 承诺了这个文件存在」=> 宽口径会制造假红，与被修的假绿同样不可用。
    # 再加一层**文件形状**过滤（无空白 / 无 = 与 : / 单个扩展名），
    # 否则命令输出格（如 `disk=160 listed=160 unlisted=0`）会被误判成登记。
    _FILE_SHAPE = re.compile(r"^[^\s`=:]+\.[A-Za-z0-9]{1,6}$")
    reg_tokens: set[str] = set()
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        for cell in line.split("|")[1:]:
            c = cell.strip()
            m = re.fullmatch(r"`([^`\n]+)`", c)
            if m:
                tok = _norm(m.group(1))
                if _FILE_SHAPE.match(tok):
                    reg_tokens.add(tok)
    known_names = set(by_name)
    stale = sorted(t for t in reg_tokens if t not in keys and t.split("/")[-1] not in known_names)

    nested = sorted(k for k in keys if "/" in k)

    print(f"coverage : disk={len(files)} listed={len(listed)} unlisted={len(unlisted)}")
    for n in unlisted:
        print(f"  UNLISTED {n} ({files[n]}B)")
    for n in sorted(ambiguous):
        print(f"  AMBIGUOUS {n} (同名文件 >1 处 —— 须写相对路径登记)")
    print(f"nested   : {len(nested)} 个子目录文件 {nested}")
    print(f"staleness: index *.md tokens with no file on disk = {len(stale)} {stale}")
    print("lifecycle: " + " / ".join(
        f"{s}={sum(1 for v in section_of.values() if v == s)}" for s in ("活", "冻", "归档")))
    total = sum(files.values())
    print(f"bytes    : indexed total = {total}B ({total / 1024:.0f} KB)")
    top = sorted(files.items(), key=lambda kv: -kv[1])[:3]
    print("largest  : " + " · ".join(f"{n} {s}B" for n, s in top))
    ok = not unlisted and not stale and not ambiguous
    print("VERDICT  : " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
