"""技能注入面探针：量「活体入口」真注入文本（只读 · 不写 snapshot cache）。

强制冷扫描会触发 prompt_builder 的 snapshot 写盘分支，故 write 侧一并打桩——
探针不留副作用（2026-11-24 实证：未打桩时一次探测就把 data/.skills_snapshot_cache 覆盖）。

活体入口 = agent/config_mixin.py::_build_system_prompt 传 skills_dirs=[<repo>/skills]。
口径与 scripts/skills_dormant_audit.py 同源（点目录整树跳过），但本脚本量的是
**prompt_builder 实际产出的注入文本**，用于「改前/改后字符数 + dormant 名 grep」取证。

用法（必须 venv 解释器）:
    ~/src/MimirAether/.venv/bin/python3 scripts/skills_injection_probe.py
    ... --dump /tmp/skills_prompt.txt     把注入文本落盘供 grep
输出:
    LIVE_LEN_CHARS / LIVE_INDEX_NAMES / LIVE_DORMANT_HITS / DORMANT_POOL / DUMP
"""
from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import agent.prompt_builder as pb  # noqa: E402

LIVE_DIRS = [str(REPO / "skills")]
DORMANT_ROOTS = [REPO / "skills" / ".dormant", pathlib.Path.home() / ".mimiraether" / "skills" / ".dormant"]


def dormant_names() -> set:
    names = set()
    for root in DORMANT_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("SKILL.md"):
            names.add(p.parts[-2])
    return names


def hits_in(prompt: str, dorm: set) -> list:
    """索引行 '    - name' / '    - name: desc' 上的精确名命中（非子串）。"""
    found = []
    for line in prompt.splitlines():
        s = line.strip()
        if not s.startswith("- "):
            continue
        nm = s[2:].split(":", 1)[0].strip()
        if nm in dorm:
            found.append(nm)
    return sorted(found)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default="")
    args = ap.parse_args()

    pb._SKILLS_PROMPT_CACHE.clear()
    orig_load, orig_write = pb._load_skills_snapshot, pb._write_skills_snapshot
    pb._load_skills_snapshot = lambda dirs: None        # 强制冷扫描，避免读到旧快照
    pb._write_skills_snapshot = lambda *a, **k: None    # 探针不落盘（只读）
    try:
        prompt = pb.build_skills_system_prompt(skills_dirs=LIVE_DIRS)
    finally:
        pb._load_skills_snapshot, pb._write_skills_snapshot = orig_load, orig_write

    dorm = dormant_names()
    hits = hits_in(prompt, dorm)
    idx = [l for l in prompt.splitlines() if l.strip().startswith("- ")]
    print("LIVE_LEN_CHARS=%d" % len(prompt))
    print("LIVE_INDEX_NAMES=%d" % len(idx))
    print("DORMANT_POOL=%d" % len(dorm))
    print("LIVE_DORMANT_HITS=%d" % len(hits))
    print("LIVE_DORMANT_SAMPLE=%s" % hits[:3])
    if args.dump:
        pathlib.Path(args.dump).write_text(prompt, encoding="utf-8")
        print("DUMP=%s" % args.dump)
    return 0 if not hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
