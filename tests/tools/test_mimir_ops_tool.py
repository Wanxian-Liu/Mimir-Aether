"""Unit tests for tools.mimir_ops_tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import mimir_ops_tool as ops


def test_allowlist_has_expected_actions():
    assert "health_check" in ops._ALLOWLIST
    assert "gateway_restart" in ops._ALLOWLIST


def test_gateway_restart_requires_confirm_and_env(monkeypatch):
    monkeypatch.delenv("MIMIR_OPS_ALLOW_GATEWAY_RESTART", raising=False)
    out = json.loads(ops.mimir_ops("gateway_restart", confirm=False))
    assert out["ok"] is False

    out2 = json.loads(ops.mimir_ops("gateway_restart", confirm=True))
    assert out2["ok"] is False
    assert "MIMIR_OPS_ALLOW_GATEWAY_RESTART" in out2.get("error", "")


def test_session_reset_pending_roundtrip(tmp_path, monkeypatch):
    ops_dir = tmp_path / "data" / "ops"
    ops_dir.mkdir(parents=True)
    monkeypatch.setattr(ops, "_ops_data_dir", lambda: ops_dir)
    monkeypatch.setattr(ops, "_session_reset_pending_path", lambda: ops_dir / "session_reset_pending.json")

    ops.request_session_reset("feishu:chat1:user1", reason="test")
    assert ops.consume_session_reset_pending("feishu:chat1:user1") is True
    assert ops.consume_session_reset_pending("feishu:chat1:user1") is False


def test_context_usage_returns_structure(monkeypatch):
    snap_path = Path(ops._ops_data_dir()) / "last_context_usage.json"
    monkeypatch.setattr(
        "agent.context_usage_snapshot.read_context_usage_snapshot",
        lambda: {"prompt_tokens": 100, "context_length": 1000},
    )
    out = json.loads(ops.mimir_ops("context_usage"))
    assert out["ok"] is True
    assert "context_usage" in out
    assert out.get("remaining_tokens_estimate") == 900
