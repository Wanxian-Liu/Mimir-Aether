"""B3 (2026-09-13) — ghost-skill scope: archived (.dormant) entries are not ghosts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.skills_qa import SkillsQA  # noqa: E402

SKILLS_ROOT = ROOT / "skills"


def test_dormant_entries_excluded_by_default(tmp_path):
    """POSITIVE: a frontmatter-less skill under .dormant is not reported as a ghost."""
    d = tmp_path / ".dormant" / "general" / "archived-shell"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("# archived shell\n\nno frontmatter here\n", encoding="utf-8")
    qa = SkillsQA(str(tmp_path))

    assert qa.detect_ghost_skills()["no_frontmatter"] == []
    audited = qa.detect_ghost_skills(include_archived=True)
    assert ".dormant/general/archived-shell" in audited["no_frontmatter"], audited


def test_live_skill_without_frontmatter_still_flagged(tmp_path):
    """NEGATIVE: a live skill lacking frontmatter is still reported."""
    d = tmp_path / "workflow" / "live-shell"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("# live shell\n\nno frontmatter here\n", encoding="utf-8")
    ghosts = SkillsQA(str(tmp_path)).detect_ghost_skills()
    assert "workflow/live-shell" in ghosts["no_frontmatter"], ghosts


def test_repo_skills_tree_has_zero_live_ghosts():
    """LOCK: the live skills tree must stay ghost-free (frontmatter present)."""
    if not SKILLS_ROOT.is_dir():
        return
    ghosts = SkillsQA(str(SKILLS_ROOT)).detect_ghost_skills()
    assert sum(len(v) for v in ghosts.values()) == 0, f"live ghost skills appeared: {ghosts}"
