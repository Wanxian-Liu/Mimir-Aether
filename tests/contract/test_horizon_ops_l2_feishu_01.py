"""Horizon ops · OPS-L2-FEISHU-01 contract (Feishu /new L2 prefetch)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "agent" / "cross_session_retrieval.py"
GATEWAY = ROOT / "gateway" / "agent_mixin.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs" / "phase0" / "ops-l2-feishu-01-closeout.md"
TESTS = ROOT / "tests" / "agent" / "test_cross_session_retrieval_feishu.py"


def test_ops_l2_feishu_01_session_key_resolution():
    text = MODULE.read_text(encoding="utf-8")
    assert "MIMIR_SESSION_KEY" in text
    assert "get_session_env" in text
    assert "get_current_session_key" in text


def test_ops_l2_feishu_01_gateway_rebind_after_dotenv():
    text = GATEWAY.read_text(encoding="utf-8")
    assert "MIMIR_SESSION_KEY" in text
    assert "load_dotenv(override=True)" in text or "load_dotenv" in text


def test_ops_l2_feishu_01_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_horizon_ops_l2_feishu_01.py" in tier0
    assert "test_cross_session_retrieval_feishu.py" in tier0


def test_ops_l2_feishu_01_closeout_exists():
    assert CLOSEOUT.is_file()
    assert TESTS.is_file()
