#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure_wiki_edges.py — 知识库「边」的可复跑量具（口径显式化）

为什么需要这个脚本（2026-11-11 内部会议裁决产物）：
  同一件事被报出过三个互不可复现的数，根因是「分子取单层扫描面、分母取未知面」
  拼成比率（metric mixing）。本脚本把扫描面（surface）与边判据（criterion）
  都变成显式参数，输出永远带口径名。

v2 修正（2026-11-11 23:40）：v1 的 frontmatter 边判据只认 `target: "[[x]]"`
  形态，漏掉了 `target: concepts/xxx` 路径形态（实测 129 张）——量具自身的口径
  漏洞，读数为 60 而真值约 189。v2 改为「任何非空 target 均计边」，并输出
  三种写法（bracket/path/bare）的分解，避免再次用单形态冒充全量。

四个扫描面（--surface）：
  single   官方 wiki_card_links.py --scan 的面：concepts/entities/discussions 单层
  recur    递归三层（含 discussions/archive）
  noarch   递归但剔除 archive（"当前活卡"）
  all      全库 *.md（含 raw/ 语料、skills 供应商文档——不建议当"卡"用）

边判据（--criterion）：
  body     只看正文双链（剥 frontmatter 后计数，非空）
  fm       只看 frontmatter relations[].target（任意写法）
  union    任一即可（默认；对应"两套语法并存、两边读数都真"）

输出：文字行 + 可 --json 机读。退出码 0 恒（这是量具不是闸）。

用法：
  ~/src/MimirAether/.venv/bin/python3 scripts/measure_wiki_edges.py --surface recur
  ~/src/MimirAether/.venv/bin/python3 scripts/measure_wiki_edges.py --selftest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BODY_LINK_RE = re.compile(r"\[\[([^\]]*)\]\]")
FM_TARGET_RE = re.compile(r"^\s*-?\s*target:\s*(.+?)\s*$", re.M)


def split_frontmatter(text: str) -> tuple[str, str]:
    """返回 (frontmatter, body)。无 frontmatter 则 fm 为空串。"""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[1], parts[2]
    return "", text


def count_body_links(body: str) -> int:
    """正文双链出现次数；空链与纯空白不计。"""
    return sum(1 for m in BODY_LINK_RE.finditer(body) if m.group(1).strip())


def fm_target_styles(fm: str) -> tuple[int, int, int]:
    """返回 (总边数, bracket 形态数, path/bare 形态数)。

    任何非空 target 都算一条边——三种写法都是合法的边声明：
      target: "[[卡名]]"        bracket
      target: concepts/卡名     path
      target: 卡名              bare
    """
    total = bracket = plain = 0
    for m in FM_TARGET_RE.finditer(fm):
        val = m.group(1).strip().strip("\"'").strip()
        if val.startswith("relations:"):
            continue
        if not val:
            continue
        total += 1
        if "[[" in val:
            bracket += 1
        else:
            plain += 1
    return total, bracket, plain


def collect_cards(wiki: Path, surface: str) -> list[Path]:
    if surface == "all":
        return sorted(wiki.rglob("*.md"))
    roots = [wiki / d for d in ("concepts", "entities", "discussions")]
    out: list[Path] = []
    for r in roots:
        if not r.exists():
            continue
        if surface == "single":
            out.extend(sorted(r.glob("*.md")))
        elif surface == "recur":
            out.extend(sorted(r.rglob("*.md")))
        elif surface == "noarch":
            out.extend(sorted(p for p in r.rglob("*.md") if "archive" not in p.parts))
        else:
            raise ValueError(f"unknown surface: {surface}")
    return out


def measure(wiki: Path, surface: str, criterion: str) -> dict:
    cards = collect_cards(wiki, surface)
    body_ge1 = body_ge2 = fm_ge1 = union_ge1 = union_ge2 = 0
    fm_bracket = fm_plain = 0
    for p in cards:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm, body = split_frontmatter(text)
        bl = count_body_links(body)
        fr, br, pl = fm_target_styles(fm)
        fm_bracket += br
        fm_plain += pl
        if bl >= 1:
            body_ge1 += 1
        if bl >= 2:
            body_ge2 += 1
        if fr >= 1:
            fm_ge1 += 1
        u = bl + fr
        if u >= 1:
            union_ge1 += 1
        if u >= 2:
            union_ge2 += 1
    n = len(cards)
    # v3 fix（2026-11-11 内部三席会 A/C 席实证）：islands 曾恒用 union_ge1 计算，
    # 导致 --criterion 开关对**头条指标**无效（body/fm/union 三次输出逐字节相同）。
    # 头条指标必须跟 criterion 走，且分源报（禁跨口径混比）。
    linked_by_criterion = {"body": body_ge1, "fm": fm_ge1, "union": union_ge1}
    if criterion not in linked_by_criterion:
        raise ValueError(f"unknown criterion: {criterion}")
    islands_by_source = {k: n - v for k, v in linked_by_criterion.items()}
    islands = n - linked_by_criterion[criterion]
    return {
        "surface": surface,
        "criterion": criterion,
        "cards": n,
        "body_ge1": body_ge1,
        "body_ge2": body_ge2,
        "fm_ge1": fm_ge1,
        "fm_edges_bracket": fm_bracket,
        "fm_edges_plain": fm_plain,
        "union_ge1": union_ge1,
        "union_ge2": union_ge2,
        "islands": islands,
        "islands_by_source": islands_by_source,
        "island_rate": round(islands / n, 4) if n else 0.0,
    }


