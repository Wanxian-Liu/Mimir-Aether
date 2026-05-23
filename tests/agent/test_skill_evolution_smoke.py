"""
EP-C03 — skill_evolution smoke tests (tests/agent/).

Three stub paths (no network, temp dirs only):
  1. parse_confirmation — JSON proceed gate
  2. FIX — in-place SKILL.md repair
  3. DERIVED — enhanced skill dir + derived_from tag
"""

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
    EvolutionContext,
    SkillEvolutionPipeline,
    parse_confirmation,
)


def _make_ctx(action, target, *, suggested_changes="", skill_dir=None):
    return EvolutionContext(
        action=action,
        suggestion=EvolutionSuggestion(
            target=target,
            action=action.value,
            reason="smoke test",
            suggested_changes=suggested_changes,
            priority=3,
            confidence=0.9,
        ),
        skill_dir=skill_dir,
    )


def _temp_source_skill():
    tmp = tempfile.mkdtemp()
    src = Path(tmp) / "demo-skill"
    src.mkdir()
    (src / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Smoke source\n---\n\n# Old\n",
        encoding="utf-8",
    )
    return tmp, src


def test_parse_confirmation_json_proceed_gate():
    assert parse_confirmation('{"proceed": true, "reason": "ok"}') is True
    assert parse_confirmation('{"proceed": false, "reason": "risky"}') is False
    assert parse_confirmation("```json\n{\"proceed\": true}\n```") is True


def test_skill_evolution_fix_smoke_writes_skill_md():
    _, src = _temp_source_skill()
    new_body = "---\nname: demo-skill\ndescription: Fixed\n---\n\n# Fixed body\n"
    ctx = _make_ctx(EvolutionAction.FIX, "demo-skill", suggested_changes=new_body, skill_dir=src)
    pipeline = SkillEvolutionPipeline(require_confirmation=False)
    result = asyncio.run(pipeline._execute_evolution(ctx))

    assert result.success is True
    assert result.action == EvolutionAction.FIX
    assert "# Fixed body" in (src / "SKILL.md").read_text(encoding="utf-8")
    assert result.diff != ""


def test_skill_evolution_derived_smoke_creates_enhanced_dir():
    _, src = _temp_source_skill()
    new_body = "---\nname: demo-skill\ndescription: Enhanced\n---\n\n# Enhanced\n"
    ctx = _make_ctx(
        EvolutionAction.DERIVED, "demo-skill", suggested_changes=new_body, skill_dir=src
    )
    pipeline = SkillEvolutionPipeline(require_confirmation=False)
    result = asyncio.run(pipeline._execute_evolution(ctx))

    assert result.success is True
    assert result.output_dir is not None
    assert result.output_dir.name == "demo-skill-enhanced"
    content = (result.output_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "derived_from" in content.lower()
    assert "# Enhanced" in content
