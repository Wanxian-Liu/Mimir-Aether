"""Bridge Wave 9 contract — backlog §18 migration items."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
BRIDGE = ROOT / "docs/MIMIR_LIU_CURSOR_BRIDGE.md"
TIER0 = ROOT / "run_ralph_tier0.sh"


def test_backlog_section18_present():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "## 18." in text
    assert "BRIDGE-CTX-B02" in text
    assert "HERM-SDH-01" in text
    assert "HERM-TGR-01" in text


def test_bridge_section6_points_to_backlog():
    text = BRIDGE.read_text(encoding="utf-8")
    assert "§18" in text or "MIMIR_EXEC_BACKLOG" in text
    assert "Hermes" in text and "OpenSpace" in text


def test_wave9_tests_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_bridge_wave9.py" in tier0
    assert "test_horizon_bridge_wave9.py" in tier0
