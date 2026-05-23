"""ISSUES #7 — pipeline close → analysis → FIX on disk (env-gated auto evolve)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_pipeline_close_auto_evolve_writes_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_EVOLVE", "1")

    from agent.execution_pipeline import (
        apply_analysis_to_pipeline,
        apply_evolution_from_close_result,
        close_execution_pipeline,
        start_execution_pipeline,
    )
    from agent.execution_pipeline_sessions import reset_execution_pipeline_state

    reset_execution_pipeline_state()

    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "loop-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# before\n", encoding="utf-8")

    start_execution_pipeline(task_name="loop-task", session_id="loop-sess")

    analysis_json = json.dumps(
        {
            "summary": "tool failed repeatedly",
            "suggestions": [
                {
                    "target": "loop-skill",
                    "action": "fix",
                    "reason": "repair skill instructions",
                    "suggested_changes": "# after loop\n",
                    "priority": 1,
                    "confidence": 0.9,
                }
            ],
        }
    )
    apply_analysis_to_pipeline(analysis_json, session_id="loop-sess", task_name="loop-task")

    result = close_execution_pipeline(session_id="loop-sess")
    assert result["evolution_suggestions"]
    assert result.get("_evolution_suggestion_objs")

    apply_evolution_from_close_result(result, skills_dir=skills_dir)

    assert "# after loop" in (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert result.get("evolution_suggestions")
