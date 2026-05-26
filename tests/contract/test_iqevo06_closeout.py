"""IQ-EVO-06: P2-LONG-IQEVO wave 1 closeout."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs/phase0/p2-long-iqevo-closeout.md"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"

IQ_EVO_WAVE_IDS = (
    "IQ-EVO-00",
    "IQ-EVO-01",
    "IQ-EVO-02",
    "IQ-EVO-03",
    "IQ-EVO-04",
    "IQ-EVO-05",
    "IQ-EVO-06",
)

IQ_EVO_ARTIFACTS = (
    "docs/MIMIR_IQ_EVOLUTION_DIRECTION.md",
    "docs/proposals/iq-evo-auto-analysis.md",
    "docs/phase0/iq-scoring-rubric.md",
    "scripts/run_evolution_eval.sh",
)


def test_iqevo_closeout_doc_exists():
    assert CLOSEOUT.is_file()
    text = CLOSEOUT.read_text(encoding="utf-8")
    assert "IQ-EVO-06" in text
    assert "3.9" in text or "documented exception" in text.lower()
    assert "run_evolution_eval" in text


def test_iqevo_wave_artifacts_present():
    missing = [p for p in IQ_EVO_ARTIFACTS if not (ROOT / p).is_file()]
    assert not missing, "missing IQ-EVO artifact:\n" + "\n".join(missing)


def test_backlog_section15_all_iq_evo_items_done():
    section = BACKLOG.read_text(encoding="utf-8").split("## 15.", 1)[1].split("## ", 1)[0]
    for item in IQ_EVO_WAVE_IDS:
        assert f"**{item}**" in section
        line = next(ln for ln in section.splitlines() if f"**{item}**" in ln)
        assert "[x]" in line, f"{item} not marked done"


def test_iqevo06_closeout_test_listed_in_tier0():
    assert "tests/contract/test_iqevo06_closeout.py" in TIER0.read_text(encoding="utf-8")
