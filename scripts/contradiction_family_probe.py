#!/usr/bin/env python3
"""矛盾族探针 —— 度量 self_contradiction_report.json 的族归并情况（只读）。

用途：回答「这份矛盾报告里有多少条是同一件事的重复？」
　　　也是 §8.5 意义上的量具：给出 entries / families / 族内与跨族相似度。

设计约束（2026-11-04 实证）：
  - 只用**引号短语 Jaccard**，不做语义合并。矛盾的定义是「决策 X」vs「模式 Y」，
    X/Y 都在「」内，所以这是最贴近结构的可比面。
  - **它抓不住同义改写**：真实数据里同一族两条可以掉到 0.000（A 族 10-28 vs 10-30）。
    因此本探针只用于「判读与取证」，**不可用于自动去重**。默认阈值 0.9 = 只认逐字重复。
  - home 解析走 pwd.getpwuid，不走 expanduser——后者在 execute_code 沙箱
    （HOME=~/.mimiraether）下会把 ~ 解析错，造成假阴性。

用法：
  python3 scripts/contradiction_family_probe.py [report.json] [threshold]
  默认阈值 0.9（安全档：只抓逐字重复）

退出码：0 正常；2 输入不可读 / 非 list
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Iterable

_QUOTE_RE = re.compile(r"「([^」]{2,})」|『([^』]{2,})』")
_STRIP_RE = re.compile(r"[\s\u3000,.，。;；:：!！?？、'\"“”‘’（）()\[\]【】《》<>·…\-—_/\\|]+")


def user_home() -> str:
    """真实用户 home——不受 HOME 环境变量污染。"""
    try:
        import pwd

        return pwd.getpwuid(os.getuid()).pw_dir
    except Exception:  # pragma: no cover - 非 POSIX 兜底
        return os.path.expanduser("~")


def default_report_path() -> str:
    return os.path.join(user_home(), ".mimiraether", "data", "self_contradiction_report.json")


def normalize(text: str) -> str:
    return _STRIP_RE.sub("", (text or "").lower())


def phrases(text: str) -> set[str]:
    """抽取「」『』内短语，归一化后作为集合。"""
    out: set[str] = set()
    for m in _QUOTE_RE.finditer(text or ""):
        s = normalize(m.group(1) or m.group(2) or "")
        if s:
            out.add(s)
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def families_of(texts: Iterable[str], threshold: float = 0.9) -> list[list[int]]:
    """贪心聚族：与已有族代表相似度 >= threshold 则并入。顺序 = 首次出现顺序。"""
    fams: list[list[int]] = []
    reps: list[set[str]] = []
    for i, t in enumerate(texts):
        p = phrases(t)
        for fi, rep in enumerate(reps):
            if jaccard(p, rep) >= threshold:
                fams[fi].append(i)
                break
        else:
            fams.append([i])
            reps.append(p)
    return fams


def main(argv: list[str]) -> int:
    path = argv[1] if len(argv) > 1 else default_report_path()
    threshold = float(argv[2]) if len(argv) > 2 else 0.9

    if not os.path.isfile(path):
        print(f"MISSING: {path}")
        return 2
    try:
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"UNREADABLE: {type(e).__name__}: {e}")
        return 2
    if not isinstance(items, list):
        print("NOT_A_LIST")
        return 2

    texts = [it.get("contradiction", "") if isinstance(it, dict) else str(it) for it in items]
    fams = families_of(texts, threshold)

    print(f"path      : {path}")
    print(f"entries   : {len(texts)}")
    print(f"threshold : {threshold}")
    print(f"families  : {len(fams)}")
    for fi, idxs in enumerate(fams, 1):
        dates = [
            (items[i].get("timestamp", "")[:10] if isinstance(items[i], dict) else "?")
            for i in idxs
        ]
        print(f"  family {fi}: n={len(idxs)} dates={dates}")
        print(f"    head: {texts[idxs[0]][:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
