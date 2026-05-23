"""
E-007 — evolution security baseline tests.

D5-0: recorder session isolation
D5-0b: skill path whitelist
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.execution_pipeline import (
    close_execution_pipeline,
    get_recorder,
    record_tool_call,
    start_execution_pipeline,
)
from agent.execution_pipeline_sessions import reset_execution_pipeline_state
from agent.post_analysis import EvolutionSuggestion
from agent.skill_evolution import EvolutionAction, EvolutionContext, SkillEvolutionPipeline
from agent.skill_path_guard import is_valid_skill_target, resolve_skill_dir


def setup_function():
    reset_execution_pipeline_state()


def teardown_function():
    reset_execution_pipeline_state()


def test_recorder_isolated_per_session(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))

    start_execution_pipeline(task_name="task-a", session_id="sess-a")
    start_execution_pipeline(task_name="task-b", session_id="sess-b")

    record_tool_call("echo", {"text": "a"}, session_id="sess-a", result_summary="a")
    record_tool_call("echo", {"text": "b"}, session_id="sess-b", result_summary="b")

    result_a = close_execution_pipeline(session_id="sess-a")
    assert result_a["summary"]["tool_calls"] == 1
    assert get_recorder(session_id="sess-b") is not None

    result_b = close_execution_pipeline(session_id="sess-b")
    assert result_b["summary"]["tool_calls"] == 1


def test_skill_path_guard_blocks_traversal():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "safe-skill").mkdir()
        (base / "safe-skill" / "SKILL.md").write_text("# ok", encoding="utf-8")

        assert is_valid_skill_target("../etc") is False
        assert is_valid_skill_target("safe-skill") is True
        assert resolve_skill_dir(base, "../safe-skill") is None
        assert resolve_skill_dir(base, "safe-skill") == (base / "safe-skill").resolve()


def test_skill_evolution_rejects_unsafe_target():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        ctx = EvolutionContext(
            action=EvolutionAction.CAPTURED,
            suggestion=EvolutionSuggestion(
                target="../../escape",
                action="captured",
                reason="bad path",
                suggested_changes="# evil",
                priority=1,
                confidence=0.5,
            ),
            skill_dir=None,
        )
        pipeline = SkillEvolutionPipeline(require_confirmation=False)
        result = asyncio.run(pipeline._execute_evolution(ctx))

        assert result.success is False
        assert "whitelist" in result.error.lower()
