"""SEM-04: memory retrieval benchmark + baseline compare semantic leg."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from compare_memory_retrieval_baseline import compare_memory_retrieval_report
from run_memory_retrieval_benchmark import BENCHMARK_QUERIES, run_benchmark


def test_run_benchmark_includes_semantic_fields_when_index_ready(tmp_path):
    like_db = tmp_path / "sessions_search.db"
    like_db.write_bytes(b"")

    with patch(
        "run_memory_retrieval_benchmark._like_search",
        return_value=(0, 0.0),
    ), patch(
        "run_memory_retrieval_benchmark._semantic_search",
        return_value=(1, 1.0),
    ), patch(
        "tools.session_search_tool._semantic_index_ready",
        return_value=True,
    ), patch(
        "run_memory_retrieval_benchmark.BENCHMARK_QUERIES",
        BENCHMARK_QUERIES[:2],
    ):
        report = run_benchmark(like_db_path=str(like_db), fts_db_path=str(tmp_path / "missing.db"))

    assert report["semantic_chroma_dir"] is not None
    assert report["semantic_hit_rate"] == 1.0
    assert report["rows"][0]["semantic_hits"] == 1


def test_run_benchmark_omits_semantic_rate_when_index_missing(tmp_path):
    like_db = tmp_path / "sessions_search.db"
    like_db.write_bytes(b"")

    with patch(
        "run_memory_retrieval_benchmark._like_search",
        return_value=(0, 0.0),
    ), patch(
        "tools.session_search_tool._semantic_index_ready",
        return_value=False,
    ), patch(
        "run_memory_retrieval_benchmark.BENCHMARK_QUERIES",
        BENCHMARK_QUERIES[:1],
    ):
        report = run_benchmark(like_db_path=str(like_db), fts_db_path=str(tmp_path / "missing.db"))

    assert report["semantic_hit_rate"] is None
    assert report["semantic_chroma_dir"] is None


def test_compare_skips_semantic_when_baseline_null():
    baseline = {
        "like_hit_rate": 0.6,
        "fts_hit_rate": 0.5,
        "fts_db": "/x/fts5_search.db",
        "semantic_hit_rate": None,
        "queries": 20,
    }
    current = dict(baseline, semantic_hit_rate=0.45, semantic_chroma_dir="/x/chroma")
    summary = compare_memory_retrieval_report(current, baseline)
    assert summary["pass"] is True
    assert summary["semantic_hit_rate"]["skipped"] is True


def test_compare_fails_semantic_regression():
    baseline = {
        "like_hit_rate": 0.6,
        "fts_hit_rate": 0.5,
        "fts_db": "/x/fts5_search.db",
        "semantic_hit_rate": 0.55,
        "queries": 20,
    }
    current = dict(baseline, semantic_hit_rate=0.45)
    summary = compare_memory_retrieval_report(current, baseline)
    assert summary["pass"] is False
    assert summary["semantic_hit_rate"]["ok"] is False


def test_compare_passes_semantic_at_baseline():
    baseline = {
        "like_hit_rate": 0.6,
        "fts_hit_rate": 0.5,
        "fts_db": "/x/fts5_search.db",
        "semantic_hit_rate": 0.55,
        "queries": 20,
    }
    current = dict(baseline)
    summary = compare_memory_retrieval_report(current, baseline)
    assert summary["pass"] is True
    assert summary["semantic_hit_rate"]["ok"] is True
