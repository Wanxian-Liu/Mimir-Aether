"""Horizon C · ENGINE-GW-01 contract (Gateway ten-item summary)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "docs" / "GATEWAY_STABILITY_BACKLOG.md"
CLOSEOUT = ROOT / "docs" / "phase0" / "engine-gw-01-closeout.md"
WS_CLOSEOUT = ROOT / "docs" / "phase0" / "engine-ws-01-closeout.md"
TIER0 = ROOT / "run_ralph_tier0.sh"


def test_engine_gw_01_backlog_completion_definition():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "STAB-07" in text
    assert "完成定义" in text


def test_engine_gw_01_ten_rows_documented():
    import re

    text = BACKLOG.read_text(encoding="utf-8")
    for n in range(1, 11):
        assert re.search(rf"\|\s*{n}\s+\|", text), f"row {n} missing in GATEWAY_STABILITY_BACKLOG"


def test_engine_gw_01_closeout_and_ws_evidence():
    assert CLOSEOUT.is_file()
    assert WS_CLOSEOUT.is_file()
    closeout = CLOSEOUT.read_text(encoding="utf-8")
    assert "无新 P0" in closeout or "STAB" in closeout


def test_engine_gw_01_tier0_registration():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_horizon_engine_gw_01.py" in tier0
