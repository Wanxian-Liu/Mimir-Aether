"""Horizon C Wave 12 · HERM-RED-02 contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REDACT_RULES_MOD = ROOT / "agent" / "redact_rules.py"
REDACT = ROOT / "agent" / "redact.py"
RULES_JSON = ROOT / "data" / "redact_rules.json"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs" / "phase0" / "herm-red-02-closeout.md"


def test_herm_red_02_rules_module():
    text = REDACT_RULES_MOD.read_text(encoding="utf-8")
    for symbol in ("load_redact_rules", "resolve_redact_rules_path", "apply_configurable_redaction"):
        assert symbol in text


def test_herm_red_02_redact_wiring():
    redact = REDACT.read_text(encoding="utf-8")
    assert "apply_loaded_rules" in redact


def test_herm_red_02_default_rules_file():
    assert RULES_JSON.is_file()
    body = RULES_JSON.read_text(encoding="utf-8")
    assert "query_param_names" in body


def test_herm_red_02_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_redact_rules.py" in tier0
    assert "test_horizon_herm_red_02.py" in tier0


def test_herm_red_02_closeout_exists():
    assert CLOSEOUT.is_file()
