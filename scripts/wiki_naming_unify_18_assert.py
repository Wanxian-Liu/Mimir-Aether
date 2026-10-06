#!/usr/bin/env python3
"""B18 回归探针 — wiki 命名口径一致性（SCHEMA.md:27-28 = 连字符族）。

断言（无 skip/xfail 分支 · 全跑）:
  A1 9 个连字符目标件在盘        A2 9 个空格源件不在盘
  A3 活面「引用形态」空格旧名 = 0  A4 断链数 = 0（repo wiki_quality_report --json）
rc: 0 全过 / 1 任一失败 / 2 探针自身跑不成
"""
from __future__ import annotations
import json, os, subprocess, sys, tempfile
from pathlib import Path

WIKI = Path(os.environ.get("WIKI_DIR", "/home/rayliu/wiki"))
REPORT = Path(__file__).resolve().parent / "wiki_quality_report.py"
EXCL_DIRS = {"raw", "reports", "archive", "discussions", "templates", ".git", "node_modules"}
EXCL_FILES = {"log.md"}
# (目录, 连字符目标 stem, 空格旧 stem)
PAIRS = [
    ("concepts", "1Q84-世界", "1Q84 世界"),
    ("concepts", "aeris10-开源相控阵雷达", "AERIS-10开源相控阵雷达"),
    ("concepts", "小小人-little-people", "小小人 Little People"),
    ("concepts", "空气蛹-air-chrysalis", "空气蛹 Air Chrysalis"),
    ("entities", "保镖-tamaru", "保镖 Tamaru"),
    ("entities", "小松-komatsu", "小松 Komatsu"),
    ("entities", "小蓟-azumi", "小蓟 Azumi"),
    ("entities", "深绘里-fukaeri", "深绘里 Fuka-Eri"),
    ("entities", "雅由美-ayumi", "雅由美 Ayumi"),
]


def ref_forms(d: str, o: str, n: str):
    return [f"[[{d}/{o}]]", f"[[{o}]]", f"target: {d}/{o}", f"{d}/{o}.md"]


def active_md():
    out = []
    for root, dirs, files in os.walk(WIKI):
        rel = os.path.relpath(root, WIKI)
        if rel.split(os.sep)[0] in EXCL_DIRS:
            dirs[:] = []
            continue
        for fn in files:
            if fn.endswith(".md") and fn not in EXCL_FILES:
                out.append(Path(root) / fn)
    return out


def main() -> int:
    if not WIKI.is_dir() or not REPORT.exists():
        print(f"PROBE-BROKEN: wiki={WIKI.is_dir()} report={REPORT.exists()}")
        return 2
    fails = []
    for d, n, o in PAIRS:                                   # A1/A2
        if not (WIKI / d / f"{n}.md").exists():
            fails.append(f"A1 缺连字符件 {d}/{n}.md")
        if (WIKI / d / f"{o}.md").exists():
            fails.append(f"A2 空格源件仍在盘 {d}/{o}.md")
    hits = 0                                                # A3
    for p in active_md():
        txt = p.read_text(encoding="utf-8", errors="replace")
        for d, n, o in PAIRS:
            for form in ref_forms(d, o, n):
                if form in txt:
                    hits += txt.count(form)
                    fails.append(f"A3 {p.relative_to(WIKI)} 残留引用 {form}")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        jp = tf.name
    rc = subprocess.run([sys.executable, str(REPORT), "--json", jp],
                        capture_output=True, text=True).returncode
    data = json.loads(Path(jp).read_text())
    os.unlink(jp)
    broken = data.get("broken_count")
    dups = data.get("duplicate_groups")
    if rc != 0 or broken != 0:                              # A4
        fails.append(f"A4 断链 broken_count={broken}（期望 0）rc={rc}")
    if dups:
        fails.append(f"A4b 同页重复组 duplicate_groups={dups}（期望 0）")
    print(f"[B18 命名口径探针] 对={len(PAIRS)} · 引用形态残留={hits} · "
          f"broken={broken} · dup={dups} · 扫描 .md={len(active_md())}")
    for f in fails:
        print("  FAIL", f)
    print("VERDICT:", "PASS" if not fails else f"FAIL({len(fails)})")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
