#!/usr/bin/env python3
"""矛盾族归并试验（只读 · 不改主路径）

目的：验证「族指纹」能否把 self_contradiction_report.json 里的重复矛盾
收敛成少数几族。用盘上真实数据当天然测试集。

用法:
  --selftest                 两向自检（不读真库，判据是否可用的前提）
  [path] [threshold]         对指定文件跑聚族（默认真库 / 0.6）

判据（§8.5 形态 1）:
  重跑命令: ~/src/MimirAether/.venv/bin/python3 ~/src/MimirAether/scripts/contradiction_family_probe.py --selftest
  复算数字: rc=0；POS >=0.6 / NEG <0.3（两控制组样本不同、期望值不同、目标不复用）
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Iterable

DEFAULT_PATH = os.path.join(
    os.environ.get("MIMIR_AETHER_HOME") or os.path.expanduser("~/.mimiraether"),
    "data",
    "self_contradiction_report.json",
)

# 归一化：小写、去标点/空白、压成连续字符流
_STRIP_RE = re.compile(r"[\s\u3000,.，。;；:：!！?？、\'\"“”‘’（）()\[\]【】《》<>·…\-—_/\\|]+")


def normalize(text: str) -> str:
    return _STRIP_RE.sub("", (text or "").lower())


def bigrams(text: str) -> set[str]:
    """字符二元组集合。中文无需分词，纯标准库、确定性。"""
    s = normalize(text)
    if len(s) < 2:
        return {s} if s else set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def family_of(texts: Iterable[str], threshold: float = 0.6) -> list[list[int]]:
    """把条目按相似度聚族，返回每族的下标列表（顺序 = 首次出现顺序）。"""
    texts = list(texts)
    grams = [bigrams(t) for t in texts]
    families: list[list[int]] = []
    reps: list[set[str]] = []
    for i, g in enumerate(grams):
        placed = False
        for fi, rep in enumerate(reps):
            if jaccard(g, rep) >= threshold:
                families[fi].append(i)
                placed = True
                break
        if not placed:
            families.append([i])
            reps.append(g)
    return families


def selftest() -> int:
    """两向控制：证明这把尺子**有鉴别力**，而不是恒真/恒假。

    三条硬约束：两控制组样本不同 · 期望值不同 · 目标（真库）不作控制样本。
    """
    # 正控：同一议题、只改尾部一个词 ⇒ 应判为「同族」
    pos_a = "决策「甲」与模式「乙」冲突：前者要求复评前验量具，后者声明修量具不计分"
    pos_b = "决策「甲」与模式「乙」冲突：前者要求复评前验量具，后者声明修量具不算分"
    # 负控：完全不同的两个议题 ⇒ 应判为「不同族」
    neg_a = "决策「技术难题自己整理，四方只作兜底」与模式「任务消息必须真写盘」存在张力"
    neg_b = "决策「可逆的我定、不可逆的上收」与模式「风险须升级为 owner+deadline」冲突"

    s_pos = jaccard(bigrams(pos_a), bigrams(pos_b))
    s_neg = jaccard(bigrams(neg_a), bigrams(neg_b))
    ok_pos = s_pos >= 0.6
    ok_neg = s_neg < 0.3
    print(f"POS sim={s_pos:.3f} (expect >=0.6) -> {'seen' if ok_pos else 'none'}")
    print(f"NEG sim={s_neg:.3f} (expect <0.3) -> {'seen' if ok_neg else 'none'}")

    # 聚族器本身：2 同族 + 1 异类 ⇒ 应得 2 族
    fams = family_of([pos_a, pos_b, neg_a], 0.6)
    ok_fam = len(fams) == 2
    print(f"FAM families={len(fams)} (expect 2) -> {'seen' if ok_fam else 'none'}")

    ok = ok_pos and ok_neg and ok_fam
    print(f"RESULT: {'PASS' if ok else 'FAIL'} rc={0 if ok else 1}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else DEFAULT_PATH
    threshold = float(args[1]) if len(args) > 1 else 0.6
    if not os.path.isfile(path):
        print(f"MISSING: {path}")
        return 2
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    if not isinstance(items, list):
        print("NOT A LIST")
        return 2

    texts = [it.get("contradiction", "") for it in items]
    fams = family_of(texts, threshold)

    print(f"file      : {path}")
    print(f"entries   : {len(texts)}")
    print(f"threshold : {threshold}")
    print(f"families  : {len(fams)}")
    print("")
    for fi, idxs in enumerate(fams, 1):
        ts = [items[i].get("timestamp", "")[:10] for i in idxs]
        print(f"--- family {fi}: n={len(idxs)} dates={ts}")
        head = texts[idxs[0]]
        print(f"    head: {head[:110]}")
        if len(idxs) > 1:
            gs = [bigrams(texts[i]) for i in idxs]
            worst = min(
                (jaccard(gs[a], gs[b]) for a in range(len(gs)) for b in range(a + 1, len(gs))),
                default=1.0,
            )
            print(f"    min intra-pair sim: {worst:.3f}")
    if len(fams) > 1:
        reps = [bigrams(texts[idxs[0]]) for idxs in fams]
        worst_cross = max(
            jaccard(reps[a], reps[b])
            for a in range(len(reps))
            for b in range(a + 1, len(reps))
        )
        print("")
        print(f"max cross-family sim: {worst_cross:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
