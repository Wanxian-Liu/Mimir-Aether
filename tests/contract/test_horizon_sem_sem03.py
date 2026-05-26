"""SEM-03 / Horizon A: semantic session_search backends."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
TOOL = ROOT / "tools/session_search_tool.py"


def test_session_search_tool_documents_semantic_backends():
    text = TOOL.read_text(encoding="utf-8")
    assert "semantic_hybrid" in text
    assert "_session_search_via_semantic" in text
    assert '"like", "fts5", "hybrid", "semantic", "semantic_hybrid"' in text
    assert "_DEFAULT_SESSION_SEARCH_BACKEND" in text
    assert '"hybrid"' in text


def test_backlog_section14_sem03_done_sem04_next():
    text = BACKLOG.read_text(encoding="utf-8")
    section = text.split("## 14. Horizon", 1)[1]
    assert "**SEM-03**" in section
    sem03 = section.split("**SEM-03**", 1)[1][:120]
    assert "[x]" in sem03
    assert "**SEM-04**" in section
    sem04 = section.split("**SEM-04**", 1)[1][:120]
    assert "[x]" in sem04
    assert "**SEM-05**" in section
    sem05 = section.split("**SEM-05**", 1)[1][:120]
    assert "[x]" in sem05
    assert "**SEM-06**" in section
    sem06 = section.split("**SEM-06**", 1)[1][:120]
    assert "[x]" in sem06
