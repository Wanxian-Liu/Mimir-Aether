"""QC7 告警判据两个结构缺陷的工程化验证（2026-09-16 · 四方 C 组审计）。

覆盖：
  (1) 最小样本量 —— 小样本越阈**不再**判 degraded，而是显式 insufficient_samples，且不落告警；
  (2) 紧急底线 —— 绝对失败数达标时仍报警（小样本闸不得闷掉真事故）；
  (3) 口径分段 —— agent_bug 标签不进系统池（OpenClaw 指定用例 1）；
  (4) 口径分段 —— system_failure 标签越阈正常落告警（OpenClaw 指定用例 2）；
  (5) 口径可读 —— /health 快照暴露样本量 / 原因 / 来源分布 / 被排除计数，便于事后复算。
"""

from __future__ import annotations

import json

import pytest


def _load(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("MIMIR_MONITOR_ERROR_RATE_THRESHOLD", raising=False)
    monkeypatch.delenv("MIMIR_MONITOR_MIN_SAMPLES", raising=False)
    monkeypatch.delenv("MIMIR_MONITOR_MIN_ERRORS_EMERGENCY", raising=False)
    import importlib

    mon = importlib.import_module("agent.monitor")
    mon.reset_monitor_state()
    return mon


def test_qc7_1_small_sample_is_not_degraded(tmp_path, monkeypatch):
    """n=20 < N_min=30、3 次失败(15%>10%) ⇒ 显式样本不足，且不得落告警。"""
    mon = _load(tmp_path, monkeypatch)
    for _ in range(17):
        mon.record_tool_outcome("ok_tool", success=True)
    for _ in range(3):
        mon.record_tool_outcome("bad_tool", success=False, error_message="boom")

    d = mon.get_agent_error_rate_detail()
    assert d["calls"] == 20 and d["errors"] == 3
    assert d["rate"] > d["threshold"]
    assert d["alarm"] is False
    assert d["status"] == "insufficient_samples"
    assert mon.get_agent_health_status() == "insufficient_samples"
    assert not (tmp_path / "data" / "monitor_alerts.json").exists()


def test_qc7_1_emergency_floor_still_alerts(tmp_path, monkeypatch):
    """n=10 < N_min，但绝对失败数 = 5（达紧急底线）⇒ 仍报警判 degraded。"""
    mon = _load(tmp_path, monkeypatch)
    for _ in range(5):
        mon.record_tool_outcome("ok_tool", success=True)
    for _ in range(5):
        mon.record_tool_outcome("bad_tool", success=False, error_message="down")
    assert mon.get_agent_health_status() == "degraded"
    alerts = json.loads((tmp_path / "data" / "monitor_alerts.json").read_text("utf-8"))
    assert alerts[-1]["sample_size"] == 10
    assert alerts[-1]["min_samples"] == 30 and alerts[-1]["min_errors_emergency"] == 5


def test_qc7_2_agent_bug_tag_does_not_trigger_system_alert(tmp_path, monkeypatch):
    """OpenClaw 用例 1：agent_bug 标签 + 阈值超限 ⇒ 不进系统池 ⇒ 不告警。"""
    mon = _load(tmp_path, monkeypatch)
    for _ in range(20):
        mon.record_tool_outcome("ok_tool", success=True)
    for _ in range(10):
        mon.record_tool_outcome(
            "execute_code", success=False,
            error_message="KeyError: 'neg,pos'",
            source_tag=mon.SOURCE_AGENT_BUG,
        )
    d = mon.get_agent_error_rate_detail()
    assert d["calls"] == 20 and d["errors"] == 0
    assert d["rate"] == 0.0
    assert d["excluded_agent_bug"] == {"calls": 10, "errors": 10}
    assert mon.get_agent_health_status() == "ok"
    assert not (tmp_path / "data" / "monitor_alerts.json").exists()


def test_qc7_2_system_failure_tag_triggers_alert(tmp_path, monkeypatch):
    """OpenClaw 用例 2：system_failure 标签 + 阈值超限 ⇒ 落告警，且 payload 带来源分布。"""
    mon = _load(tmp_path, monkeypatch)
    for _ in range(20):
        mon.record_tool_outcome("ok_tool", success=True)
    for _ in range(10):
        mon.record_tool_outcome(
            "read_file", success=False,
            error_message="Connection refused",
            source_tag=mon.SOURCE_SYSTEM_FAILURE,
        )
    assert mon.get_agent_health_status() == "degraded"
    alerts = json.loads((tmp_path / "data" / "monitor_alerts.json").read_text("utf-8"))
    last = alerts[-1]
    assert last["by_source"][mon.SOURCE_SYSTEM_FAILURE] == {"calls": 10, "errors": 10}
    assert last["pool"] == "excludes source_tag=agent_bug"
    assert last["agent_error_rate"] > last["threshold"]


def test_qc7_classifier_and_snapshot_fields(tmp_path, monkeypatch):
    """分类器启发式 + /health 快照口径字段齐全（可复算，不用猜）。"""
    mon = _load(tmp_path, monkeypatch)
    assert mon.classify_error_source("execute_code", "KeyError: 'id'") == mon.SOURCE_AGENT_BUG
    assert mon.classify_error_source("read_file", "Connection refused") == mon.SOURCE_SYSTEM_FAILURE
    assert mon.classify_error_source("read_file", "") == mon.SOURCE_UNSPECIFIED

    for _ in range(10):
        mon.record_tool_outcome("ok_tool", success=True, duration_ms=5.0)
    snap = mon.snapshot_for_health()
    for key in ("agent_error_calls", "agent_error_reason", "agent_error_min_samples", "agent_error_by_source"):
        assert key in snap, key
    assert snap["agent_error_calls"] == 10
    assert snap["agent_error_reason"] == "ok"
