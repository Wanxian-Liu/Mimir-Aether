"""SEM-05 / Horizon A: P2-LONG-SEM tier0 regression manifest (≥3 contract + smoke)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIER0 = ROOT / "run_ralph_tier0.sh"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"

# Keep in sync with run_ralph_tier0.sh Gate2 SEM wave entries.
SEM_TIER0_PATHS = (
    "tests/contract/test_horizon_sem_sem01.py",
    "tests/contract/test_horizon_sem_sem02.py",
    "tests/contract/test_horizon_sem_sem03.py",
    "tests/contract/test_horizon_sem_sem04.py",
    "tests/contract/test_horizon_sem_sem05.py",
    "tests/contract/test_horizon_sem_sem06.py",
    "tests/tools/test_chroma_session_indexer.py",
    "tests/tools/test_session_search_semantic.py",
    "tests/tools/test_memory_retrieval_benchmark_semantic.py",
    "tests/tools/test_sem05_smoke.py",
)


def test_sem_tier0_manifest_has_at_least_three_files():
    assert len(SEM_TIER0_PATHS) >= 3


def test_sem_tier0_paths_exist_on_disk():
    missing = [p for p in SEM_TIER0_PATHS if not (ROOT / p).is_file()]
    assert not missing, "missing SEM tier0 test files:\n" + "\n".join(missing)


def test_sem_tier0_paths_listed_in_run_ralph_tier0():
    text = TIER0.read_text(encoding="utf-8")
    missing = [p for p in SEM_TIER0_PATHS if p not in text]
    assert not missing, "add to run_ralph_tier0.sh:\n" + "\n".join(missing)


def test_backlog_section14_sem_wave_complete():
    text = BACKLOG.read_text(encoding="utf-8")
    section = text.split("## 14. Horizon", 1)[1]
    assert "**SEM-06**" in section
    sem06 = section.split("**SEM-06**", 1)[1][:120]
    assert "[x]" in sem06
