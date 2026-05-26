"""Horizon Wave 3 (IQ-EVO-11～14) contract — Cursor grains 11～13."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
ROLLOUT = ROOT / "docs/ops/MIMIR_AUTO_ANALYSIS_ROLLOUT.md"
RUNTIME_CONTRACT = ROOT / "docs/MIMIR_RUNTIME_CONTRACT.md"
ENV_EXAMPLE = ROOT / ".env.example"
LIST_SCRIPT = ROOT / "scripts/list_analysis_artifacts.sh"
PROMPT_BUILDER = ROOT / "agent/prompt_builder.py"
SESSION_SEARCH_TOOL = ROOT / "tools/session_search_tool.py"
TIER0 = ROOT / "run_ralph_tier0.sh"

WAVE3_CURSOR_IDS = (
    "IQ-EVO-11",
    "IQ-EVO-12",
    "IQ-EVO-13",
)


def test_session_search_guidance_search_first():
    text = PROMPT_BUILDER.read_text(encoding="utf-8")
    assert "SESSION_SEARCH_GUIDANCE" in text
    assert "search-first" in text
    assert "MUST call" in text
    assert "session_search before answering" in text


def test_session_search_hybrid_default_iqevo11():
    text = SESSION_SEARCH_TOOL.read_text(encoding="utf-8")
    assert '_DEFAULT_SESSION_SEARCH_BACKEND = "hybrid"' in text
    assert "sync_message_to_chroma" in (ROOT / "tools/chroma_session_indexer.py").read_text(
        encoding="utf-8"
    )


def test_backlog_wave3_cursor_items_present():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "Wave 3" in text
    for item in WAVE3_CURSOR_IDS:
        assert f"**{item}**" in text


def test_wave3_contract_listed_in_tier0():
    text = TIER0.read_text(encoding="utf-8")
    assert "tests/contract/test_horizon_iqevo_wave3.py" in text


def test_auto_analysis_production_rollout_iqevo13():
    rollout = ROLLOUT.read_text(encoding="utf-8")
    assert "MIMIR_AUTO_ANALYSIS" in rollout
    assert "MIMIR_AUTO_EVOLVE" in rollout
    assert "analysis_artifacts" in rollout
    assert "7" in rollout
    assert LIST_SCRIPT.is_file()
    runtime = RUNTIME_CONTRACT.read_text(encoding="utf-8")
    assert "MIMIR_AUTO_ANALYSIS" in runtime
    assert "ops/MIMIR_AUTO_ANALYSIS_ROLLOUT.md" in runtime
    env = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "MIMIR_AUTO_ANALYSIS" in env
    assert "MIMIR_AUTO_EVOLVE" in env
