"""SEM-06 / Horizon A: P2-LONG-SEM wave closeout."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs/phase0/p2-long-sem-closeout.md"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"

SEM_ARTIFACTS = (
    "docs/adr/006-semantic-memory-chromadb.md",
    "tools/chroma_session_indexer.py",
    "scripts/backfill_chroma_sessions.py",
    "scripts/run_memory_retrieval_benchmark.py",
    "scripts/compare_memory_retrieval_baseline.py",
    "docs/phase0/p2-long-sem-closeout.md",
)

SEM_WAVE_IDS = (
    "SEM-01",
    "SEM-02",
    "SEM-03",
    "SEM-04",
    "SEM-05",
    "SEM-06",
)


def test_sem_closeout_doc_exists():
    assert CLOSEOUT.is_file()
    text = CLOSEOUT.read_text(encoding="utf-8")
    assert "SEM-06" in text
    assert "semantic_heavy" in text.lower() or "语义 query 子集" in text
    assert "#32" in text


def test_sem_wave_artifacts_present():
    missing = [p for p in SEM_ARTIFACTS if not (ROOT / p).is_file()]
    assert not missing, "missing SEM artifact:\n" + "\n".join(missing)


def test_backlog_section14_all_sem_items_done():
    section = BACKLOG.read_text(encoding="utf-8").split("## 14. Horizon", 1)[1]
    for item in SEM_WAVE_IDS:
        assert f"**{item}**" in section
        chunk = section.split(f"**{item}**", 1)[1][:120]
        assert "[x]" in chunk, f"{item} not marked done"


def test_p2_long_sem_marked_complete_in_section11():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "**P2-LONG-SEM**" in text
    # §11 parallel tasks table row should show [x] after closeout.
    section11 = text.split("## 11.", 1)[1].split("## 12.", 1)[0]
    sem_row = section11.split("**P2-LONG-SEM**", 1)[1][:160]
    assert "[x]" in sem_row


def test_sem06_closeout_test_listed_in_tier0():
    assert "tests/contract/test_horizon_sem_sem06.py" in TIER0.read_text(encoding="utf-8")
