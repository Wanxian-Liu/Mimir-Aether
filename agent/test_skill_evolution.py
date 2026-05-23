"""Tests for agent/skill_evolution.py — FIX/DERIVED/CAPTURED execution pipeline.

EV-K05: test stub for skill evolution module.
Tests import, construction, all three actions, error paths, and stats.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.post_analysis import EvolutionSuggestion  # noqa: E402
from agent.skill_evolution import (  # noqa: E402
    EvolutionAction,
    EvolutionContext,
    EvolutionResult,
    SkillEvolutionPipeline,
    apply_with_retry,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

def _make_ctx(action, target, reason="", suggested_changes="",
              priority=3, confidence=0.85, skill_dir=None, skill_content=""):
    return EvolutionContext(
        action=action,
        suggestion=EvolutionSuggestion(
            target=target,
            action=action.value,
            reason=reason,
            suggested_changes=suggested_changes,
            priority=priority,
            confidence=confidence,
        ),
        skill_dir=skill_dir,
        skill_content=skill_content,
    )


def _temp_skill_dir():
    """Create a temporary skills directory with a source skill for testing."""
    tmp = tempfile.mkdtemp()
    src = Path(tmp) / "source-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text(
        "---\nname: source-skill\ndescription: Test source\n---\n\n# Source\n\nOld content.\n"
    )
    (src / "README.md").write_text("Source readme.\n")
    return tmp, src


# ── Import + Construction ────────────────────────────────────────────────────

def test_import_skill_evolution():
    """All key symbols should be importable."""
    assert SkillEvolutionPipeline is not None
    assert EvolutionAction.FIX.value == "fix"
    assert EvolutionAction.DERIVED.value == "derived"
    assert EvolutionAction.CAPTURED.value == "captured"
    assert EvolutionResult is not None
    assert EvolutionContext is not None
    assert apply_with_retry is not None


def test_pipeline_construction():
    """Pipeline should construct with default stats."""
    p = SkillEvolutionPipeline()
    assert p.stats == {"total_evolved": 0, "total_skipped": 0}


# ── FIX ─────────────────────────────────────────────────────────────────────

def test_fix_writes_skills_md_and_returns_diff():
    tmp, src = _temp_skill_dir()
    ctx = _make_ctx(
        EvolutionAction.FIX,
        target="source-skill",
        suggested_changes="---\nname: source-skill\ndescription: Fixed\n---\n\n# Fixed content.\n",
        skill_dir=src,
        skill_content=(src / "SKILL.md").read_text(),
    )
    p = SkillEvolutionPipeline()
    result = asyncio.run(p._execute_evolution(ctx))

    assert result.success is True
    assert result.action == EvolutionAction.FIX
    assert result.target == "source-skill"
    assert result.diff != ""
    assert "# Fixed content" in result.diff
    assert (src / "SKILL.md").read_text().startswith("---")


# ── DERIVED ──────────────────────────────────────────────────────────────────

def test_derived_creates_new_dir_and_copies_files():
    tmp, src = _temp_skill_dir()
    ctx = _make_ctx(
        EvolutionAction.DERIVED,
        target="source-skill-v2",
        suggested_changes="---\nname: source-skill-v2\ndescription: Enhanced\n---\n\n# Enhanced v2.\n",
        skill_dir=src,
        skill_content=(src / "SKILL.md").read_text(),
    )
    p = SkillEvolutionPipeline()
    result = asyncio.run(p._execute_evolution(ctx))

    assert result.success is True
    new_dir = result.output_dir
    assert new_dir is not None
    assert new_dir.exists()
    assert (new_dir / "SKILL.md").exists()
    assert (new_dir / "README.md").exists()
    content = (new_dir / "SKILL.md").read_text()
    assert "Enhanced v2" in content
    assert "derived_from" in content.lower()
    assert result.diff != ""


# ── CAPTURED (skill_dir set) ─────────────────────────────────────────────────

def test_captured_with_skill_dir_creates_frontmatter():
    tmp, src = _temp_skill_dir()
    ctx = _make_ctx(
        EvolutionAction.CAPTURED,
        target="my-captured-skill",
        reason="Extracted from T-09 audit: self_evolution is empty shell",
        suggested_changes="# My Captured Skill\n\nAuto-captured from analysis.\n",
        priority=4,
        confidence=0.92,
        skill_dir=src,
    )
    p = SkillEvolutionPipeline()
    result = asyncio.run(p._execute_evolution(ctx))

    assert result.success is True
    # skills_base = ctx.skill_dir.parent = tmp (not tmp/skills/)
    expected = Path(tmp) / "my-captured-skill"
    assert result.output_dir == expected
    assert expected.exists()
    assert (expected / "SKILL.md").exists()
    content = (expected / "SKILL.md").read_text()
    assert content.startswith("---\n")
    assert "name: my-captured-skill" in content
    assert "category: captured" in content
    assert "evolve_priority: 4" in content
    assert "evolve_confidence: 92%" in content
    assert "My Captured Skill" in content


# ── CAPTURED (home fallback) ─────────────────────────────────────────────────

def test_captured_fallback_uses_mimir_home_env(monkeypatch):
    tmp = tempfile.mkdtemp()
    home = Path(tmp) / "fake_home"
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(home))
    ctx = _make_ctx(
        EvolutionAction.CAPTURED,
        target="bare-captured-skill",
        reason="No source directory available",
        suggested_changes="",
        priority=2,
        confidence=0.75,
        skill_dir=None,
    )
    p = SkillEvolutionPipeline()
    result = asyncio.run(p._execute_evolution(ctx))

    assert result.success is True
    expected = home / "skills" / "bare-captured-skill"
    assert result.output_dir == expected
    assert expected.exists()
    content = (expected / "SKILL.md").read_text()
    assert "No source directory available" in content


# ── CAPTURED (empty content → failure) ───────────────────────────────────────

def test_captured_empty_content_returns_failure():
    tmp, src = _temp_skill_dir()
    ctx = _make_ctx(
        EvolutionAction.CAPTURED,
        target="empty-skill",
        reason="",
        suggested_changes="",
        skill_dir=src,
    )
    p = SkillEvolutionPipeline()
    result = asyncio.run(p._execute_evolution(ctx))

    assert result.success is False
    assert "No suggested_changes or reason" in result.error


# ── Unsupported action ───────────────────────────────────────────────────────

def test_unsupported_action_returns_failure():
    with patch.object(EvolutionAction, "__contains__", return_value=False):
        # Simulate an action that doesn't match any supported branch
        ctx = EvolutionContext(
            action=EvolutionAction.FIX,  # real action, but we bypass branches
            suggestion=EvolutionSuggestion(
                target="test-target",
                action="unknown",
                reason="should fail",
                suggested_changes="",
                priority=1,
                confidence=0.0,
            ),
        )
        # Create a context that will hit the else branch
        pass

    # More direct: test that an action not matching FIX/DERIVED/CAPTURED → failure
    # Since all enum values are covered, we test the else branch via a mock
    p = SkillEvolutionPipeline()

    # Use a context with an action that doesn't match any branch
    import types  # noqa: E402
    ctx = EvolutionContext(
        action=types.SimpleNamespace(value="bogus"),  # type: ignore
        suggestion=EvolutionSuggestion(
            target="test-target",
            action="bogus",
            reason="",
            suggested_changes="",
            priority=1,
            confidence=0.0,
        ),
    )
    result = asyncio.run(p._execute_evolution(ctx))
    assert result.success is False
    assert "Unsupported action" in result.error


# ── Stats ────────────────────────────────────────────────────────────────────

def test_stats_increment_with_successful_evolution():
    tmp, src = _temp_skill_dir()
    ctx = _make_ctx(
        EvolutionAction.FIX,
        target="source-skill",
        suggested_changes="---\nname: source-skill\n---\n\nFixed.\n",
        skill_dir=src,
        skill_content=(src / "SKILL.md").read_text(),
    )
    p = SkillEvolutionPipeline()
    asyncio.run(p._evolve_single(ctx))
    assert p.stats["total_evolved"] == 1
    assert p.stats["total_skipped"] == 0
