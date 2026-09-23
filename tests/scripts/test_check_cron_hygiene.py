"""B1/B3 cron 记账卫生闸 + 行175 三项补强（R4 理由实质化 / R5 通道可达性 / R3 WARN→FAIL）。

只证明「坏样本被拒」不算数，必须同时证明「好样本不被误拦」——本文件两侧都测。
R5 一律注入探针（不打网络）；真 ping 的可达性由 CLI 侧负控覆盖（见 commit message）。
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
CUTOFF = gate.REASON_STANDARD_CUTOFF
STAMPED = "谁=Mimir | 何时=2026-09-21 | 为何=任务已闭环 | 可逆转=enabled+deliver"


def _probe_ok() -> dict:
    return {"verdict": "AUTH_OK", "source": "test-stub"}


def _probe_never_called() -> dict:
    raise AssertionError("R5 探针不该被调用（本用例无 feishu 投递依赖）")


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


def _pairs(jobs, probe=None):
    return sorted(
        {(r, lvl) for r, lvl, _m in gate.evaluate(jobs, now=FIXED_NOW, feishu_probe_fn=probe or _probe_ok)}
    )


def _rules(jobs, probe=None) -> list:
    return sorted({r for r, _lvl, _m in gate.evaluate(jobs, now=FIXED_NOW, feishu_probe_fn=probe or _probe_ok)})


# --- 负控（坏样本必须被拒）---------------------------------------------------


def test_disabled_without_reason_fails():
    assert _pairs([_job("b1", enabled=False)]) == [(gate.RULE_DISABLED_NO_REASON, gate.LEVEL_FAIL)]


def test_enabled_with_local_deliver_fails():
    assert _pairs([_job("b2", deliver="local")]) == [(gate.RULE_ENABLED_LOCAL, gate.LEVEL_FAIL)]


def test_enabled_with_frozen_next_run_fails():
    """行175 补强③：僵尸时间从 WARN 升级为 FAIL。"""
    assert _pairs([_job("b3", next_run_at="2026-08-19T03:46:01+00:00")]) == [
        (gate.RULE_ENABLED_FROZEN, gate.LEVEL_FAIL)
    ]


def test_two_char_reason_rejected_when_newly_stopped():
    """行176 指定负控：只有「恢复」两字的假 reason 必须被闸拒。"""
    jobs = [_job("b4", enabled=False, disable_reason="恢复", paused_at="2026-09-21T02:00:00+00:00")]
    assert _pairs(jobs) == [(gate.RULE_DISABLED_REASON_THIN, gate.LEVEL_FAIL)]


def test_two_char_reason_rejected_without_provenance():
    """无 paused_at/last_run_at ⇒ 无法证明早于 cutoff ⇒ 不得豁免。"""
    assert _pairs([_job("b5", enabled=False, disable_reason="恢复")]) == [
        (gate.RULE_DISABLED_REASON_THIN, gate.LEVEL_FAIL)
    ]


def test_missing_four_fields_rejected_when_newly_stopped():
    jobs = [
        _job(
            "b6",
            enabled=False,
            disable_reason="一次性验收任务已完成（batch2 B4-b 窗口验收），保留为证据记录。",
            paused_at="2026-09-21T02:00:00+00:00",
        )
    ]
    assert _pairs(jobs) == [(gate.RULE_DISABLED_REASON_THIN, gate.LEVEL_FAIL)]


def test_feishu_auth_error_fails():
    assert _pairs(
        [_job("b7")], probe=lambda: {"verdict": "AUTH_ERR", "source": "injected", "code": 10003}
    ) == [(gate.RULE_FEISHU_UNREACHABLE, gate.LEVEL_FAIL)]


def test_feishu_no_credentials_fails():
    assert _pairs(
        [_job("b8")], probe=lambda: {"verdict": "NO_CREDENTIALS", "source": "injected"}
    ) == [(gate.RULE_FEISHU_UNREACHABLE, gate.LEVEL_FAIL)]


def test_feishu_transport_error_is_warn_only():
    assert _pairs(
        [_job("b9")], probe=lambda: {"verdict": "TRANSPORT_ERR", "source": "injected"}
    ) == [(gate.RULE_FEISHU_UNREACHABLE, gate.LEVEL_WARN)]


# --- 孪生对照（好样本不得被误拦）---------------------------------------------


def test_twin_enabled_feishu_passes():
    assert _pairs([_job("g1")]) == []


def test_twin_disabled_with_stamped_reason_passes():
    assert _pairs([_job("g2", enabled=False, disable_reason=STAMPED)]) == []


def test_twin_disabled_with_stamped_paused_reason_passes():
    assert _pairs([_job("g3", enabled=False, paused_reason=STAMPED)]) == []


def test_twin_legacy_thin_reason_is_legacy_not_red():
    """迁移窗口对照：历史停用（早于 cutoff）的薄理由记 LEGACY，不假红。"""
    jobs = [_job("g4", enabled=False, disable_reason="N13 正控完成", paused_at="2026-09-18T05:13:28+00:00")]
    assert _pairs(jobs) == [(gate.RULE_DISABLED_REASON_THIN, gate.LEVEL_LEGACY)]


def test_twin_local_deliver_exempt_passes():
    assert _pairs([_job("g5", deliver="local", local_deliver_reason="runner 只落台账")], probe=_probe_never_called) == []


def test_twin_probe_off_produces_no_finding():
    assert _pairs([_job("g6")], probe=lambda: {"verdict": "SKIPPED", "source": "env-off"}) == []


def test_twin_unknown_verdict_is_warn_not_fail():
    assert _pairs([_job("g7")], probe=lambda: {"verdict": "ZZQ_UNKNOWN_VERDICT"}) == [
        (gate.RULE_FEISHU_UNREACHABLE, gate.LEVEL_WARN)
    ]


def test_cutoff_boundary_splits_legacy_and_new():
    """同一理由文本，只改停用时刻 ⇒ 分级必须翻转（判别力对照）。"""
    before = gate.assess_reason(_job("c1", enabled=False, disable_reason="恢复", paused_at="2026-09-20T15:59:59+00:00"), CUTOFF)
    after = gate.assess_reason(_job("c2", enabled=False, disable_reason="恢复", paused_at="2026-09-20T16:00:01+00:00"), CUTOFF)
    assert before.legacy is True and after.legacy is False


# --- R5 缓存分桶（限流保护：不重复打 API，且异桶不命中）----------------------


def test_cache_hit_only_for_same_origin_and_credential(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"verdict": "AUTH_OK", "ts": 1e12 + 1, "origin": "https://o1", "id_fp": "aaaa"}), encoding="utf-8")
    import time as _t

    fresh = {"verdict": "AUTH_OK", "ts": _t.time(), "origin": "https://o1", "id_fp": "aaaa"}
    state.write_text(json.dumps(fresh), encoding="utf-8")
    assert gate._read_cache(state, "https://o1", "aaaa", 1800) is not None
    assert gate._read_cache(state, "https://o2", "aaaa", 1800) is None
    assert gate._read_cache(state, "https://o1", "bbbb", 1800) is None
    assert gate._read_cache(state, "https://o1", "aaaa", 0) is None


def test_corrupt_cache_does_not_raise(tmp_path):
    state = tmp_path / "broken.json"
    state.write_text("{not json", encoding="utf-8")
    assert gate._read_cache(state, "https://o1", "aaaa", 1800) is None


def test_default_probe_respects_net_off(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_CRON_HYGIENE_NET", "0")
    monkeypatch.setenv("MIMIR_CRON_HYGIENE_FEISHU_STATE", str(tmp_path / "s.json"))
    result = gate.feishu_probe()
    assert result["verdict"] == "SKIPPED"
    assert not (tmp_path / "s.json").exists()  # 关闭时不落缓存、不联网


# --- 退出码契约 ---------------------------------------------------------------


def test_run_returns_zero_when_jobs_file_missing(tmp_path):
    assert gate.run(tmp_path / "nope.json") == gate.EXIT_OK


def test_run_returns_one_on_any_fail(tmp_path):
    p = tmp_path / "jobs.json"
    p.write_text(json.dumps({"jobs": [_job("b1", enabled=False)]}), encoding="utf-8")
    assert gate.run(p, feishu_probe_fn=_probe_ok) == gate.EXIT_FAIL


def test_run_returns_one_on_fake_two_char_reason(tmp_path):
    """行176 指定负控的端到端形态：写盘 → 跑闸 → 退出码非 0。"""
    p = tmp_path / "jobs.json"
    p.write_text(
        json.dumps({"jobs": [_job("fake", name="假-两字理由", enabled=False, disable_reason="恢复")]}),
        encoding="utf-8",
    )
    assert gate.run(p, feishu_probe_fn=_probe_ok) == gate.EXIT_FAIL


def test_run_returns_zero_on_warn_only(tmp_path):
    p = tmp_path / "jobs.json"
    p.write_text(json.dumps({"jobs": [_job("w1")]}), encoding="utf-8")
    assert gate.run(p, feishu_probe_fn=lambda: {"verdict": "TRANSPORT_ERR"}) == gate.EXIT_OK


def test_run_returns_zero_on_legacy_only(tmp_path):
    p = tmp_path / "jobs.json"
    p.write_text(
        json.dumps({"jobs": [_job("l1", enabled=False, disable_reason="N13 正控完成", paused_at="2026-09-18T05:13:28+00:00")]}),
        encoding="utf-8",
    )
    assert gate.run(p, feishu_probe_fn=_probe_ok) == gate.EXIT_OK


def test_selftest_all_pass():
    assert gate.selftest() == gate.EXIT_OK


# --- 口径回归：真实 jobs.json 必须干净（本机有该文件时；注入探针保持无网）----


def test_live_jobs_file_is_clean_if_present():
    live = gate.default_jobs_file()
    if not live.exists():
        pytest.skip(f"no live jobs.json at {live} (CI)")
    assert gate.run(live, feishu_probe_fn=_probe_ok) == gate.EXIT_OK


# --- R3 宽限窗（2026-09-23）：修「到点 → 调度器执行」之间的竞态假阳性 ---------
# 生产事故：wiki-watcher（间隔 300s）实测 t0 时 next_run_at 落后 now 仅 12s
# 即被判 R3 FAIL；70s 后同一 job 的 next_run_at 已推进 ⇒ 同一 job 可红可绿。
# 判据由「是否逾期」改为「逾期是否超过宽限」（宽限 = max(120s, 2 倍本 job 间隔)）。
#
# 注：本组用例**同时**包含「旧判据必然假红」的对照臂 —— 只证明新形态绿不够，
# 还要证明旧形态在同一字节上会红（否则无法区分「修好」与「本来就绿」）。


def _legacy_frozen_pairs(jobs) -> list:
    """修复前的判据（逐字复刻）：``next_run_at < now`` 即 FAIL（无宽限窗）。"""
    now = FIXED_NOW
    out = []
    for j in jobs:
        nxt = gate._parse_ts(j.get("next_run_at"))
        if nxt is not None and nxt < now:
            out.append((gate.RULE_ENABLED_FROZEN, gate.LEVEL_FAIL))
    return sorted(set(out))


def _live_job(jid, overdue_s, interval_s=300):
    """造一个「调度器还活着」的 job：next_run_at 刚刚过去 overdue_s 秒。"""
    now = FIXED_NOW
    nxt = now - __import__("datetime").timedelta(seconds=overdue_s)
    return _job(
        jid,
        next_run_at=nxt.isoformat(),
        last_run_at=(nxt - __import__("datetime").timedelta(seconds=interval_s)).isoformat(),
    )


def test_production_flapping_case_does_not_fail():
    """生产原案（间隔 300s、逾期 12s）：闸必须放行。"""
    j = _live_job("w", overdue_s=12)
    assert _pairs([j]) == []
    # 对照臂：旧判据在同一字节上必然假红
    assert _legacy_frozen_pairs([j]) == [(gate.RULE_ENABLED_FROZEN, gate.LEVEL_FAIL)]


def test_overdue_just_inside_grace_does_not_fail():
    assert _pairs([_live_job("w", overdue_s=599)]) == []


def test_overdue_just_beyond_grace_fails():
    assert _pairs([_live_job("w", overdue_s=601)]) == [
        (gate.RULE_ENABLED_FROZEN, gate.LEVEL_FAIL)
    ]


def test_real_zombie_still_fails_hours_later():
    """真僵尸（数小时）不得因宽限窗被放过。"""
    assert _pairs([_live_job("w", overdue_s=25131)]) == [
        (gate.RULE_ENABLED_FROZEN, gate.LEVEL_FAIL)
    ]


def test_unknown_interval_uses_floor():
    """无 last_run_at ⇒ 无法推间隔 ⇒ 只用 120s 下限。"""
    now = FIXED_NOW
    inside = _job("w1", next_run_at=(now - __import__("datetime").timedelta(seconds=30)).isoformat())
    beyond = _job("w2", next_run_at=(now - __import__("datetime").timedelta(seconds=200)).isoformat())
    assert _pairs([inside]) == []
    assert _pairs([beyond]) == [(gate.RULE_ENABLED_FROZEN, gate.LEVEL_FAIL)]


def test_frozen_job_with_inverted_delta_uses_floor():
    """冻结 job 的 next_run_at 早于 last_run_at ⇒ 差为负 ⇒ 退下限（不失真为「间隔巨大」）。"""
    now = FIXED_NOW
    j = _job(
        "w3",
        next_run_at="2026-09-19T00:00:00+00:00",
        last_run_at=(now - __import__("datetime").timedelta(seconds=60)).isoformat(),
    )
    assert gate._schedule_interval_s(j) is None
    assert gate._frozen_grace_s(j) == gate._FROZEN_GRACE_MIN_S


def test_grace_formula_is_twice_the_interval():
    for interval, want in ((300, 600.0), (60, 120.0), (1800, 3600.0), (10, 120.0)):
        assert gate._frozen_grace_s(_live_job("w", overdue_s=0, interval_s=interval)) == want
