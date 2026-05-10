#!/usr/bin/env python3
"""
Audit SKILL.md files for YAML frontmatter and auto_load (same contract as skills_loader).

Usage:
  python scripts/audit_skills_auto_load.py
  python scripts/audit_skills_auto_load.py --roots skills optional-skills

Exit code is always 0 (report-only) so local/CI tier0 is unaffected.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Match skills/skills_loader._parse_frontmatter
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str, bool]:
    """Returns (frontmatter_dict, body, has_frontmatter_block)."""
    m = _FRONTMATTER.match(content)
    if not m:
        return {}, content, False
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, m.group(2), True


def auto_load_status(fm: Dict[str, Any]) -> str:
    if "auto_load" not in fm:
        return "missing"
    v = fm["auto_load"]
    if v is True:
        return "true"
    if v is False:
        return "false"
    return str(v)


def has_auto_load_meta(fm: Dict[str, Any]) -> bool:
    meta = fm.get("auto_load_meta")
    return isinstance(meta, dict) and len(meta) > 0


def short_description(fm: Dict[str, Any]) -> str:
    meta = fm.get("auto_load_meta")
    if isinstance(meta, dict):
        d = meta.get("description")
        if isinstance(d, str) and d.strip():
            return d.strip()[:80]
    d = fm.get("description")
    if isinstance(d, str) and d.strip():
        return d.strip()[:80]
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit SKILL.md auto_load frontmatter.")
    ap.add_argument(
        "--roots",
        nargs="+",
        default=["skills"],
        help="Directories to scan (default: skills)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Print JSON lines instead of a table",
    )
    args = ap.parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    rows: List[dict] = []

    for rel in args.roots:
        base = (root_dir / rel).resolve()
        if not base.is_dir():
            print(f"# skip (not a dir): {base}", file=sys.stderr)
            continue
        for path in sorted(base.rglob("SKILL.md")):
            text = path.read_text(encoding="utf-8")
            fm, _body, has_fm = parse_frontmatter(text)
            rel_path = path.relative_to(root_dir)
            skill_dir = path.parent.name
            rows.append(
                {
                    "path": str(rel_path),
                    "skill_dir": skill_dir,
                    "has_yaml_block": has_fm,
                    "auto_load": auto_load_status(fm),
                    "has_auto_load_meta": has_auto_load_meta(fm),
                    "description_preview": short_description(fm),
                }
            )

    if args.json:
        import json

        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
        return

    # Text table
    print("path\tauto_load\thas_meta\tyaml_block\tdescription_preview")
    for r in rows:
        print(
            f"{r['path']}\t{r['auto_load']}\t{r['has_auto_load_meta']}\t{r['has_yaml_block']}\t{r['description_preview']}"
        )

    # Summary for mimiraether
    mim = [r for r in rows if "/mimiraether/" in r["path"].replace("\\", "/")]
    if mim:
        missing = sum(1 for r in mim if r["auto_load"] == "missing")
        true_n = sum(1 for r in mim if r["auto_load"] == "true")
        print("", file=sys.stderr)
        print(
            f"# summary skills/mimiraether: auto_load=true={true_n}, auto_load missing={missing}, total={len(mim)}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
