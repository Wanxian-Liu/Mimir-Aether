#!/usr/bin/env python3
"""wiki_edge_matrix.py — 知识库「边语法 × 消费者」覆盖矩阵量具。

用途：回答「全库有几种边语法、每种被谁认」，找出「生产端写得出、消费端不认、
且不报错」的静默缺口。

设计纪律（本仓血泪）：
  - 只读，永不写 wiki
  - 每种语法都带正控（构造样本必须命中）/ 负控（构造样本必须不命中）
  - 分母必须显式：非 raw/ 的 .md 文件数
  - 机器读数，不接受「大概/约」

用法：
  wiki_edge_matrix.py --inventory           # 生产端语法盘点
  wiki_edge_matrix.py --consumers           # 消费端能力盘点
  wiki_edge_matrix.py --matrix              # 覆盖矩阵 + 静默缺口
  wiki_edge_matrix.py --selftest            # 探针自证（正/负控）
  wiki_edge_matrix.py --check               # 缺口非零则 rc=1（闸门模式）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WIKI_ROOT = Path.home() / "wiki"
GIT_SEG = "/" + ".git/"
RAW_SEG = "/raw/"

# ---------------------------------------------------------------- 语法定义
# 每种边语法：name -> {regex, kind(body|frontmatter), consumers:[...]}
SYNTAX = {
    "wikilink":       {"re": re.compile(r"\[\[([^\]\n]+?)\]\]"),                      "kind": "body"},
    "md_link":        {"re": re.compile(r"\[([^\]\n]*)\]\(([^)\s]+?\.md(?:#[^)]*)?)\)"), "kind": "body"},
    "source_line":    {"re": re.compile(r"来源[:：]\s*([^\n]+)"),                     "kind": "body"},
    "book_chapter":   {"re": re.compile(r"《([^》]+)》\s*第?\s*(\d+)\s*章"),           "kind": "body"},
    "fm_relations":   {"re": re.compile(r"^relations:\s*$", re.MULTILINE),            "kind": "frontmatter"},
    "fm_based_on":    {"re": re.compile(r"^based_on:\s*(.+)$", re.MULTILINE),         "kind": "frontmatter"},
    "fm_derived_from":{"re": re.compile(r"^derived_from:\s*(.+)$", re.MULTILINE),     "kind": "frontmatter"},
    "fm_related":     {"re": re.compile(r"^related:\s*(.+)$", re.MULTILINE),          "kind": "frontmatter"},
    "fm_sources":     {"re": re.compile(r"^sources:\s*(.+)$", re.MULTILINE),          "kind": "frontmatter"},
    "fm_parent":      {"re": re.compile(r"^parent:\s*(.+)$", re.MULTILINE),           "kind": "frontmatter"},
    "fm_links":       {"re": re.compile(r"^links:\s*(.+)$", re.MULTILINE),            "kind": "frontmatter"},
}

# 消费者 → 其 docstring/代码声明的解析面（真源：graph_leg.py 的 re.compile 清单）
CONSUMERS = {
    "graph_leg": {
        "path": "~/.hermes/scripts/rag-eval/graph_leg.py",
        "recognizes": ["wikilink", "source_line", "book_chapter", "fm_based_on", "fm_relations"],
        "note": "8 条 re.compile：_YAML/\
_WIKILINK/_SOURCE_LINE/_BOOK_CHAPTER/_ANY_BOOK/_BASED_ON_INLINE/_BASED_ON_BLOCK/_RELATIONS_BLOCK",
    },
    "wiki_card_links": {
        "path": "~/.hermes/scripts/wiki_card_links.py",
        "recognizes": ["wikilink"],
        "note": "官方双链计数口径：只数 [[...]]",
    },
    "wiki_deadlinks": {
        "path": "~/.hermes/scripts/wiki_deadlinks.py",
        "recognizes": ["wikilink"],
        "note": "死链判定：只解 [[...]]",
    },
    "measure_wiki_edges": {
        "path": "~/src/MimirAether/scripts/measure_wiki_edges.py",
        "recognizes": ["wikilink", "fm_relations", "fm_based_on", "fm_derived_from"],
        "note": "本席量具 v3",
    },
}


def iter_cards(root: Path | None = None):
    root = root or WIKI_ROOT
    for p in sorted(root.rglob("*.md")):
        s = str(p)
        if RAW_SEG in s or GIT_SEG in s:
            continue
        yield p


def split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            return text[3:end], text[end + 4:]
    return "", text


def inventory(root: Path | None = None) -> dict:
    files = list(iter_cards(root))
    counts = {k: 0 for k in SYNTAX}
    filecounts = {k: 0 for k in SYNTAX}
    for p in files:
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        fm, body = split_frontmatter(t)
        for name, spec in SYNTAX.items():
            hay = fm if spec["kind"] == "frontmatter" else body
            n = len(spec["re"].findall(hay))
            if n:
                counts[name] += n
                filecounts[name] += 1
    return {"cards": len(files), "occurrences": counts, "files": filecounts}


def consumers() -> dict:
    out = {}
    for name, spec in CONSUMERS.items():
        p = Path(str(spec["path"]).replace("~", str(Path.home())))
        out[name] = {
            "path": str(spec["path"]),
            "exists": p.exists(),
            "lines": len(p.read_text(encoding="utf-8", errors="ignore").splitlines()) if p.exists() else 0,
            "recognizes": spec["recognizes"],
            "note": spec["note"],
        }
    return out


def matrix_by_consumer(inv: dict, cons: dict) -> dict:
    """二维矩阵：每个消费者 × 每种语法 = seen/missing。

    纪律：**不用并集口径**。并集会掩盖单链路缺口——只要有一个消费者认出，
    全局就算「认了」，而真正跑的那条链可能一条都没认。这正是「似是而非」。
    """
    produced = {k for k, v in inv["occurrences"].items() if v > 0}
    grid = {}
    for cname, c in cons.items():
        rec = set(c["recognizes"])
        grid[cname] = {
            syn: ("seen" if syn in rec else "MISSING")
            for syn in sorted(produced)
        }
    # 每条语法：有几个消费者认
    coverage = {
        syn: sum(1 for c in cons.values() if syn in set(c["recognizes"]))
        for syn in sorted(produced)
    }
    per_consumer_gaps = {
        cname: {
            "missing": sorted(s for s, v in row.items() if v == "MISSING"),
            "lost_occurrences": sum(inv["occurrences"][s] for s, v in row.items() if v == "MISSING"),
        }
        for cname, row in grid.items()
    }
    return {
        "cards": inv["cards"],
        "produced_occurrences": {s: inv["occurrences"][s] for s in sorted(produced)},
        "coverage_count": coverage,
        "grid": grid,
        "per_consumer_gaps": per_consumer_gaps,
        "zero_consumer": sorted(s for s in produced if coverage[s] == 0),
    }


def matrix(inv: dict, cons: dict) -> dict:
    """兼容旧口径的汇总（并集），仅用于对比；判定一律用 matrix_by_consumer。"""
    produced = {k for k, v in inv["occurrences"].items() if v > 0}
    recognized = set()
    for c in cons.values():
        recognized |= set(c["recognizes"])
    silent = sorted(produced - recognized)
    return {
        "produced": sorted(produced),
        "recognized": sorted(recognized),
        "silent_gaps_union": silent,
        "gap_occurrences": {k: inv["occurrences"][k] for k in silent},
        "WARNING": "并集口径会掩盖单链路缺口；判定请用 --matrix2",
    }


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    """正控 / 负控：每条语法必须能区分「有」和「没有」。"""
    fails = []
    samples = {
        "wikilink":        ("见 [[某卡]] 与 [[另一卡]]", 2, "见 某卡 与 另一卡"),
        "md_link":         ("见 [文本](./a.md) 和 [x](../b/c.md)", 2, "见 文本 和 x"),
        "source_line":     ("来源：某论文 2026", 1, "出处：某论文 2026"),
        "book_chapter":    ("《1Q84》第 3 章", 1, "《1Q84》第三章无数字"),
        "fm_relations":    ("relations:\n  - type: a", 1, "relation:\n  - type: a"),
        "fm_based_on":     ("based_on: [x]", 1, "basedoff: [x]"),
        "fm_derived_from": ("derived_from: 原话全集", 1, "derivedfrom: 原话全集"),
        "fm_related":      ("related: [a]", 1, "relatedness: [a]"),
        "fm_sources":      ("sources: [a]", 1, "source_map: [a]"),
        "fm_parent":       ("parent: a", 1, "parental: a"),
        "fm_links":        ("links: [a]", 1, "linkset: [a]"),
    }
    for name, (pos, expect, neg) in samples.items():
        got = len(SYNTAX[name]["re"].findall(pos))
        got_neg = len(SYNTAX[name]["re"].findall(neg))
        if got != expect or got_neg != 0:
            fails.append(f"{name}: pos={got}(want {expect}) neg={got_neg}(want 0)")
    # 关键负控：md_link 不得把 wikilink 数成 md 链接
    if len(SYNTAX["md_link"]["re"].findall("[[x]]")) != 0:
        fails.append("md_link 误吞 wikilink")
    if len(SYNTAX["wikilink"]["re"].findall("[t](./a.md)")) != 0:
        fails.append("wikilink 误吞 md_link")

    total = len(samples) + 2
    if fails:
        print(f"SELFTEST FAIL ({len(fails)}/{total})")
        for f in fails:
            print("  ✗", f)
        return 1
    print(f"SELFTEST PASS ({total}/{total})  pos/neg 双向可分")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", action="store_true")
    ap.add_argument("--consumers", action="store_true")
    ap.add_argument("--matrix", action="store_true", help="并集口径汇总（仅供对比，不作判定）")
    ap.add_argument("--matrix2", action="store_true", help="二维矩阵（判定口径）")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--check", action="store_true", help="关键链路有静默缺口 => rc=1")
    ap.add_argument("--key-consumer", default="graph_leg", help="--check 的判定链路（默认图腿）")
    ap.add_argument("--root", default=None)
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    root = Path(a.root) if a.root else None
    if a.inventory:
        print(json.dumps(inventory(root), ensure_ascii=False, indent=2))
        return 0
    if a.consumers:
        print(json.dumps(consumers(), ensure_ascii=False, indent=2))
        return 0
    if a.matrix2 or a.check:
        cons = consumers()
        m = matrix_by_consumer(inventory(root), cons)
        print(json.dumps(m, ensure_ascii=False, indent=2))
        if a.check:
            key = a.key_consumer
            if key not in m["per_consumer_gaps"]:
                print(f"CHECK: unknown --key-consumer {key}", file=sys.stderr)
                return 2
            lost = m["per_consumer_gaps"][key]["lost_occurrences"]
            n_missing = len(m["per_consumer_gaps"][key]["missing"])
            print(f"CHECK[{key}]: missing_syntaxes={n_missing} lost_occurrences={lost} zero_consumer={len(m['zero_consumer'])}")
            return 1 if lost else 0
        return 0
    if a.matrix:
        m = matrix(inventory(root), consumers())
        print(json.dumps(m, ensure_ascii=False, indent=2))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
