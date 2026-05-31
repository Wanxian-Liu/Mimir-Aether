"""D5-ADR: ADR-008 evolution canonical path must exist and name production SoT."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "docs" / "adr" / "008-evolution-canonical-path.md"

_REQUIRED_PHRASES = (
    "skill_evolution",
    "MIMIR_AUTO_EVOLVE",
    "apply_evolution_from_analysis",
    "Path A",
    "synthetic_sessions",
)


def test_adr_008_evolution_canonical_path_exists():
    assert ADR.is_file(), f"missing ADR: {ADR}"


def test_adr_008_names_canonical_production_path():
    text = ADR.read_text(encoding="utf-8")
    missing = [p for p in _REQUIRED_PHRASES if p not in text]
    assert not missing, "ADR-008 must document:\n" + "\n".join(missing)
