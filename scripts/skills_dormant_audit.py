"""技能注入面审计（只读 · 不写 snapshot cache）

用途：验证「.dormant 技能是否仍被注入 prompt」与「同名内外层是否内容分叉」。
出处：2026-11-23 内部会议（整改方案审计 + 子代理短命根因）§6 T0-1/T0-2。

用法（必须用 venv 解释器）:
    ~/src/MimirAether/.venv/bin/python3 scripts/skills_dormant_audit.py
    ... --json        机器可读
    ... --selftest    双向自检（正控 live 保留 / 负控 dormant 计入 / 分叉计 1）

rc 语义:
    0 = 无 dormant 名被注入（负控过）且分叉数 <= 基线
    1 = 有 dormant 名被注入，或分叉数超基线（回归）
    2 = 参数/环境错（argparse 默认）

基线（2026-11-23 · 修前）:
    names_total=201  live=52  dormant_only=149  chars=26238  diverged=6
    T0-1 修好后应为: names_total=52 live=52 dormant_only=0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
ROOTS = [REPO / "skills", pathlib.Path.home() / ".mimiraether" / "skills"]
BASELINE_DIVERGED = 6


def iter_dedup(roots):
    """按 prompt_builder 顺序（先到先得，name=parts[-2]）去重。"""
    seen = {}
    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob("SKILL.md")):
            name = p.parts[-2]
            if name not in seen:
                seen[name] = p
    return seen


def desc_of(p):
    try:
        t = p.read_text(errors="replace")
    except OSError:
        return ""
    m = re.search(r"^description:\s*(.+)$", t, re.M)
    return (m.group(1).strip() if m else "")[:300]


def measure(roots=None):
    roots = roots or ROOTS
    seen = iter_dedup(roots)
    dormant = {n: p for n, p in seen.items() if ".dormant" in p.parts}
    live = {n: p for n, p in seen.items() if ".dormant" not in p.parts}
    chars = sum(len(n) + len(desc_of(p)) + 8 for n, p in seen.items())
    live_chars = sum(len(n) + len(desc_of(p)) + 8 for n, p in live.items())
    diverged = []
    r0 = roots[0]
    if r0.exists():
        for p in r0.rglob("SKILL.md"):
            inner = p.parent / p.parent.name / "SKILL.md"
            if inner.exists():
                a = hashlib.md5(p.read_bytes()).hexdigest()
                b = hashlib.md5(inner.read_bytes()).hexdigest()
                if a != b:
                    diverged.append(p.parent.name)
    return {
        "names_total": len(seen),
        "live": len(live),
        "dormant_only": len(dormant),
        "chars": chars,
        "live_chars": live_chars,
        "diverged": sorted(set(diverged)),
        "diverged_count": len(set(diverged)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--baseline-diverged", type=int, default=BASELINE_DIVERGED)
    args = ap.parse_args()

    if args.selftest:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / "skills"
            live_p = root / "cat" / "alive-skill"
            dead_p = root / ".dormant" / "cat" / "dead-skill"
            for d, nm in ((live_p, "alive-skill"), (dead_p, "dead-skill")):
                d.mkdir(parents=True)
                (d / "SKILL.md").write_text(
                    "---\nname: %s\ndescription: probe %s\n---\nbody\n" % (nm, nm)
                )
            inner = live_p / "alive-skill"
            inner.mkdir()
            (inner / "SKILL.md").write_text(
                "---\nname: alive-skill\ndescription: FORKED\n---\n"
            )
            m = measure([root])
            ok = (m["names_total"] == 2 and m["live"] == 1
                  and m["dormant_only"] == 1 and m["diverged_count"] == 1)
            print("selftest measure=%s" % m)
            print("SELFTEST %s" % ("OK" if ok else "FAIL"))
            return 0 if ok else 1

    m = measure()
    if args.json:
        print(json.dumps(m, ensure_ascii=False))
    else:
        print("注入技能名: 总 %d | live %d | dormant-only %d"
              % (m["names_total"], m["live"], m["dormant_only"]))
        print("注入文本: %d 字符（live 部分 %d）" % (m["chars"], m["live_chars"]))
        print("同名内外层内容分叉: %d 处 %s" % (m["diverged_count"], m["diverged"]))

    rc = 0
    if m["dormant_only"] > 0:
        rc = 1
    if m["diverged_count"] > args.baseline_diverged:
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
