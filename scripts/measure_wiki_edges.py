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

--check-targets 目标存在性校验（v4 · 2026-11-24 · 闸模式，退出码语义例外）：
  对本脚本**同一套边判据**抽出的每个链接目标（正文 [[X]] + frontmatter target 的
  bracket/path/bare 三种写法）在库里解析，报「幽灵目标」= 边指向不存在的卡。
  解析口径搬自官方 ~/.hermes/scripts/wiki_deadlinks.py（Obsidian 视角）：
    · 全库按文件名匹配：target 取 basename，与全库 stem 比对（跨目录同名可解析）
    · 认 aliases: 头字段（行内 [] 与多行 - 两种写法）——别名可解析，不算幽灵
    · 剥围栏代码块 + 行内代码（教学占位 [[x]] 不是边）；还原表格转义（转义竖线）
    · 认锚点 #/^（[[卡#节]] 按「卡」判）；.md 后缀可选
  两档幽灵（Obsidian 解析大小写不敏感，混报会把口径假阳说成内容问题）：
    · ghosts      = 精确不存在（硬幽灵，**只有它触发 rc=1**）
    · ghost_soft  = 仅大小写 / 空格↔连字符不符（Obsidian 可解析，单列不判红）
  另单列 skipped_noncard = URL / memory: 等方案 / 纯数字字面量（不是卡目标）。
  与量具的差别（**显式声明，不静默**）：量具 body 计数不剥代码块，本校验剥。
  故输出同报 links_raw（量具口径）与 links_checked（剥后口径），差 = 代码块内链接数。
  退出码（仅 --check-targets 下）：0 = 0 幽灵 · 1 = 有幽灵 · 3 = 空转（0 个 .md，禁判绿）
  不加本参数时仍恒 0（不改变既有量具用法）。

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


# ---- 目标存在性校验（--check-targets · v4 2026-11-24） ----
# 解析口径搬自官方 ~/.hermes/scripts/wiki_deadlinks.py（Obsidian 视角 · 见模块 docstring）
FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`]*`")
BODY_LINK_TARGET_RE = re.compile(r"\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]")
ALIASES_INLINE_RE = re.compile(r"(?m)^aliases:\s*\[(.*?)\]")
ALIASES_LIST_RE = re.compile(r"(?m)^aliases:\s*\n((?:\s*-\s*.+\n)+)")
ANCHOR_SEPS = ("#", "^")
# 非卡目标（不是「边指向不存在的卡」）：URL、memory: 等方案前缀、纯数字字面量。
# 单独计数并报出，不计入幽灵——否则真幽灵会被语料噪声淹没（口径显式，不静默丢）。
NONCARD_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.\-]*://|memory:|mailto:)|^[\d\s,.]+$")


def strip_code(text: str) -> str:
    """剥围栏代码块 + 行内代码 + 还原表格转义（教学占位不是边）。"""
    t = FENCE_RE.sub(" ", text)
    t = INLINE_CODE_RE.sub(" ", t)
    return t.replace(r"\|", "|")


def _fold(s: str) -> str:
    """Obsidian 友好折叠：casefold + 空格/下划线视同连字符。"""
    return s.replace(" ", "-").replace("_", "-").casefold()


def build_target_index(wiki: Path) -> tuple[set[str], set[str], set[str]]:
    """全库目标索引：(精确名, 别名, 折叠名)。禁隐式排除——all 面含 raw/ 语料。"""
    names: set[str] = set()
    aliases: set[str] = set()
    folded: set[str] = set()
    for p in wiki.rglob("*.md"):
        if ".git" in p.parts:
            continue
        if "archive" in p.parts:
            pass  # 归档件里的卡名仍是可解析目标（Obsidian 全库匹配），故不排除
        names.add(p.stem)
        folded.add(_fold(p.stem))
        try:
            rel_name = p.relative_to(wiki).as_posix()[:-3]
        except ValueError:
            rel_name = ""
        if rel_name:
            names.add(rel_name)
            folded.add(_fold(rel_name))
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm, _ = split_frontmatter(text)
        for m in ALIASES_INLINE_RE.finditer(fm):
            for a in m.group(1).split(","):
                a = a.strip().strip("\"'")
                if a:
                    aliases.add(a)
                    folded.add(_fold(a))
        for m in ALIASES_LIST_RE.finditer(fm):
            for a in re.findall(r"-\s*(.+)", m.group(1)):
                a = a.strip().strip("\"'")
                if a:
                    aliases.add(a)
                    folded.add(_fold(a))
    return names, aliases, folded


