"""B1/B3 cron 记账卫生闸 —— 负控与孪生对照（2026-09-19 · 刘哥批）。

只证明「坏样本被拒」不算数，必须同时证明「好样本不被误拦」——本文件两侧都测。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_cron_hygiene as gate  # noqa: E402

FIXED_NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


def _job(jid: str, **over) -> dict:
    job = {
        "id": jid,
        "name": jid,
        "enabled": True,
        "deliver": "feishu:oc_x",
        "next_run_at": "2999-01-01T00:00:00+00:00",
    }
    job.update(over)
    return job


def _rules(jobs) -> list:
    return sorted({r for r, _lvl, _m in gate.evaluate(jobs, now=FIXED_NOW)})


# --- 负控（坏样本必须被拒）---------------------------------------------------


def test_disabled_without_reason_fails():
    assert _rules([_job("b1", enabled=False)]) == [gate.RULE_DISABLED_NO_REASON]


def test_enabled_with_local_deliver_fails():
    assert _rules([_job("b2", deliver="local")]) == [gate.RULE_ENABLED_LOCAL]


def test_enabled_with_frozen_next_run_warns():
    jobs = [_job("b3", next_run_at="2026-08-19T03:46:01+00:00")]
    assert _rules(jobs) == [gate.RULE_ENABLED_FROZEN]
    levels = {lvl for _r, lvl, _m in gate.evaluate(jobs, now=FIXED_NOW)}
    assert levels == {"WARN"}


# --- 孪生对照（好样本不得被误拦）---------------------------------------------


def test_twin_enabled_feishu_passes():
    assert _rules([_job("g1")]) == []


def test_twin_disabled_with_disable_reason_passes():
    assert _rules([_job("g2", enabled=False, disable_reason="一次性任务已完成")]) == []


def test_twin_disabled_with_paused_reason_passes():
    assert _rules([_job("g3", enabled=False, paused_reason="等外部依赖")]) == []


def test_twin_local_deliver_exempt_passes():
    assert _rules([_job("g4", deliver="local", local_deliver_reason="runner 只落台账")]) == []


# --- 退出码契约 ---------------------------------------------------------------


def test_run_returns_zero_when_jobs_file_missing(tmp_path):
    assert gate.run(tmp_path / "nope.json") == gate.EXIT_OK


def test_run_returns_one_on_any_fail(tmp_path):
    p = tmp_path / "jobs.json"
    p.write_text(json.dumps({"jobs": [_job("b1", enabled=False)]}), encoding="utf-8")
    assert gate.run(p) == gate.EXIT_FAIL


def test_run_returns_zero_on_warn_only(tmp_path):
    p = tmp_path / "jobs.json"
    p.write_text(
        json.dumps({"jobs": [_job("w1", next_run_at="2026-08-19T03:46:01+00:00")]}),
        encoding="utf-8",
    )
    assert gate.run(p) == gate.EXIT_OK


def test_selftest_all_pass():
    assert gate.selftest() == gate.EXIT_OK


# --- 口径回归：真实 jobs.json 必须干净（本机有该文件时）-----------------------


def test_live_jobs_file_is_clean_if_present():
    live = gate.default_jobs_file()
    if not live.exists():
        pytest.skip(f"no live jobs.json at {live} (CI)")
    assert gate.run(live) == gate.EXIT_OK
