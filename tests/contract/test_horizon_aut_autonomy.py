"""Horizon §17 · P1-LONG-AUTONOMY — contract checks."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
OPS_TOOL = ROOT / "tools/mimir_ops_tool.py"
OPS_PANEL = ROOT / "docs/ops/MIMIR_OPS_PANEL.md"
CLOSEOUT = ROOT / "docs/phase0/p1-long-autonomy-closeout.md"
PROMPT = ROOT / "agent/prompt_builder.py"
SNAPSHOT = ROOT / "agent/context_usage_snapshot.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
AGENT_MIXIN = ROOT / "gateway/agent_mixin.py"


def test_backlog_section_17_present():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "## 17." in text
    assert "**AUTO-01**" in text
    assert "P1-LONG-AUTONOMY" in text


def test_mimir_ops_tool_registered():
    text = OPS_TOOL.read_text(encoding="utf-8")
    assert 'name="mimir_ops"' in text or "name='mimir_ops'" in text
    assert "health_check" in text
    assert "session_reset" in text


def test_ops_panel_autonomy_section():
    text = OPS_PANEL.read_text(encoding="utf-8")
    assert "mimir_ops" in text
    assert "/new" in text


def test_prompt_has_session_autonomy_guidance():
    assert "SESSION_AUTONOMY_GUIDANCE" in PROMPT.read_text(encoding="utf-8")


def test_context_usage_snapshot_module():
    assert "write_context_usage_snapshot" in SNAPSHOT.read_text(encoding="utf-8")


def test_gateway_consumes_session_reset_pending():
    text = AGENT_MIXIN.read_text(encoding="utf-8")
    assert "consume_session_reset_pending" in text


def test_closeout_doc_exists():
    assert CLOSEOUT.is_file()


def test_autonomy_contract_in_tier0():
    assert "tests/contract/test_horizon_aut_autonomy.py" in TIER0.read_text(encoding="utf-8")