def normalize_target(tgt: str) -> str:
    """去锚点/去 .md/去尾斜杠；纯锚点（指向本文）返回空串。"""
    t = tgt.strip()
    for sep in ANCHOR_SEPS:
        t = t.split(sep)[0]
    t = t.strip().rstrip("/")
    if t.endswith(".md"):
        t = t[:-3]
    return t.strip()


def resolve_target(tgt: str, names: set[str], aliases: set[str],
                   folded: set[str] | None = None) -> "bool | str | None":
    """True=精确可解析 · "soft"=仅大小写/空格不符（Obsidian 可解析）· False=幽灵 · None=豁免。"""
    t = normalize_target(tgt)
    if not t:
        return None
    base = t.split("/")[-1]
    if base in names or t in names or t in aliases or base in aliases:
        return True
    if folded is not None and (_fold(base) in folded or _fold(t) in folded):
        return "soft"
    return False


def extract_targets(text: str, criterion: str) -> list[str]:
    """按 criterion 抽链接目标——与 measure() 同一套边判据，但剥代码块（声明见 docstring）。"""
    fm, body = split_frontmatter(text)
    out: list[str] = []
    if criterion in ("body", "union"):
        for m in BODY_LINK_TARGET_RE.finditer(strip_code(body)):
            out.append(m.group(1))
    if criterion in ("fm", "union"):
        for m in FM_TARGET_RE.finditer(fm):
            val = m.group(1).strip().strip("\"'").strip()
            if not val or val.startswith("relations:"):
                continue
            inner = BODY_LINK_TARGET_RE.findall(val)
            out.extend(inner if inner else [val])
    return out


def count_raw_body_links(text: str) -> int:
    """量具口径（不剥代码块）的正文链接数——用于显式报两口径差。"""
    _, body = split_frontmatter(text)
    return count_body_links(body)


def check_targets(wiki: Path, surface: str, criterion: str) -> tuple[dict, int]:
    """目标存在性校验。返回 (读数, 退出码 0/1/3)。"""
    cards = collect_cards(wiki, surface)
    md_total = sum(1 for p in wiki.rglob("*.md") if ".git" not in p.parts) if wiki.exists() else 0
    names, aliases, folded = (build_target_index(wiki) if wiki.exists()
                              else (set(), set(), set()))
    instances = 0
    raw_instances = 0
    ghost_instances = 0
    skipped = 0
    skipped_noncard = 0
    soft_targets: dict[str, int] = {}
    resolved_unique: set[str] = set()
    ghosts: dict[str, int] = {}
    for p in cards:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        raw_instances += count_raw_body_links(text)
        for tgt in extract_targets(text, criterion):
            if NONCARD_RE.match(tgt.strip()):
                skipped_noncard += 1
                continue
            verdict = resolve_target(tgt, names, aliases, folded)
            if verdict is None:
                skipped += 1
                continue
            instances += 1
            key = normalize_target(tgt)
            if verdict is True:
                resolved_unique.add(key)
            elif verdict == "soft":
                # 仅大小写/空格不符 ⇒ Obsidian 可解析，不计硬幽灵；单列并计数（口径显式）
                soft_targets[key] = soft_targets.get(key, 0) + 1
            else:
                ghost_instances += 1
                ghosts[key] = ghosts.get(key, 0) + 1
    unique = len(resolved_unique) + len(ghosts) + len(soft_targets)
    result = {
        "surface": surface,
        "criterion": criterion,
        "cards": len(cards),
        "md_files": md_total,
        "links_raw": raw_instances,
        "links_checked": instances,
        "unique_targets": unique,
        "resolved_targets": len(resolved_unique),
        "ghost_targets": len(ghosts),
        "ghost_instances": ghost_instances,
        "ghost_soft_targets": len(soft_targets),
        "ghost_soft": dict(sorted(soft_targets.items(), key=lambda kv: (-kv[1], kv[0]))),
        "skipped_anchor": skipped,
        "skipped_noncard": skipped_noncard,
        "ghosts": dict(sorted(ghosts.items(), key=lambda kv: (-kv[1], kv[0]))),
    }
    if md_total == 0:
        return result, 3
    return result, (1 if ghosts else 0)


