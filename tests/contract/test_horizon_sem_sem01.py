"""SEM-01 / Horizon A: P2-LONG-SEM kickoff artifacts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "docs/adr/006-semantic-memory-chromadb.md"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
PATH_CONTRACT = ROOT / "docs/path-contract.md"


def test_adr006_proposed_and_names_chroma_path():
    assert ADR.is_file()
    text = ADR.read_text(encoding="utf-8")
    assert "Accepted" in text or "Proposed" in text
    assert "chroma_sessions" in text
    assert "semantic_hybrid" in text


def test_path_contract_documents_chroma_under_mimir_data_dir():
    text = PATH_CONTRACT.read_text(encoding="utf-8")
    assert "ADR-006" in text
    assert "chroma_sessions" in text
    assert "get_mimir_data_dir()" in text


def test_backlog_section14_sem01_done_sem02_next():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "## 14. Horizon" in text
    section = text.split("## 14. Horizon", 1)[1]
    assert "**SEM-01**" in section
    sem01 = section.split("**SEM-01**", 1)[1][:120]
    assert "[x]" in sem01
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
