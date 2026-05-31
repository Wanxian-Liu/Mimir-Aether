"""E-009 — single-pathway FIX write via evolve_from_suggestions (D5-2)."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.post_analysis import EvolutionSuggestion
from agent.skill_evolution import (
    EvolutionAction,
    SkillEvolutionPipeline,
    normalize_evolution_action,
)


def test_normalize_evolution_action_aliases():
    assert normalize_evolution_action("derive") == "derived"
    assert normalize_evolution_action("capture") == "captured"
    assert normalize_evolution_action("fix") == "fix"
    assert normalize_evolution_action("deprecate") == "deprecate"


def test_fix_without_skill_dir_falls_back_to_captured():
    tmp = tempfile.mkdtemp()
    skills_dir = Path(tmp)
    suggestion = EvolutionSuggestion(
        target="unknown-tool",
        action="fix",
        reason="tool errors",
        suggested_changes="# Guidance\n\nUse session_search first.\n",
        priority=3,
        confidence=0.7,
    )
    pipeline = SkillEvolutionPipeline(require_confirmation=False)
    results = asyncio.run(
        pipeline.evolve_from_suggestions([suggestion], skills_dir)
    )
    assert len(results) == 1
    assert results[0].success is True
    assert results[0].action == EvolutionAction.CAPTURED
    assert (skills_dir / "unknown-tool" / "SKILL.md").is_file()


def test_evolve_from_suggestions_deprecate_succeeds_without_skill_write():
    tmp = tempfile.mkdtemp()
    skills_dir = Path(tmp)
    suggestion = EvolutionSuggestion(
        target="broken-tool",
        action="deprecate",
        reason="consistently failing",
        priority=2,
        confidence=0.9,
    )
    pipeline = SkillEvolutionPipeline(require_confirmation=False)
    results = asyncio.run(
        pipeline.evolve_from_suggestions([suggestion], skills_dir)
    )
    assert len(results) == 1
    assert results[0].success is True
    assert results[0].action == EvolutionAction.DEPRECATE
    assert results[0].changes_applied == 0


def test_evolve_from_suggestions_fix_writes_skill_md():
    tmp = tempfile.mkdtemp()
    skills_dir = Path(tmp)
    skill_dir = skills_dir / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: before\n---\n\n# Before\n",
        encoding="utf-8",
    )

    suggestion = EvolutionSuggestion(
        target="demo-skill",
        action="fix",
        reason="e2e fix path",
        suggested_changes="---\nname: demo-skill\ndescription: after\n---\n\n# After E009\n",
        priority=2,
        confidence=0.95,
    )

    pipeline = SkillEvolutionPipeline(require_confirmation=False)
    results = asyncio.run(
        pipeline.evolve_from_suggestions([suggestion], skills_dir)
    )

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].action == EvolutionAction.FIX
    content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "# After E009" in content
    assert results[0].diff != ""


def test_evolve_from_suggestions_accepts_derive_alias():
    tmp = tempfile.mkdtemp()
    skills_dir = Path(tmp)
    skill_dir = skills_dir / "alias-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# src\n", encoding="utf-8")

    suggestion = EvolutionSuggestion(
        target="alias-skill",
        action="derive",
        reason="alias maps to derived",
        suggested_changes="# derived body\n",
        priority=3,
        confidence=0.8,
    )

    pipeline = SkillEvolutionPipeline(require_confirmation=False)
    results = asyncio.run(
        pipeline.evolve_from_suggestions([suggestion], skills_dir)
    )

    assert results[0].success is True
    assert results[0].action == EvolutionAction.DERIVED
    assert (skills_dir / "alias-skill-enhanced" / "SKILL.md").exists()
