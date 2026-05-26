"""SEM-07 / Horizon A: production semantic baseline + eval gate."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_20260526 = ROOT / "docs/phase0/memory-retrieval-benchmark-20260526.json"
EVAL_SCRIPT = ROOT / "scripts/run_evolution_eval.sh"
CLOSEOUT = ROOT / "docs/phase0/p2-long-sem-closeout.md"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
OPS_PANEL = ROOT / "docs/ops/MIMIR_OPS_PANEL.md"
TIER0 = ROOT / "run_ralph_tier0.sh"


def test_frozen_baseline_20260526_enables_semantic_gate():
    assert BASELINE_20260526.is_file()
    data = json.loads(BASELINE_20260526.read_text(encoding="utf-8"))
    assert data.get("semantic_hit_rate") is not None
    assert data.get("semantic_chroma_dir")
    assert data.get("frozen_at") == "2026-05-26"


def test_evolution_eval_defaults_to_20260526_baseline():
    text = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "memory-retrieval-benchmark-20260526.json" in text


def test_closeout_documents_sem07_and_iqevo11_incremental():
    text = CLOSEOUT.read_text(encoding="utf-8")
    assert "SEM-07" in text
    assert "IQ-EVO-11" in text or "MIMIR_CHROMA_INCREMENTAL" in text


def test_ops_panel_sem_production_section():
    text = OPS_PANEL.read_text(encoding="utf-8")
    assert "semantic_hybrid" in text
    assert "MIMIR_EMBED_MODEL" in text
    assert "backfill_chroma_sessions" in text


def test_backlog_sem07_done():
    section = BACKLOG.read_text(encoding="utf-8").split("## 14. Horizon", 1)[1]
    chunk = section.split("**SEM-07**", 1)[1].split("\n", 1)[0]
    assert "[x]" in chunk


def test_sem07_contract_in_tier0():
    assert "tests/contract/test_horizon_sem_sem07.py" in TIER0.read_text(encoding="utf-8")