def fmt_targets(r: dict) -> str:
    head = (
        f"targets surface={r['surface']:7s} criterion={r['criterion']:5s} | "
        f"cards={r['cards']:5d} md_files={r['md_files']:5d} | "
        f"links_raw {r['links_raw']:6d} links_checked {r['links_checked']:6d} | "
        f"unique {r['unique_targets']:5d} resolved {r['resolved_targets']:5d} | "
        f"ghost {r['ghost_targets']:4d} (instances {r['ghost_instances']:5d}) | "
        f"soft(case) {r['ghost_soft_targets']:3d} | "
        f"skipped noncard {r['skipped_noncard']:3d} anchor {r['skipped_anchor']:3d}"
    )
    top = ", ".join(f"{k}({v})" for k, v in list(r["ghosts"].items())[:10])
    return head + (f"\nghosts: {top}" if top else "\nghosts: （无）")


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
        # ---- --check-targets 三控（负控先行：幽灵必须报红）----
        ct, ct_rc = check_targets(w, "single", "union")
        checks += [
            ("negctl(targets): 幽灵 x,y 必被报出", {"x", "y"} <= set(ct["ghosts"])),
            ("negctl(targets): 有幽灵 ⇒ rc=1 报红", ct_rc == 1),
            ("negctl(targets): 幽灵实例数=2", ct["ghost_instances"] == 2),
            ("targets 抽取: links_raw=2（body 口径不剥代码块）", ct["links_raw"] == 2),
            ("targets 抽取: links_checked=4（body 2 + fm 2）", ct["links_checked"] == 4),
            ("targets 解析: 可解析 a + 路径式 concepts/a = 2（b 只在 archive 面）",
             ct["resolved_targets"] == 2),
            ("targets 恒等式: resolved + ghost == unique",
             ct["resolved_targets"] + ct["ghost_targets"] == ct["unique_targets"]),
        ]
        # 非卡豁免受控差分：加一张含 URL / memory: / 纯数字 的卡 ⇒ noncard 涨、ghost 不变
        (w / "concepts/g.md").write_text(
            "---\ntitle: g\n---\n[[https://example.com]] [[memory:MEMORY_ID]] [[0, 1]]\n",
            encoding="utf-8")
        ct3, ct3_rc = check_targets(w, "single", "union")
        checks += [
            ("noncard 豁免: URL/memory:/纯数字 计 3", ct3["skipped_noncard"] == 3),
            ("noncard 豁免: 幽灵数不变（仍 2）", ct3["ghost_targets"] == 2),
            ("noncard 豁免: rc 仍为 1", ct3_rc == 1),
        ]
        # soft 分级：只差大小写 ⇒ 计 soft，不计硬幽灵，不改变 rc
        (w / "concepts/CaseIdx.md").write_text(
            "---\ntitle: CaseIdx\n---\nno link\n", encoding="utf-8")
        (w / "concepts/h.md").write_text(
            "---\ntitle: h\n---\n[[caseidx]]\n", encoding="utf-8")
        ct4, ct4_rc = check_targets(w, "single", "union")
        checks += [
            ("soft 分级: 仅大小写不符进入 ghost_soft", "caseidx" in ct4["ghost_soft"]),
            ("soft 分级: 硬幽灵不变（仍 2）", ct4["ghost_targets"] == 2),
            ("soft 分级: soft 不参与 rc（仍 1）", ct4_rc == 1),
        ]
        # 正控：把幽灵卡补上 ⇒ 幽灵清零、rc=0（证明红是内容驱动，不是恒红）
        (w / "concepts/x.md").write_text("---\ntitle: x\n---\nno link\n", encoding="utf-8")
        (w / "concepts/y.md").write_text("---\ntitle: y\n---\nno link\n", encoding="utf-8")
        ct2, ct2_rc = check_targets(w, "single", "union")
        checks += [
            ("posctl(targets): 补卡后幽灵=0", ct2["ghost_targets"] == 0),
            ("posctl(targets): soft 仍在但不判红", ct2["ghost_soft_targets"] >= 1),
            ("posctl(targets): 补卡后 rc=0 放行", ct2_rc == 0),
        ]
        # 空转负控：0 个 .md 不许判绿
        with tempfile.TemporaryDirectory() as td2:
            e = Path(td2)
            (e / "concepts").mkdir()
            _, e_rc = check_targets(e, "single", "union")
        checks.append(("空转负控(targets): 0 个 .md ⇒ rc=3", e_rc == 3))

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
    ap.add_argument("--check-targets", action="store_true",
                    help="目标存在性校验（幽灵目标 ⇒ 清单 + rc=1；0 个 .md ⇒ rc=3）")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.check_targets:
        tr, trc = check_targets(Path(a.wiki), a.surface, a.criterion)
        print(json.dumps(tr, ensure_ascii=False, indent=2) if a.json else fmt_targets(tr))
        return trc
    r = measure(Path(a.wiki), a.surface, a.criterion)
    print(json.dumps(r, ensure_ascii=False) if a.json else fmt(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
