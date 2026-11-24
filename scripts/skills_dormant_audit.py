"""技能注入面审计（只读 · 不写 snapshot cache）

用途：验证「同名内外层是否内容分叉」与「点目录技能是否仍被注入 prompt」。
出处：2026-11-23 内部会议（整改方案审计 + 子代理短命根因）§6 T0-1/T0-2。

口径（2026-11-24 对齐 agent/prompt_builder.py::_iter_skill_files · _build_skills_manifest）:
    跳过**点目录整树**——相对技能根任一路径段以 "." 开头即不纳入。
    即 .dormant / .hub / .archive / .pytest_cache 等**任意**点目录一律整树跳过；
    旧版只认路径里含 ".dormant" 这一种名字，对 .hub 之类漏网（本次对齐点）。

用法（必须用 venv 解释器）:
    ~/src/MimirAether/.venv/bin/python3 scripts/skills_dormant_audit.py
    ... --json        机器可读
    ... --selftest    双向自检（正控 普通嵌套技能仍计入 / 负控 点目录整树跳过 · 含嵌套与另一种点目录名 / 分叉计 1）

rc 语义:
    0 = dormant_only == 0（点目录整树跳过生效）且分叉数 <= 基线
    1 = 仍有点目录技能被计入（口径破损 = 回归），或分叉数超基线
    2 = 参数/环境错（argparse 默认）

基线（口径切换前后各一档 · 读数由本脚本实测）:
    旧口径（2026-11-23 · 点目录只认 .dormant）:
        names_total=201  live=52  dormant_only=149  chars=26246  diverged=6
    新口径（2026-11-24 · 点目录整树跳过）:
        names_total=59   live=59  dormant_only=0    chars=10054  diverged=0
    两档差异的两个成因（不是抖动，都是口径变更的直接后果）:
      live 52 -> 59：旧口径下 .dormant 里的同名技能先到先得，**遮住**了
                     ~/.mimiraether/skills 下同名 live 技能（7 个名字被解放）；
      diverged 6 -> 0：旧口径的 6 处分叉全在点目录树内（死件），新口径不再计入。
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
# 新口径基线：点目录整树跳过，repo/skills 活体面无分叉
BASELINE_DIVERGED = 0


def is_visible(rel_parts):
    """相对技能根的任一段以 "." 开头 => 属点目录整树，不纳入（对齐 prompt_builder）。"""
    return not any(str(x).startswith(".") for x in rel_parts)


def iter_skill_files(root):
    """按 prompt_builder 口径遍历 SKILL.md：跳过点目录整树。"""
    if not root.exists():
        return []
    out = []
    for p in sorted(root.rglob("SKILL.md")):
        try:
            rel = p.relative_to(root)
        except ValueError:  # pragma: no cover - rglob 结果必在 root 下
            continue
        if is_visible(rel.parts):
            out.append(p)
    return out


def iter_dedup(roots):
    """按 prompt_builder 顺序（先到先得，name=parts[-2]）去重。"""
    seen = {}
    for root in roots:
        for p in iter_skill_files(root):
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
    roots = list(roots or ROOTS)
    seen = iter_dedup(roots)
    # 不变量探针：seen 已按口径过滤 => dormant 应恒为空集。
    # 若不为空，说明过滤失效（回归），由 rc=1 报出，不静默吞掉。
    dormant = {n: p for n, p in seen.items() if ".dormant" in p.parts}
    live = {n: p for n, p in seen.items() if n not in dormant}
    chars = sum(len(n) + len(desc_of(p)) + 8 for n, p in seen.items())
    live_chars = sum(len(n) + len(desc_of(p)) + 8 for n, p in live.items())
    diverged = []
    r0 = roots[0]
    for p in iter_skill_files(r0):
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
        "seen": sorted(seen),
    }


def _selftest(verbose=False):
    """双向自检（新口径）:
    正控① 普通嵌套技能仍计入；正控② 第二个普通技能仍计入（防过滤过头全跳过）；
    负控① 顶层点目录 .dormant 整树跳过；
    负控② 另一种点目录名 .hub 整树跳过（旧口径漏网点）；
    负控③ 嵌套点目录 <live>/.archive/ 整树跳过（"整树"而非"仅顶层"）；
    分叉 同名内层文件不同 => diverged_count 计 1。
    """
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td) / "skills"
        live_p = root / "cat" / "alive-skill"
        dead_p = root / ".dormant" / "cat" / "dead-skill"
        hub_p = root / ".hub" / "pack" / "hub-skill"
        plain_p = root / "cat" / "plain-skill"
        nested_dot = live_p / ".archive" / "old-skill"
        for d, nm in ((live_p, "alive-skill"), (dead_p, "dead-skill"),
                      (hub_p, "hub-skill"), (plain_p, "plain-skill"),
                      (nested_dot, "old-skill")):
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(
                "---\nname: %s\ndescription: probe %s\n---\nbody\n" % (nm, nm)
            )
        inner = live_p / "alive-skill"
        inner.mkdir()
        (inner / "SKILL.md").write_text(
            "---\nname: alive-skill\ndescription: FORKED\n---\n"
        )
        m = measure([root])
        # 新口径断言（与旧口径相反：点目录不再计入 dormant_only）
        ok = (m["names_total"] == 2 and m["live"] == 2
              and m["dormant_only"] == 0 and m["diverged_count"] == 1)
        if verbose:
            print("selftest measure=%s" % m)
        else:
            print("selftest measure=%s" % {k: v for k, v in m.items() if k != "seen"})
        print("SELFTEST %s" % ("OK" if ok else "FAIL"))
        return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--baseline-diverged", type=int, default=BASELINE_DIVERGED)
    args = ap.parse_args()

    if args.selftest:
        return _selftest(args.verbose)

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
