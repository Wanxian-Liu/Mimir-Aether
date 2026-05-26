"""Horizon Wave 7 · 1c DecisionRing + Compressor policy contract (IQ-EVO-43～45)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
POLICY_MOD = ROOT / "agent/decision_compressor_policy.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
DRAFT = ROOT / "docs/phase0/iqevo-1c-contract-draft.md"


def test_1c_never_writes_skill_md():
    """1C-01: 1c module must not import skill evolution write APIs."""
    text = POLICY_MOD.read_text(encoding="utf-8")
    forbidden = (
        "skill_evolution",
        "evolution_rollback",
        "SkillEvolutionPipeline",
        "write_skill_md_guarded",
        "create_skill_dir_guarded",
    )
    for token in forbidden:
        assert token not in text
    assert "SKILL.md" not in text


def test_1c_rejects_top3_keys_in_policy(tmp_path, monkeypatch):
    """1C-02: Top-3 keys cannot be persisted via apply_policy_patch."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_1C_POLICY", "1")

    from agent.decision_compressor_policy import apply_policy_patch, policy_path

    result = apply_policy_patch(
        {"ring": {"compressor.threshold_percent": 0.40}}
    )
    assert result.get("rejected") is True
    assert not policy_path().is_file() or "compressor.threshold_percent" not in policy_path().read_text(
        encoding="utf-8"
    )

    result2 = apply_policy_patch({"compressor.threshold_percent": 0.40})
    assert result2.get("rejected") is True


def test_wave7_1c_contract_in_tier0():
    assert "test_horizon_iqevo_wave7_1c.py" in TIER0.read_text(encoding="utf-8")


def test_1c_draft_exists():
    assert DRAFT.is_file()
    assert "1C-01" in DRAFT.read_text(encoding="utf-8")


def test_1c_policy_bounds_reject_out_of_range(tmp_path, monkeypatch):
    """1C-04: out-of-range compressor/ring values are rejected."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_1C_POLICY", "1")

    from agent.decision_compressor_policy import apply_policy_patch

    r1 = apply_policy_patch({"compressor": {"protect_first_n": 0}})
    assert r1.get("rejected") is True
    r2 = apply_policy_patch({"ring": {"max_retries": 99}})
    assert r2.get("rejected") is True


def test_1c_at_most_two_nudges_per_close(tmp_path, monkeypatch):
    """1C-05: one close applies at most one D* and one C* (≤2 audit keys)."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_1C_POLICY", "1")

    from agent.decision_compressor_policy import run_1c_policy_after_pipeline_close

    pipeline = {
        "errors": [{"tool_name": "x"}, {"tool_name": "y"}, {"tool_name": "z"}],
        "degraded_tools": ["a", "b"],
        "tune_changes": [],
    }
    entries = run_1c_policy_after_pipeline_close(
        pipeline, session_id="s1", task_name="t"
    )
    keys = [e.get("key") for e in entries if e.get("ok")]
    assert len(keys) <= 2
    assert sum(1 for k in keys if k and k.startswith("ring.")) <= 1
    assert sum(1 for k in keys if k and k.startswith("compressor.")) <= 1


def test_1c_never_calls_set_override(tmp_path, monkeypatch):
    """1C-03: 1c learner must not call tuned_thresholds.set_override."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_1C_POLICY", "1")

    from agent.decision_compressor_policy import run_1c_policy_after_pipeline_close

    pipeline = {
        "errors": [{"tool_name": "x"}, {"tool_name": "y"}],
        "degraded_tools": ["a", "b"],
        "tune_changes": [],
    }
    with patch("agent.tuned_thresholds.set_override") as mock_so:
        run_1c_policy_after_pipeline_close(pipeline, session_id="s2", task_name="t")
        mock_so.assert_not_called()


def test_1c_env_gate_off_by_default(tmp_path, monkeypatch):
    """1C-06: without MIMIR_AUTO_1C_POLICY, run_1c does not create policy file."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("MIMIR_AUTO_1C_POLICY", raising=False)

    from agent.decision_compressor_policy import (
        policy_path,
        run_1c_policy_after_pipeline_close,
    )

    assert run_1c_policy_after_pipeline_close(
        {"errors": [{"tool_name": "x"}]},
        session_id="off",
    ) == []
    assert not policy_path().is_file()


def test_1c_and_evolve_disjoint_persistence(tmp_path, monkeypatch):
    """1C-07: 1c nudge does not touch skills/ or tuned_thresholds.json."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_1C_POLICY", "1")

    skill_md = tmp_path / "skills" / "evolve-target" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("# before evolve\n", encoding="utf-8")

    tuned = tmp_path / "data" / "tuned_thresholds.json"
    tuned.parent.mkdir(parents=True)
    tuned_before = '{"schema_version":1,"overrides":{"compressor.threshold_percent":0.45}}'
    tuned.write_text(tuned_before, encoding="utf-8")

    from agent.decision_compressor_policy import run_1c_policy_after_pipeline_close

    with patch("agent.tuned_thresholds.set_override") as mock_so:
        with patch(
            "agent.execution_pipeline.apply_evolution_from_analysis",
            return_value=[],
        ) as mock_evo:
            run_1c_policy_after_pipeline_close(
                {
                    "errors": [{"tool_name": "x"}, {"tool_name": "y"}],
                    "degraded_tools": ["a"],
                    "tune_changes": [],
                },
                session_id="disjoint",
                task_name="t",
            )
            mock_evo.assert_not_called()
            mock_so.assert_not_called()

    assert skill_md.read_text(encoding="utf-8") == "# before evolve\n"
    assert tuned.read_text(encoding="utf-8") == tuned_before


def test_1c_b4_close_chain_wiring():
    """§49 checklist: tune→1c in close; post_analysis tail delegates tune+1c."""
    ep = (ROOT / "agent/execution_pipeline.py").read_text(encoding="utf-8")
    pca = (ROOT / "agent/post_close_analysis.py").read_text(encoding="utf-8")
    assert "defer_tune_and_1c" in ep
    assert "run_tune_after_pipeline_close" in ep
    assert "run_1c_policy_after_pipeline_close" in ep
    assert "run_tune_and_1c_after_post_analysis" in pca
    assert POLICY_MOD.read_text(encoding="utf-8").count("set_override") == 0
