"""
Tests: Curator Auto-Pass & Pin Mechanism

Verifies:
1. pin_skill / unpin_skill / is_pinned / list_pinned
2. run_curation_pass(dry_run=True) skips pinned skills
3. run_curation_pass(dry_run=True) reports correctly
4. format_curation_pass_result produces readable output
5. cron_curator_pass integration
6. Module compiles & imports cleanly

Author: MimirAether (self-evolved)
"""

import pytest
import sys
from pathlib import Path

# Ensure agent/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.skill_curator import (
    pin_skill, unpin_skill, is_pinned, list_pinned,
    run_curation_pass, format_curation_pass_result,
    cron_curator_pass,
    scan_skills, assess_staleness,
    SkillStatus, CuratorAction,
)


class TestPinMechanism:
    """Pin/unpin/list/is_pinned."""

    def test_pin_new_skill(self):
        """Pin a skill that isn't pinned yet."""
        name = "test-pin-curator-xyz"
        # Ensure not pinned
        if is_pinned(name):
            unpin_skill(name)
        assert pin_skill(name) is True
        assert is_pinned(name) is True
        assert name in list_pinned()
        # Cleanup
        unpin_skill(name)

    def test_pin_duplicate_returns_false(self):
        """Pinning already-pinned returns False."""
        name = "test-dup-pin-xyz"
        pin_skill(name)
        assert pin_skill(name) is False  # already pinned
        unpin_skill(name)

    def test_unpin_nonexistent(self):
        """Unpinning non-pinned returns False."""
        assert unpin_skill("nonexistent-skill-xyz") is False

    def test_unpin_removes(self):
        """Unpinning removes from list."""
        name = "test-remove-pin-xyz"
        pin_skill(name)
        assert unpin_skill(name) is True
        assert not is_pinned(name)
        assert name not in list_pinned()

    def test_is_pinned_false_by_default(self):
        """Unpinned skill returns False."""
        assert is_pinned("completely-unknown-skill-xyz") is False

    def test_multiple_pins(self):
        """Multiple skills can be pinned independently."""
        names = ["test-multi-a-xyz", "test-multi-b-xyz"]
        for n in names:
            pin_skill(n)
        assert all(is_pinned(n) for n in names)
        assert set(names) <= set(list_pinned())
        for n in names:
            unpin_skill(n)


class TestRunCurationPassDryRun:
    """run_curation_pass in dry_run mode."""

    def test_dry_run_returns_structured(self):
        """Dry run returns expected keys."""
        result = run_curation_pass(dry_run=True)
        assert "summary" in result
        assert "actions" in result
        assert "errors" in result
        assert result["dry_run"] is True

    def test_dry_run_summary_has_counts(self):
        """Summary has meaningful counts."""
        result = run_curation_pass(dry_run=True)
        s = result["summary"]
        assert "total" in s
        assert s["total"] > 0  # We have 106 skills
        assert s["fresh"] + s["stale"] + s["dormant"] == s["total"]

    def test_dry_run_pinned_skipped(self):
        """Pinned skills appear as skipped in pass."""
        name = "test-curator-dryrun-xyz"
        pin_skill(name)

        result = run_curation_pass(dry_run=True)
        # Pinned count should include our test skill
        assert name in result["summary"]["pinned_list"]

        unpin_skill(name)

    def test_dry_run_no_mutations(self):
        """Dry run must never mutate."""
        before = scan_skills()
        result = run_curation_pass(dry_run=True)
        after = scan_skills()
        # Counts unchanged
        assert len(before) == len(after)
        # No skills capsulized
        assert result["summary"]["capsulized"] == 0


class TestFormatCurationPassResult:
    """format_curation_pass_result output."""

    def test_format_dry_run_empty(self):
        """Format of a dry run with no issues."""
        # With 0 dormants and fresh all around, output is clean
        result = run_curation_pass(dry_run=True)
        formatted = format_curation_pass_result(result)
        assert "[DRY RUN]" in formatted
        assert "total" in formatted.lower() or str(result["summary"]["total"]) in formatted

    def test_format_includes_actions_when_present(self):
        """Format lists actions."""
        # Directly construct a result with actions
        result = {
            "summary": {"total": 1, "fresh": 0, "stale": 0, "dormant": 1,
                        "pinned": 0, "pinned_list": [],
                        "capsulized": 0, "archived": 0, "skipped_pinned": 0},
            "actions": [{
                "name": "test-dormant",
                "action": CuratorAction.CAPSULIZE_NOW,
                "reason": "60天未触",
                "days_since": 70,
                "result": "dry_run",
            }],
            "dry_run": True,
            "errors": [],
        }
        formatted = format_curation_pass_result(result)
        assert "test-dormant" in formatted
        assert "60天未触" in formatted


class TestCronCuratorPass:
    """cron_curator_pass integration."""

    def test_cron_returns_string(self):
        """cron_curator_pass returns a formatted string."""
        report = cron_curator_pass(dry_run=True)
        assert isinstance(report, str)
        assert "Curator Pass" in report

    def test_cron_dry_run_no_mutations(self):
        """Cron dry run doesn't mutate."""
        before = scan_skills()
        cron_curator_pass(dry_run=True)
        after = scan_skills()
        assert len(before) == len(after)


class TestCompileAndImport:
    """Ensure module compiles cleanly."""

    def test_compile(self):
        """function auto-docstring. """
        import py_compile
        py_compile.compile("agent/skill_curator.py", doraise=True)

    def test_import_all(self):
        """All __all__ symbols are importable."""
        from agent.skill_curator import __all__ as all_names
        for name in all_names:
            obj = getattr(sys.modules["agent.skill_curator"], name, None)
            assert obj is not None, f"__all__ entry '{name}' not found in module"
