"""Horizon C Wave 15+ · ENGINE-WS-01 contract (STAB-01/06 evidence)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_AGENT = ROOT / "run_agent.py"
FEISHU = ROOT / "gateway" / "platforms" / "feishu_adapter.py"
AGENT_MIXIN = ROOT / "gateway" / "agent_mixin.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs" / "phase0" / "engine-ws-01-closeout.md"
STAB_BACKLOG = ROOT / "docs" / "GATEWAY_STABILITY_BACKLOG.md"
ACTIVITY_TEST = ROOT / "tests" / "test_run_agent_activity.py"
WS_TEST = ROOT / "tests" / "test_feishu_ws_dispatch.py"


def test_engine_ws_01_activity_heartbeat_in_run_agent():
    text = RUN_AGENT.read_text(encoding="utf-8")
    assert "_ACTIVITY_HEARTBEAT_INTERVAL" in text
    assert "_activity_heartbeat" in text
    assert "get_activity_summary" in text
    assert "STAB-01" in text


def test_engine_ws_01_feishu_nonblocking_dispatch():
    text = FEISHU.read_text(encoding="utf-8")
    assert "run_coroutine_threadsafe" in text
    assert "_sync_p2_im_message_receive_v1" in text
    assert "STAB-01" in text


def test_engine_ws_01_gateway_inactivity_poll():
    text = AGENT_MIXIN.read_text(encoding="utf-8")
    assert "get_activity_summary" in text
    assert "seconds_since_activity" in text
    assert "inactivity" in text.lower()


def test_engine_ws_01_stab_backlog_documents_coverage():
    text = STAB_BACKLOG.read_text(encoding="utf-8")
    assert "STAB-01" in text
    assert "STAB-06" in text or "activity" in text


def test_engine_ws_01_tests_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_run_agent_activity.py" in tier0
    assert "test_feishu_ws_dispatch.py" in tier0
    assert "test_horizon_engine_ws_01.py" in tier0


def test_engine_ws_01_closeout_exists():
    assert CLOSEOUT.is_file()
    assert ACTIVITY_TEST.is_file()
    assert WS_TEST.is_file()
