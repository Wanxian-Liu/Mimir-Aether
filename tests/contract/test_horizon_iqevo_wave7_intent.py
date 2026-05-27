"""Wave 7 IQ-EVO-47 Intent MVP contract (tier0 manifest)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIER0 = ROOT / "run_ralph_tier0.sh"


def test_intent_predictor_module_exists():
    path = ROOT / "agent" / "intent_predictor.py"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "class IntentPrediction" in text
    assert "def predict(" in text


def test_wave7_intent_contract_in_tier0():
    assert "test_horizon_iqevo_wave7_intent.py" in TIER0.read_text(encoding="utf-8")


def test_intent_wired_in_core_loop():
    text = (ROOT / "agent" / "core_loop.py").read_text(encoding="utf-8")
    assert "intent_predictor" in text
    assert "_intent_context_block" in text
