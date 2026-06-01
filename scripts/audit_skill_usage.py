#!/usr/bin/env python3
"""Audit skill usage: total registered, loaded, never-loaded, usage distribution.

Sources:
  - skills/ directory (SKILL.md count = registered)
  - persistent.json skill_usage (runtime session tracking)
  - agent.log skill_view calls (historical)
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

MIMIR_HOME = Path(os.environ.get("MIMIR_AETHER_HOME", "~/.mimiraether")).expanduser()
SKILLS_DIR = MIMIR_HOME / "skills"
PERSISTENT = MIMIR_HOME / "data" / "persistent.json"
AGENT_LOG = MIMIR_HOME / "logs" / "agent.log"


def count_skill_dirs() -> int:
    """Count directories under skills/ that have a SKILL.md."""
    if not SKILLS_DIR.is_dir():
        return 0
    return sum(1 for d in SKILLS_DIR.iterdir() if d.is_dir() and (d / "SKILL.md").is_file())


def list_skill_dirs() -> list[str]:
    """List all skill names with SKILL.md."""
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(
        d.name for d in SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    )


def load_skill_usage() -> dict:
    """Load skill_usage from persistent.json."""
    if not PERSISTENT.is_file():
        return {}
    try:
        data = json.loads(PERSISTENT.read_text())
        return data.get("skill_usage", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def detect_auto_load_skills() -> set[str]:
    """Detect skills with auto_load: true in their SKILL.md frontmatter."""
    auto = set()
    for d in SKILLS_DIR.iterdir():
        skill_md = d / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            content = skill_md.read_text()
            if re.search(r"auto_load\s*:\s*true", content, re.IGNORECASE):
                auto.add(d.name)
        except OSError:
            pass
    return auto


def scan_log_skill_view_calls(log_path: Path = AGENT_LOG) -> Counter:
    """Scan agent.log for skill_view calls."""
    counter: Counter = Counter()
    if not log_path.is_file():
        return counter
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        # Pattern 1: skill_view("name") or skill_view('name') in function calls
        for m in re.finditer(
            r'skill_view\(\s*["\']([^"\']+)["\']', text, re.IGNORECASE
        ):
            counter[m.group(1)] += 1
        # Pattern 2: [MIMIR_SKILL_ROUTE_NUDGE] -> skill_view for skill: name
        for m in re.finditer(
            r"call skill_view for each skill:\s*([^\n]+)", text, re.IGNORECASE
        ):
            for name in m.group(1).split(","):
                name = name.strip()
                if name:
                    counter[name] += 1
        # Pattern 3: loaded skill "name"
        for m in re.finditer(r'loaded skill\s+["\']?([^"\'\s,.]+)', text, re.IGNORECASE):
            counter[m.group(1)] += 1
    except OSError:
        pass
    return counter


def report(verbose: bool = True) -> dict:
    """Generate audit report."""
    # 1. File-system registration
    registered = list_skill_dirs()
    total_registered = len(registered)
    auto_load_count = 0
    auto_load_names = detect_auto_load_skills()
    auto_loaded = [s for s in registered if s in auto_load_names]
    non_loaded = [s for s in registered if s not in auto_load_names]

    # 2. Runtime usage from persistent.json
    skill_usage = load_skill_usage()
    tracked = set(skill_usage.keys())
    viewed_from_persistent = {
        k for k, v in skill_usage.items()
        if isinstance(v, dict) and v.get("viewed_count", 0) > 0
    }

    # 3. Log analysis
    log_counts = scan_log_skill_view_calls()
    viewed_from_log = set(log_counts.keys())
    all_viewed = viewed_from_persistent | viewed_from_log

    # 4. Stats
    total_skills = total_registered + len(tracked - set(registered))
    never_viewed = [s for s in registered if s not in all_viewed]
    top_viewed = log_counts.most_common(10)

    # Build result
    result = {
        "total_registered": total_registered,
        "total_with_runtime_tracking": total_skills,
        "auto_loaded": len(auto_loaded),
        "manual_loaded": len(all_viewed - auto_load_names),
        "never_viewed": len(never_viewed),
        "viewed_skills": sorted(all_viewed),
        "never_viewed_skills": never_viewed,
        "top_viewed": [(name, count) for name, count in top_viewed],
    }

    if verbose:
        print(f"{'='*60}")
        print(f"  Skill Usage Audit Report")
        print(f"{'='*60}")
        print(f"\n📊 概览")
        print(f"  技能目录中（有 SKILL.md）：{total_registered}")
        print(f"  含运行时追踪记录（含未注册的）：{total_skills}")
        print(f"  自动加载（auto_load=true）：   {len(auto_loaded)}")
        print(f"  被调用过（log + persistent）： {len(all_viewed)}")
        print(f"  从未加载：                     {len(never_viewed)}")
        print(f"\n🔝 Top 10 被调用技能（log 统计）")
        if top_viewed:
            for name, count in top_viewed:
                marker = " ⚡auto" if name in auto_load_names else ""
                print(f"  {count:3d}x  {name}{marker}")
        else:
            print(f"  （暂无 log 记录）")
        print(f"\n💤 未加载技能（{len(never_viewed)} 个）")
        if never_viewed:
            for s in sorted(never_viewed):
                print(f"  · {s}")
        print(f"\n🔧 自动加载技能（{len(auto_loaded)} 个）")
        for s in sorted(auto_loaded):
            print(f"  · {s}")
        print()

    return result


if __name__ == "__main__":
    verbose = "-q" not in sys.argv
    report(verbose=verbose)
