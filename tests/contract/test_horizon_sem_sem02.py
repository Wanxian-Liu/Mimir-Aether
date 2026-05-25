"""SEM-02 / Horizon A: Chroma persist + backfill indexer."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
INDEXER = ROOT / "tools/chroma_session_indexer.py"
BACKFILL = ROOT / "scripts/backfill_chroma_sessions.py"


def test_sem02_backfill_script_and_indexer_exist():
    assert INDEXER.is_file()
    assert BACKFILL.is_file()
    text = INDEXER.read_text(encoding="utf-8")
    assert "session_messages" in text
    assert "backfill_chroma_sessions" in text
    assert "upsert" in text


def test_mimir_constants_exposes_chroma_dir():
    from mimir_constants import get_mimir_chroma_dir

    path = get_mimir_chroma_dir()
    assert path.name == "chroma_sessions"
    assert path.parent.name == "data"


def test_backlog_section14_sem02_done_sem03_next():
    text = BACKLOG.read_text(encoding="utf-8")
    section = text.split("## 14. Horizon", 1)[1]
    assert "**SEM-02**" in section
    sem02 = section.split("**SEM-02**", 1)[1][:120]
    assert "[x]" in sem02
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
