"""SEM-04 / Horizon A: benchmark + eval semantic leg."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
BENCHMARK = ROOT / "scripts/run_memory_retrieval_benchmark.py"
COMPARE = ROOT / "scripts/compare_memory_retrieval_baseline.py"
BASELINE = ROOT / "docs/phase0/memory-retrieval-benchmark-20260524.json"


def test_benchmark_and_compare_scripts_expose_semantic_hit_rate():
    assert "semantic_hit_rate" in BENCHMARK.read_text(encoding="utf-8")
    assert "semantic_hit_rate" in COMPARE.read_text(encoding="utf-8")


def test_frozen_baseline_has_semantic_fields():
    import json

    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert "semantic_hit_rate" in data
    assert data["semantic_hit_rate"] is None


def test_backlog_section14_sem04_done_sem05_next():
    text = BACKLOG.read_text(encoding="utf-8")
    section = text.split("## 14. Horizon", 1)[1]
    assert "**SEM-04**" in section
    sem04 = section.split("**SEM-04**", 1)[1][:120]
    assert "[x]" in sem04
    assert "**SEM-05**" in section
    sem05 = section.split("**SEM-05**", 1)[1][:120]
    assert "[x]" in sem05
    assert "**SEM-06**" in section
    sem06 = section.split("**SEM-06**", 1)[1][:120]
    assert "[x]" in sem06
