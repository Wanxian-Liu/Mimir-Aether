"""Horizon B1 · OBS-B1-03 — ISSUES #10 TRUNCATE monitoring closeout."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLOSEOUT = ROOT / "docs/phase0/obs-b1-03-issue10-closeout.md"
ISSUES = ROOT / "docs/MIMIR_ISSUES.md"
OPS_PANEL = ROOT / "docs/ops/MIMIR_OPS_PANEL.md"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
TIER0 = ROOT / "run_ralph_tier0.sh"


def test_closeout_documents_issue10_exception():
    assert CLOSEOUT.is_file()
    text = CLOSEOUT.read_text(encoding="utf-8")
    assert "#10" in text or "ISSUES #10" in text
    assert "documented exception" in text.lower()
    assert "MIMIR_TRUNCATE_SINCE_START_MAX" in text or "R4" in text
    assert "STAB-04" in text


def test_issues_10_not_in_active_section():
    text = ISSUES.read_text(encoding="utf-8")
    active_match = re.search(
        r"## Active.*?\n\n(.*?)\n\n---",
        text,
        re.DOTALL,
    )
    assert active_match, "Active section missing"
    active_body = active_match.group(1)
    assert "| 10 |" not in active_body
    assert "obs-b1-03-issue10-closeout" in text.lower()


def test_issues_10_archived_with_closeout_ref():
    text = ISSUES.read_text(encoding="utf-8")
    assert re.search(r"\|\s*10\s*\|.*obs-b1-03", text, re.IGNORECASE | re.DOTALL)


def test_ops_panel_points_at_since_start_kpi():
    text = OPS_PANEL.read_text(encoding="utf-8")
    assert "MIMIR_TRUNCATE_SINCE_START_MAX" in text
    assert "since-start" in text.lower() or "since gateway start" in text.lower()


def test_backlog_obs_b1_03_present():
    assert "**OBS-B1-03**" in BACKLOG.read_text(encoding="utf-8")


def test_obs_b1_03_contract_in_tier0():
    assert "tests/contract/test_horizon_obs_b1_03.py" in TIER0.read_text(encoding="utf-8")