def fmt(r: dict) -> str:
    return (
        f"surface={r['surface']:7s} cards={r['cards']:5d} | "
        f"body>=1 {r['body_ge1']:5d}  body>=2 {r['body_ge2']:5d} | "
        f"fm>=1 {r['fm_ge1']:4d} (bracket {r['fm_edges_bracket']}, path/bare {r['fm_edges_plain']}) | "
        f"union>=1 {r['union_ge1']:5d} | islands {r['islands']:5d} ({r['island_rate']*100:.1f}%)"
    )


def selftest() -> int:
    """受控差分：口径/判据必须分别改变读数（否则量具无鉴别力）。"""
    import tempfile

    ok = True
    with tempfile.TemporaryDirectory() as td:
        w = Path(td)
        for d in ("concepts", "entities", "discussions", "discussions/archive"):
            (w / d).mkdir(parents=True, exist_ok=True)
        # A: 正文 2 链
        (w / "concepts/a.md").write_text(
            "---\ntitle: a\n---\n[[" + "x]] [[" + "y]]\n", encoding="utf-8")
        # B: frontmatter bracket 形态 1 边
        (w / "concepts/b.md").write_text(
            "---\ntitle: b\nrelations:\n  - type: related_to\n    target: \"[[" + "a]]\"\n---\nno link\n",
            encoding="utf-8")
        # C: 真孤岛
        (w / "concepts/c.md").write_text("---\ntitle: c\n---\nno link\n", encoding="utf-8")
        # D: 空链不计
        (w / "concepts/d.md").write_text("---\ntitle: d\n---\n[[]]\n", encoding="utf-8")
        # E: 只在 archive（surface 轴）
        (w / "discussions/archive/e.md").write_text(
            "---\ntitle: e\n---\n[[" + "a]] [[" + "b]]\n", encoding="utf-8")
        # F: frontmatter 路径形态 1 边（v1 漏掉的那种）
        (w / "concepts/f.md").write_text(
            "---\ntitle: f\nrelations:\n  - type: related_to\n    target: concepts/a\n---\nno link\n",
            encoding="utf-8")

        single = measure(w, "single", "union")
        recur = measure(w, "recur", "union")

        checks = [
            ("surface axis: single cards=5", single["cards"] == 5),
            ("surface axis: recur cards=6", recur["cards"] == 6),
            ("criterion axis: body>=1 ignores fm", single["body_ge1"] == 1),
            ("criterion axis: union>=1 counts fm", single["union_ge1"] == 3),
            ("negative: islands found=2 (c,d)", single["islands"] == 2),
            ("negative: empty link not counted", single["body_ge2"] == 1),
            ("v2 fix: path-style target counted", single["fm_ge1"] == 2),
            ("v2 fix: style split bracket=1 plain=1",
             single["fm_edges_bracket"] == 1 and single["fm_edges_plain"] == 1),
            # v3：头条指标必须跟 criterion 走（旧版此处只断言中间字段，故 bug 逃逸）
            ("v3: islands body=4", single["islands_by_source"]["body"] == 4),
            ("v3: islands fm=3", single["islands_by_source"]["fm"] == 3),
            ("v3: headline follows criterion",
             measure(w, "single", "body")["islands"] == 4
             and measure(w, "single", "fm")["islands"] == 3),
            # 负控：三口径若仍同值 ⇒ 开关又死，本项必失
            ("v3 negative: 三口径不得同值",
             len({single["islands_by_source"][k] for k in ("body", "fm", "union")}) == 3),
        ]
        for name, good in checks:
            print(f"  [{'PASS' if good else 'FAIL'}] {name}")
            ok = ok and good
    print("\nselftest: " + ("OK" if ok else "FAILED") + f" ({len(checks)} checks)")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki", default=str(Path.home() / "wiki"))
    ap.add_argument("--surface", default="recur",
                    choices=["single", "recur", "noarch", "all"])
    ap.add_argument("--criterion", default="union",
                    choices=["body", "fm", "union"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = measure(Path(a.wiki), a.surface, a.criterion)
    print(json.dumps(r, ensure_ascii=False) if a.json else fmt(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
