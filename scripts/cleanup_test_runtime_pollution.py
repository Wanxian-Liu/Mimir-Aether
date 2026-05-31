#!/usr/bin/env python3
"""One-shot cleanup: test-session lines in agent.log + test skill artifacts."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.synthetic_sessions import is_synthetic_session_id
from mimir_constants import get_mimir_home

_EVOLUTION_LINE = re.compile(
    r"post_analysis evolution session_id=(\S+)"
)
_TEST_SKILL_DIRS = ("unknown-tool",)


def _filter_agent_log(log_path: Path, *, dry_run: bool) -> tuple[int, int]:
    if not log_path.is_file():
        return 0, 0
    raw = log_path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines(keepends=True)
    kept: list[str] = []
    removed = 0
    for line in lines:
        m = _EVOLUTION_LINE.search(line)
        if m and is_synthetic_session_id(m.group(1)):
            removed += 1
            continue
        kept.append(line)
    if removed and not dry_run:
        backup = log_path.with_suffix(
            f".bak.{time.strftime('%Y%m%d-%H%M%S')}"
        )
        shutil.copy2(log_path, backup)
        log_path.write_text("".join(kept), encoding="utf-8")
    return len(lines), removed


def _remove_test_skills(skills_root: Path, *, dry_run: bool) -> list[str]:
    removed: list[str] = []
    for name in _TEST_SKILL_DIRS:
        path = skills_root / name
        if not path.is_dir():
            continue
        removed.append(str(path))
        if not dry_run:
            shutil.rmtree(path)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--home",
        type=Path,
        default=None,
        help="Mimir home (default: get_mimir_home())",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only; do not modify files",
    )
    args = parser.parse_args()
    home = args.home or get_mimir_home()
    log_path = home / "logs" / "agent.log"
    skills_root = home / "skills"

    total, stripped = _filter_agent_log(log_path, dry_run=args.dry_run)
    skill_paths = _remove_test_skills(skills_root, dry_run=args.dry_run)

    print(f"home={home}")
    print(f"agent.log lines={total} stripped_evolution_lines={stripped}")
    if skill_paths:
        print(f"skill_dirs_removed={skill_paths}")
    else:
        print("skill_dirs_removed=none")
    if args.dry_run:
        print("(dry-run; no files changed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
