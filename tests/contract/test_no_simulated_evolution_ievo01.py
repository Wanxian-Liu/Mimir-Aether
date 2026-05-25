"""IEVO-01 / D5-1: production paths must not emit simulated:true pseudo-evolution markers."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from agent.evolution_audit import (
    assert_evolution_summary_allowed,
    scan_runtime_trees_for_simulated_evolution_markers,
)

ROOT = Path(__file__).resolve().parents[2]
EVOLUTION_LOG = ROOT / "docs" / "evolution_log.md"


def test_runtime_trees_no_simulated_true_markers():
    violations = scan_runtime_trees_for_simulated_evolution_markers(ROOT)
    assert not violations, "simulated:true in runtime tree:\n" + "\n".join(violations[:30])


def test_evolution_log_has_no_simulated_true_rows():
    text = EVOLUTION_LOG.read_text(encoding="utf-8", errors="ignore")
    hits = [
        f"line {i}: {line[:100]}"
        for i, line in enumerate(text.splitlines(), 1)
        if re.search(r"simulated\s*:\s*true", line, re.I)
    ]
    assert not hits, "docs/evolution_log.md must not contain simulated:true:\n" + "\n".join(
        hits[:10]
    )


@pytest.mark.parametrize(
    "summary",
    [
        "metrics: n/a; simulated: true",
        "simulated:true stub",
        '"simulated": true',
    ],
)
def test_assert_evolution_summary_rejects_simulated(summary: str):
    with pytest.raises(ValueError, match="simulated"):
        assert_evolution_summary_allowed(summary)


def test_assert_evolution_summary_allows_real_summary():
    assert_evolution_summary_allowed("IND-05: persistent_store; tier0 278+2 pass")
