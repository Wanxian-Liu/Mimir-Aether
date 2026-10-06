#!/usr/bin/env python3
"""Twin-arm tests for the chroma index health report (B2/P0-B, zero LLM).

Every arm here exists to answer one question the cron ledger cannot: when this
job says "ok", did anything actually get checked?

  * healthy fixture -> heartbeat, exit 0   (the instrument is alive)
  * drift / garbage / unfinished backfill -> exit 2 with the reading
  * a monitor that stopped writing -> exit 2, and it says so as "monitor stalled"
    rather than as an index fault -- conflating the two sends the reader to the
    wrong place
  * a missing health file -> exit 2 (absence is not health)
  * NEGATIVE CONTROL on the healthy fixture: the drift/garbage/backfill findings
    must NOT fire. Without it "exit 2 on the bad case" would be indistinguishable
    from "exit 2 on everything".
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "chroma_health_report.py"

_spec = importlib.util.spec_from_file_location("chroma_health_report", MODULE_PATH)
report = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(report)

NOW = dt.datetime(2026, 9, 26, 6, 0, tzinfo=dt.timezone.utc)


def _health(**overrides):
    checks = {
        "source_indexable": 20894,
        "source_garbage": 205,
        "chroma_docs": 20896,
        "backfill_phase": "done",
        "incremental_enabled": True,
        "garbage_in_index": 0,
        "garbage_scan_scanned": 5000,
    }
    checks.update(overrides.pop("checks", {}))
    payload = {"checked_at": "2026-09-26T05:58:00", "ok": overrides.pop("ok", True), "checks": checks}
    payload.update(overrides)
    return payload


def _evaluate(health, *, health_mtime=None, chroma_mtime=None, newest_source_ts=None, interval_hours=6):
    if health_mtime is None:
        health_mtime = NOW.timestamp() - 120  # 2 minutes fresh
    return report.evaluate(
        health,
        now=NOW,
        health_mtime=health_mtime,
        chroma_mtime=chroma_mtime,
        newest_source_ts=newest_source_ts,
        interval_hours=interval_hours,
    )


def test_healthy_index_reports_heartbeat_and_exits_zero():
    healthy, problems, heartbeat = _evaluate(_health())
    assert healthy, problems
    assert problems == []
    assert "docs=20896" in heartbeat
    assert "漂移=+2" in heartbeat
    assert "扫描覆盖=24%" in heartbeat, "the sample coverage must be stated, not implied"


def test_healthy_fixture_does_not_trip_the_finders():
    """Negative control: the bad-case detectors must stay quiet on a good case."""
    _, problems, _ = _evaluate(_health())
    joined = " ".join(problems)
    for word in ("漂移", "垃圾", "backfill", "停摆", "落后"):
        assert word not in joined, "the healthy fixture tripped: %s" % word


def test_drift_beyond_threshold_is_reported():
    healthy, problems, _ = _evaluate(_health(checks={"chroma_docs": 20896 + 500}))
    assert not healthy
    assert any("漂移" in p for p in problems), problems


def test_drift_within_threshold_is_tolerated():
    """The twin of the drift arm: +2 must not be reported as drift."""
    healthy, problems, _ = _evaluate(_health(checks={"chroma_docs": 20896}))
    assert healthy and problems == [], problems


def test_garbage_regression_is_reported():
    healthy, problems, _ = _evaluate(_health(checks={"garbage_in_index": 7}))
    assert not healthy
    assert any("垃圾" in p for p in problems), problems


def test_unfinished_backfill_is_reported():
    healthy, problems, _ = _evaluate(_health(checks={"backfill_phase": "running"}))
    assert not healthy
    assert any("backfill" in p for p in problems), problems


def test_stalled_monitor_is_reported_as_a_monitor_fault():
    """A quiet instrument is not a healthy subject. Owner: the monitor itself."""
    stale = NOW.timestamp() - 20 * 3600  # 20h on a 6h cadence
    healthy, problems, _ = _evaluate(_health(), health_mtime=stale)
    assert not healthy
    assert any("停摆" in p for p in problems), problems


def test_index_lagging_the_source_is_reported():
    newest = NOW.timestamp()
    healthy, problems, _ = _evaluate(_health(ok=True), chroma_mtime=newest - 7200, newest_source_ts=newest)
    assert not healthy
    assert any("落后" in p for p in problems), problems


def test_index_ahead_of_the_source_is_not_a_lag():
    """Twin of the lag arm: a chroma write after the newest message is normal."""
    newest = NOW.timestamp() - 30
    healthy, problems, _ = _evaluate(_health(), chroma_mtime=newest + 10, newest_source_ts=newest)
    assert healthy and problems == [], problems


def test_missing_health_file_is_not_health(tmp_path, capsys):
    missing = tmp_path / "nope.json"
    code = report.run(_args(health_file=missing))
    out = capsys.readouterr().out
    assert code == 2
    assert "未产出" in out, out


def test_corrupt_health_file_is_reported(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    code = report.run(_args(health_file=bad))
    out = capsys.readouterr().out
    assert code == 2
    assert "无法解析" in out, out


def test_end_to_end_healthy_file_exits_zero(tmp_path, capsys):
    hf = tmp_path / "p0_index_health.json"
    hf.write_text(json.dumps(_health(), ensure_ascii=False), encoding="utf-8")
    chroma = tmp_path / "chroma.sqlite3"
    chroma.write_bytes(b"x")
    code = report.run(
        _args(health_file=hf, now=NOW.isoformat(), chroma_file=chroma, source_db=tmp_path / "missing.db")
    )
    out = capsys.readouterr().out
    assert code == 0, out
    assert out.startswith("[索引健康] ✅"), out


def test_end_to_end_alarm_exits_two(tmp_path, capsys):
    hf = tmp_path / "p0_index_health.json"
    hf.write_text(json.dumps(_health(checks={"garbage_in_index": 3}), ensure_ascii=False), encoding="utf-8")
    code = report.run(_args(health_file=hf, now=NOW.isoformat(), source_db=tmp_path / "missing.db"))
    out = capsys.readouterr().out
    assert code == 2
    assert "🔴" in out, out


def _args(**overrides):
    base = {
        "health_file": None,
        "chroma_file": str(Path("/nonexistent-chroma")),
        "source_db": None,
        "now": None,
        "interval_hours": 6,
    }
    base.update(overrides)
    return type("A", (), base)()


def test_module_reads_no_model_client():
    """Zero LLM is the whole point of moving this job to script form."""
    source = MODULE_PATH.read_text(encoding="utf-8")
    for banned in ("openai", "anthropic", "deepseek", "openrouter", "litellm"):
        assert banned not in source.lower(), "the report layer must not talk to a model: %s" % banned

# --- #10 判据分型 (2026-10-07) -------------------------------------------------
# 旧判据 `abs(drift) > allowed` 把「多」与「缺」两种**方向相反**的故障合并成一个
# 告警，外部读不出方向。下面两臂是**正控/负控**：同一函数、同一阈值、只差方向，
# 必须判出**相反**结论。缺任一侧 ⇒ 合并判据会重新溜回来而无人发现。


def test_drift_over_threshold_is_reported_as_surplus():
    """正控：chroma 多于源（多索引），方向 over。"""
    health = _health(checks={"source_indexable": 20000, "chroma_docs": 20500})
    healthy, problems, _ = _evaluate(health)
    assert not healthy
    assert any("多索引" in p for p in problems), problems
    assert report.drift_direction_of(health) == "over"


def test_drift_under_threshold_is_reported_as_gap():
    """负控：chroma 少于源（漏索引），方向 under —— 与正控方向相反。"""
    health = _health(checks={"source_indexable": 20000, "chroma_docs": 19500})
    healthy, problems, _ = _evaluate(health)
    assert not healthy
    assert any("漏索引" in p for p in problems), problems
    assert report.drift_direction_of(health) == "under"


def test_drift_directions_are_opposite_not_merged():
    """两臂必须给出相反结论；若同向 ⇒ 判据又退回 abs() 合并。"""
    over = _health(checks={"source_indexable": 20000, "chroma_docs": 20500})
    under = _health(checks={"source_indexable": 20000, "chroma_docs": 19500})
    assert report.drift_direction_of(over) == "over"
    assert report.drift_direction_of(under) == "under"
    assert report.drift_direction_of(over) != report.drift_direction_of(under)


def test_drift_within_threshold_is_aligned():
    """阴性对照：阈值内不得贴方向标签（否则每轮都告警 = 告警失效）。"""
    health = _health(checks={"source_indexable": 20000, "chroma_docs": 20005})
    assert report.drift_direction_of(health) == "ok"
    assert report.classify_drift(0, 400) == "ok"
    assert report.classify_drift(401, 400) == "over"
    assert report.classify_drift(-401, 400) == "under"


def test_heartbeat_states_direction():
    """心跳也带方向：健康时外部同样要能读出「多还是缺」。"""
    _, _, heartbeat = _evaluate(_health())
    assert "漂移=+2(ok)" in heartbeat, heartbeat


def test_alert_exit_states_direction(tmp_path, capsys):
    """告警出口带机读方向行（外部不必解析中文文案）。"""
    hf = tmp_path / "p0_index_health.json"
    hf.write_text(
        json.dumps(_health(checks={"source_indexable": 20000, "chroma_docs": 19500}), ensure_ascii=False),
        encoding="utf-8",
    )
    code = report.run(_args(health_file=hf, now=NOW.isoformat(), source_db=tmp_path / "missing.db"))
    out = capsys.readouterr().out
    assert code == 2, out
    assert "漂移方向=under" in out, out
    assert "缺口为负(缺)=True" in out, out
