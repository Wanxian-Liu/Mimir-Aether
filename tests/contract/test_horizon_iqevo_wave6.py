"""Horizon Wave 6 (IQ-EVO-27～39) contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WAVE6_PLAN = ROOT / "docs/phase0/p2-long-iqevo-wave6-qualified-agent.md"
CLOSEOUT = ROOT / "docs/phase0/p2-long-iqevo-wave6-closeout.md"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
TIER0 = ROOT / "run_ralph_tier0.sh"
HANDOFF = ROOT / "docs/superpowers/plans/2026-05-26-wave6-cursor-handoff.md"

WAVE6_IDS = tuple(f"IQ-EVO-{n}" for n in range(27, 40))


def test_wave6_plan_and_handoff():
    assert WAVE6_PLAN.is_file() and HANDOFF.is_file()
    text = WAVE6_PLAN.read_text(encoding="utf-8")
    assert "合格智能体" in text
    assert "IQ-EVO-38" in text


def test_wave6_artifacts():
    pb = ROOT / "agent/prompt_builder.py"
    assert "build_analysis_artifact_guidance" in pb.read_text(encoding="utf-8")
    assert (ROOT / "tools/wave6_evidence.py").is_file()
    assert (ROOT / "scripts/wave6_collect_evidence.py").is_file()
    assert (ROOT / "docs/ops/evolution-eval-weekly.md").is_file()


def test_backlog_wave6():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "Wave 6" in text
    for item in WAVE6_IDS:
        assert f"**{item}**" in text


def test_wave6_closeout_exists():
    assert CLOSEOUT.is_file()
    assert "4.8" in CLOSEOUT.read_text(encoding="utf-8") or "documented exception" in CLOSEOUT.read_text(
        encoding="utf-8"
    )


def test_wave6_in_tier0():
    assert "test_horizon_iqevo_wave6.py" in TIER0.read_text(encoding="utf-8")
