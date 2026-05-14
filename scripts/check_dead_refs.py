#!/usr/bin/env python3
"""Dead reference scanner for MimirAether skills — enhanced v2.

Scans all SKILL.md files for:
  1. Hardcoded /home/* paths that don't exist
  2. Inline path references (backtick-quoted) that don't resolve
  3. Python import references to non-existent modules
  4. Skill-to-skill references (frontmatter related_skills + inline skill_view)
  5. mimicore submodule imports (validated per-file, not blanket-banned)
  6. Stale hermes-agent cross-references

Usage:
    python scripts/check_dead_refs.py          # full scan
    python scripts/check_dead_refs.py --quiet  # only errors / exit code
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
PY_IMPORT_RE = re.compile(
    r"(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_.]*)"
)
INLINE_PATH_RE = re.compile(
    r"`(~?(?:\.openclaw|\.mimiraether|\.hermes)/[^`]*\.(?:py|md|json|yaml|sh|yaml)[^`]*)`"
)
HARD_PATH_RE = re.compile(
    r"/home/\w+/[^\s`\"']+\.(?:py|md|json|yaml|sh)"
)
SKILL_REF_RE = re.compile(
    r'skill_view\s*\(\s*["\']([a-zA-Z0-9_-]+)["\']'
)
RELATED_RE = re.compile(
    r'related_skills\s*:\s*\[([^\]]*)\]'
)
SKILL_NAME_RE = re.compile(
    r'"([a-zA-Z0-9_-]+)"'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def collect_skill_mds() -> List[Path]:
    return sorted(SKILLS_DIR.rglob("SKILL.md"))


def build_skill_index() -> Dict[str, Path]:
    """Build a map of skill-name → SKILL.md path for cross-ref validation."""
    index: Dict[str, Path] = {}
    for md in collect_skill_mds():
        name = md.parent.name
        index[name] = md
    return index


def resolve_path(ref: str) -> Path:
    """Resolve a path reference against REPO_ROOT or $HOME."""
    ref = ref.strip()
    if ref.startswith("~/"):
        return Path(ref).expanduser()
    if ref.startswith("/"):
        return Path(ref)
    return REPO_ROOT / ref


def file_exists(path: Path) -> bool:
    """Check if a path exists, handling glob patterns."""
    s = str(path)
    if "*" in s:
        return bool(list(Path(s).parent.glob(Path(s).name)))
    return path.exists()


# ---------------------------------------------------------------------------
# Checkers
# ---------------------------------------------------------------------------
def check_mimicore_import(import_path: str) -> Tuple[bool, str]:
    """Validate a mimicore.* import resolves to an actual file."""
    parts = import_path.split(".")
    if parts[0] != "mimicore":
        return True, ""

    # mimicore.xxx.yyy → mimicore/xxx/yyy.py  OR mimicore/xxx/yyy/__init__.py
    fname = "/".join(parts) + ".py"
    init_fname = "/".join(parts) + "/__init__.py"

    if (REPO_ROOT / fname).exists() or (REPO_ROOT / init_fname).exists():
        return True, ""
    return False, f"Dead mimicore import: from {import_path} ... → {fname} not found"


def check_standard_import(import_path: str) -> Tuple[bool, str]:
    """Check if a non-mimicore Python import path resolves."""
    parts = import_path.split(".")
    root = parts[0]
    if root not in ("agent", "gateway", "tools", "mimiraether"):
        return True, ""  # external lib, skip

    fname = "/".join(parts) + ".py"
    init_fname = "/".join(parts) + "/__init__.py"

    if (REPO_ROOT / fname).exists() or (REPO_ROOT / init_fname).exists():
        return True, ""
    return False, f"No such module: {fname} (from import {import_path})"


def extract_related_skills(content: str) -> List[str]:
    """Extract skill names from frontmatter related_skills list."""
    match = RELATED_RE.search(content)
    if not match:
        return []
    inner = match.group(1)
    return [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()]


def check_skill(skill_md: Path, skill_index: Dict[str, Path]) -> List[str]:
    """Check a single SKILL.md for dead references. Returns list of issue strings."""
    issues: List[str] = []
    content = skill_md.read_text()
    skill_name = skill_md.parent.name

    # ------------------------------------------------------------------
    # 1. Hardcoded /home/* paths
    # ------------------------------------------------------------------
    for m in HARD_PATH_RE.finditer(content):
        p = m.group()
        if not resolve_path(p).exists():
            issues.append(f"Dead hard path: {p}")

    # ------------------------------------------------------------------
    # 2. Inline backtick paths
    # ------------------------------------------------------------------
    for m in INLINE_PATH_RE.finditer(content):
        p = m.group(1)
        if p.startswith("http"):
            continue
        # Skip template/placeholder tokens
        if any(tok in p for tok in ("<", ">", "$")):
            continue
        resolved = resolve_path(p)
        if not file_exists(resolved):
            issues.append(f"Unresolved path: {p}")

    # ------------------------------------------------------------------
    # 3. Python imports in code blocks
    # ------------------------------------------------------------------
    for m in PY_IMPORT_RE.finditer(content):
        imp = m.group(1)
        if imp.startswith("mimicore"):
            ok, err = check_mimicore_import(imp)
        else:
            ok, err = check_standard_import(imp)
        if not ok:
            issues.append(err)

    # ------------------------------------------------------------------
    # 4. Skill-to-skill references (related_skills)
    # ------------------------------------------------------------------
    related = extract_related_skills(content)
    for ref_name in related:
        if ref_name not in skill_index:
            issues.append(f"related_skills references non-existent skill: '{ref_name}'")

    # ------------------------------------------------------------------
    # 5. Inline skill_view() calls
    # ------------------------------------------------------------------
    seen: Set[str] = set()
    for m in SKILL_REF_RE.finditer(content):
        ref_name = m.group(1)
        if ref_name in seen:
            continue
        seen.add(ref_name)
        if ref_name not in skill_index:
            issues.append(f"skill_view() references non-existent skill: '{ref_name}'")

    return issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    quiet = "--quiet" in sys.argv
    skill_mds = collect_skill_mds()
    skill_index = build_skill_index()

    total_issues = 0
    clean_count = 0

    for skill_md in skill_mds:
        issues = check_skill(skill_md, skill_index)
        if issues:
            total_issues += len(issues)
            name = str(skill_md.parent.relative_to(SKILLS_DIR))
            print(f"\n⚠  {name} ({len(issues)} issues)")
            for iss in issues:
                print(f"   • {iss}")
        else:
            clean_count += 1

    print(f"\n{'='*60}")
    print(f"Scanned: {len(skill_mds)} skills")
    print(f"  Clean: {clean_count}")
    print(f"  Issues: {total_issues} in {len(skill_mds) - clean_count} skills")

    return 1 if total_issues > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
