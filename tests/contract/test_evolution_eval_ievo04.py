"""IEVO-04: evolution eval script and baseline compare logic."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from compare_memory_retrieval_baseline import compare_memory_retrieval_report
RUN_SCRIPT = ROOT / "scripts" / "run_evolution_eval.sh"
COMPARE_SCRIPT = ROOT / "scripts" / "compare_memory_retrieval_baseline.py"
BASELINE = ROOT / "docs" / "phase0" / "memory-retrieval-benchmark-20260524.json"


def test_run_evolution_eval_script_exists():
    assert RUN_SCRIPT.is_file()
    assert RUN_SCRIPT.stat().st_mode & 0o111


def test_compare_passes_when_at_baseline():
    baseline = {"like_hit_rate": 0.6, "fts_hit_rate": 0.5, "fts_db": "/x/fts5_search.db", "queries": 20}
    current = dict(baseline)
    summary = compare_memory_retrieval_report(current, baseline)
    assert summary["pass"] is True


def test_compare_fails_on_like_regression():
    baseline = {"like_hit_rate": 0.6, "fts_hit_rate": 0.5, "fts_db": "/x/fts5_search.db", "queries": 20}
    current = {"like_hit_rate": 0.4, "fts_hit_rate": 0.5, "fts_db": "/x/fts5_search.db", "queries": 20}
    summary = compare_memory_retrieval_report(current, baseline)
    assert summary["pass"] is False
    assert summary["like_hit_rate"]["ok"] is False


def test_compare_semantic_skipped_for_legacy_baseline():
    baseline = {
        "like_hit_rate": 0.6,
        "fts_hit_rate": 0.5,
        "fts_db": "/x/fts5_search.db",
        "semantic_hit_rate": None,
        "queries": 20,
    }
    current = dict(baseline, semantic_hit_rate=0.4)
    summary = compare_memory_retrieval_report(current, baseline)
    assert summary["pass"] is True
    assert summary["semantic_hit_rate"]["skipped"] is True


def test_compare_cli_against_repo_baseline(tmp_path: Path):
    assert BASELINE.is_file()
    current = json.loads(BASELINE.read_text(encoding="utf-8"))
    current_path = tmp_path / "current.json"
    current_path.write_text(json.dumps(current), encoding="utf-8")
    proc = subprocess.run(
        [
            "python3",
            str(COMPARE_SCRIPT),
            str(current_path),
            "--baseline",
            str(BASELINE),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
