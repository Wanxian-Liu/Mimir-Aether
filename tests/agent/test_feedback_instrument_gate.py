"""IQ 批1③ 量具存活闸：absent / stale 必须与 live 可区分（灭「静默 0 假绿」）。

背景：`data/feedback_events.jsonl` 自 2026-08-16 13:44 停摆 35 天，而读端
`summarize_recent_experience()` 对「文件缺失」与「有文件但零事件」都返回 event_count=0
⇒ 下游把「量具坏了」读成「没有失败」。

臂设计（自问：这条读数在两种世界里会不同吗？）：
* A1 缺件 ⇒ absent（不是 0 分，是 N/A）
* A2 有件但零行 ⇒ 仍非 live（**与 A1 同判 N/A、与 A3 不同判 live**）
* A3 末条 ts 新鲜 ⇒ live + 计数可入分
* A4 末条 ts 超阈值 ⇒ stale
* A5 env 覆盖阈值 ⇒ 判据随阈值移动（防「阈值写死」）
* A6 告警：非 live 必发 WARNING 且同状态去重
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import pytest

from agent import experience_buffer as eb


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("MIMIR_FEEDBACK_STALE_SECONDS", raising=False)
    eb.reset_instrument_warnings()
    return tmp_path


def _events(home: Path) -> Path:
    p = home / "data" / "feedback_events.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _row(ts: float, event_type: str = "tool_failure", tool: str = "read_file") -> str:
    return json.dumps(
        {"ts": ts, "event_type": event_type, "payload": {"tool_name": tool}},
        ensure_ascii=False,
    )


def test_a1_missing_file_is_absent_not_zero(home):
    summary = eb.summarize_recent_experience()
    assert summary["instrument_status"] == eb.INSTRUMENT_ABSENT
    assert summary["scorable"] is False
    assert summary["n_a_reason"].startswith("instrument_status=absent")
    assert summary["event_count"] == 0  # 数值仍在，但**不可入分**


def test_a2_empty_file_is_not_live(home):
    _events(home).write_text("", encoding="utf-8")
    summary = eb.summarize_recent_experience()
    assert summary["instrument_status"] != eb.INSTRUMENT_LIVE
    assert summary["scorable"] is False


def test_a3_fresh_row_is_live(home):
    _events(home).write_text(_row(time.time() - 30) + "\n", encoding="utf-8")
    summary = eb.summarize_recent_experience()
    assert summary["instrument_status"] == eb.INSTRUMENT_LIVE
    assert summary["scorable"] is True
    assert summary["tool_failure_count"] == 1
    assert summary["top_failed_tools"] == ["read_file"]
    assert "n_a_reason" not in summary


def test_a4_stale_row_is_stale(home):
    _events(home).write_text(_row(time.time() - 30 * 86400) + "\n", encoding="utf-8")
    summary = eb.summarize_recent_experience()
    assert summary["instrument_status"] == eb.INSTRUMENT_STALE
    assert summary["scorable"] is False
    assert summary["instrument"]["age_s"] > 29 * 86400


def test_a5_env_override_moves_threshold(home, monkeypatch):
    p = _events(home)
    p.write_text(_row(time.time() - 120) + "\n", encoding="utf-8")

    monkeypatch.setenv("MIMIR_FEEDBACK_STALE_SECONDS", "60")
    assert eb.summarize_recent_experience()["instrument_status"] == eb.INSTRUMENT_STALE

    monkeypatch.setenv("MIMIR_FEEDBACK_STALE_SECONDS", "3600")
    assert eb.summarize_recent_experience()["instrument_status"] == eb.INSTRUMENT_LIVE


def test_a6_non_live_warns_once_per_status(home, caplog):
    with caplog.at_level(logging.WARNING, logger="agent.experience_buffer"):
        eb.summarize_recent_experience()
        eb.summarize_recent_experience()
    hits = [r for r in caplog.records if "INSTRUMENT-DEBT" in r.getMessage()]
    assert len(hits) == 1, f"expected one deduped warning, got {len(hits)}"
