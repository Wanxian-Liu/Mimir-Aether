"""CLEARANCE-DONE: P0-LONG-CLEARANCE §0 D1–D8 evidence on disk."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DONE_DOC = ROOT / "docs/phase0/p0-long-clearance-done.md"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"


def test_clearance_done_doc_exists_and_claims_8_of_8():
    assert DONE_DOC.is_file()
    text = DONE_DOC.read_text(encoding="utf-8")
    assert "CLEARANCE-DONE" in text
    assert "D1" in text and "D8" in text
    assert "326+2" in text or "tier0" in text


def test_backlog_marks_clearance_done_checked():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "**CLEARANCE-DONE**" in text
    block = text.split("**CLEARANCE-DONE**", 1)[1][:120]
    assert "[x]" in block


def test_github_open_count_documented_as_three_or_fewer():
    text = DONE_DOC.read_text(encoding="utf-8")
    assert "3 open" in text or "**3**" in text
