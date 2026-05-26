"""Horizon Wave 5 (IQ-EVO-20～25) contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WAVE5_PLAN = ROOT / "docs/phase0/p2-long-iqevo-wave5.md"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
TUNED = ROOT / "agent/tuned_thresholds.py"
EXPERIENCE = ROOT / "agent/experience_buffer.py"
AUTO_TUNER = ROOT / "agent/auto_tuner.py"
TIER0 = ROOT / "run_ralph_tier0.sh"

ENGINEERING_IDS = (
    "IQ-EVO-21",
    "IQ-EVO-22",
    "IQ-EVO-23",
    "IQ-EVO-24",
    "IQ-EVO-25",
)


def test_wave5_plan():
    text = WAVE5_PLAN.read_text(encoding="utf-8")
    assert "MIMIR_AUTO_TUNER" in text
    assert "1b" in text


def test_modules_exist():
    assert TUNED.is_file() and EXPERIENCE.is_file() and AUTO_TUNER.is_file()
    assert "compressor.threshold_percent" in TUNED.read_text(encoding="utf-8")
    assert "MIMIR_AUTO_TUNER" in AUTO_TUNER.read_text(encoding="utf-8")


def test_wiring():
    assert "run_tune_after_pipeline_close" in (ROOT / "agent/execution_pipeline.py").read_text(
        encoding="utf-8"
    )
    assert "get_tuned_int" in (ROOT / "agent/degeneration_guard.py").read_text(encoding="utf-8")
    assert "get_tuned_float" in (ROOT / "agent/core_loop.py").read_text(encoding="utf-8")


def test_backlog_wave5():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "Wave 5" in text
    for item in ENGINEERING_IDS:
        assert f"**{item}**" in text


def test_wave5_in_tier0():
    assert "test_horizon_iqevo_wave5.py" in TIER0.read_text(encoding="utf-8")
