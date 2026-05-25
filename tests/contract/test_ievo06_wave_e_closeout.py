"""IEVO-06: P2-LONG-IEVO wave closeout — tier0 manifest + D8 evidence."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs/phase0/p2-long-iev0-closeout.md"

# Full Wave E contract + regression bundle (sync with run_ralph_tier0.sh).
WAVE_E_TIER0 = (
    "tests/contract/test_no_simulated_evolution_ievo01.py",
    "tests/contract/test_evolution_tier0_manifest_ievo02.py",
    "tests/contract/test_observability_sot_ievo03.py",
    "tests/contract/test_evolution_eval_ievo04.py",
    "tests/agent/test_ievo05_monitor_insights_regression.py",
    "tests/contract/test_monitor_insights_ievo05.py",
    "tests/contract/test_ievo06_wave_e_closeout.py",
)

D8_ARTIFACTS = (
    "agent/evolution_audit.py",
    "docs/adr/005-observability-execution-sot.md",
    "scripts/run_evolution_eval.sh",
    "scripts/compare_memory_retrieval_baseline.py",
    "docs/phase0/memory-retrieval-benchmark-20260524.json",
)


def test_wave_e_closeout_doc_exists():
    assert CLOSEOUT.is_file()
    text = CLOSEOUT.read_text(encoding="utf-8")
    assert "IEVO-06" in text
    assert "D8" in text


def test_wave_e_tier0_paths_listed_in_run_ralph_tier0():
    text = TIER0.read_text(encoding="utf-8")
    missing = [p for p in WAVE_E_TIER0 if p not in text]
    assert not missing, "add to run_ralph_tier0.sh:\n" + "\n".join(missing)


def test_d8_industrial_evolution_mvp_artifacts_present():
    missing = [p for p in D8_ARTIFACTS if not (ROOT / p).is_file()]
    assert not missing, "missing D8 artifact:\n" + "\n".join(missing)


def test_backlog_marks_iev0_sub_items_done():
    text = (ROOT / "docs/MIMIR_EXEC_BACKLOG.md").read_text(encoding="utf-8")
    for item in ("IEVO-01", "IEVO-02", "IEVO-03", "IEVO-04", "IEVO-05", "IEVO-06"):
        assert item in text
    # Closeout row must be checked (IEVO-06 done).
    assert "**IEVO-06**" in text
    assert "IEVO-06" in text and "[x]" in text.split("IEVO-06")[1][:80]
