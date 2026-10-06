"""B4 · run 级健康出声 · 回归用例（2026-10-06 · 任务书 行218「B4 观测」）。

受控差分：同一函数只换**自变量**（日期 / 阈值 / 阈值 env / 连续 run 次数），
判据全部为数字（计数、告警条数、fired 列表），**不用形容词**。

覆盖：
  ① daily_counts：按日过滤 + 静默死族聚合 + 坏行跳过（pure，无 IO）
  ② evaluate：阈值边界（差一个不触 / 到阈值触 / 0 = 关闭）（pure）
  ③ record_run_exit：落 ledger + 当日计数 + 越线出声 + **每类每日只出声一次**
  ④ 回滚 env：MIMIR_RUN_HEALTH=0 ⇒ 不落盘不出声
  ⑤ 阈值 env 覆盖：调高阈值 ⇒ 同样的计数不触
  ⑥ fail-open：目标路径不可写 ⇒ 返回 error，不抛（观测设施不得拖垮 run）
"""
from __future__ import annotations

import json

import pytest

from agent import run_health as rh


def _line(day, reason, **kw):
    rec = {"date": day, "exit_reason": reason, "ts": day + "T00:00:00"}
    rec.update(kw)
    return json.dumps(rec, ensure_ascii=False)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """把 run_health 的家目录钉到 tmp_path（不碰 ~/.mimiraether）。"""
    monkeypatch.setattr(rh, "_home", lambda: tmp_path)
    for name in ("MIMIR_RUN_HEALTH", "MIMIR_RUN_HEALTH_EMPTY_THRESHOLD",
                 "MIMIR_RUN_HEALTH_MAXTURNS_THRESHOLD", "MIMIR_RUN_HEALTH_TOTAL_THRESHOLD"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


# ───────────────────────── ① daily_counts（pure） ─────────────────────────

def test_daily_counts_filters_by_day_and_aggregates_silent_death():
    lines = [
        _line("2026-10-06", "empty_content"),
        _line("2026-10-06", "max_turns"),
        _line("2026-10-06", "natural"),
        _line("2026-10-06", "verify_exhausted"),
        _line("2026-10-05", "empty_content"),   # 另一天 ⇒ 不计
    ]
    c = rh.daily_counts(lines, "2026-10-06")
    assert c["runs"] == 4
    assert c["empty_content"] == 1
    assert c["max_turns"] == 1
    assert c["silent_death"] == 3          # empty_content + max_turns + verify_exhausted
    assert "natural" not in c or c["natural"] == 1


def test_daily_counts_skips_bad_lines_without_raising():
    lines = ["not json", "{bad", _line("2026-10-06", "max_turns")]
    c = rh.daily_counts(lines, "2026-10-06")
    assert c["runs"] == 1 and c["max_turns"] == 1


# ───────────────────────── ② evaluate（pure） ─────────────────────────

def test_evaluate_threshold_boundary():
    thr = {"empty_content": 2, "max_turns": 1, "silent_death": 3}
    assert rh.evaluate({"empty_content": 1}, thr) == []                    # 差一个 ⇒ 不触
    assert rh.evaluate({"empty_content": 2}, thr) == ["empty_content=2>=2"]  # 到阈值 ⇒ 触
    assert rh.evaluate({"max_turns": 1}, thr) == ["max_turns=1>=1"]
    assert rh.evaluate({"empty_content": 1, "max_turns": 1}, thr) == ["max_turns=1>=1"]  # 总数 2 < 3


def test_evaluate_zero_limit_disables_that_kind():
    assert rh.evaluate({"empty_content": 99}, {"empty_content": 0, "max_turns": 0, "silent_death": 0}) == []


# ───────────────────────── ③ 端到端：出声 + 幂等 ─────────────────────────

def test_record_run_exit_fires_once_per_day_and_keeps_counting(home):
    r1 = rh.record_run_exit("empty_content", turns_used=3)
    assert r1["enabled"] is True and r1["counts"]["empty_content"] == 1 and r1["fired"] == []

    r2 = rh.record_run_exit("empty_content", turns_used=4)
    assert r2["counts"]["empty_content"] == 2
    assert r2["fired"] == ["empty_content=2>=2"]          # 越线 ⇒ 出声

    r3 = rh.record_run_exit("empty_content", turns_used=5)
    assert r3["counts"]["empty_content"] == 3 and r3["fired"] == []   # 同类当日不重复出声

    ledger = [json.loads(l) for l in open(home / "logs" / "run_health.jsonl", encoding="utf-8")]
    alerts = [json.loads(l) for l in open(home / "data" / "ops" / "run_health_alerts.jsonl", encoding="utf-8")]
    assert len(ledger) == 3
    assert len(alerts) == 1 and alerts[0]["kind"] == "empty_content"


def test_record_run_exit_max_turns_default_threshold_fires_on_first(home):
    r = rh.record_run_exit("max_turns", turns_used=120, max_turns=120)
    assert r["fired"] == ["max_turns=1>=1"] and r["counts"]["silent_death"] == 1


def test_state_file_snapshot_carries_counts_and_alerted_flags(home):
    rh.record_run_exit("empty_content")
    rh.record_run_exit("empty_content")
    st = json.loads(open(home / "data" / "ops" / "run_health_state.json", encoding="utf-8").read())
    assert st["counts"]["empty_content"] == 2
    assert st["alerted"][st["date"]]["empty_content"] is True


# ───────────────────────── ④⑤ env ─────────────────────────

def test_env_rollback_writes_nothing(home, monkeypatch):
    monkeypatch.setenv("MIMIR_RUN_HEALTH", "0")
    r = rh.record_run_exit("empty_content")
    assert r == {"enabled": False}
    assert not (home / "logs" / "run_health.jsonl").exists()


def test_threshold_env_override_suppresses_alert(home, monkeypatch):
    monkeypatch.setenv("MIMIR_RUN_HEALTH_EMPTY_THRESHOLD", "5")
    fired = []
    for _ in range(3):
        fired += rh.record_run_exit("empty_content")["fired"]
    assert fired == []
    assert rh.record_run_exit("empty_content")["counts"]["empty_content"] == 4


# ───────────────────────── ⑥ fail-open ─────────────────────────

def test_fail_open_when_path_unwritable(tmp_path, monkeypatch):
    (tmp_path / "logs").write_text("not a dir", encoding="utf-8")   # 让 mkdir 失败
    monkeypatch.setattr(rh, "_home", lambda: tmp_path)
    monkeypatch.delenv("MIMIR_RUN_HEALTH", raising=False)
    r = rh.record_run_exit("empty_content")
    assert r["enabled"] is True and "error" in r          # 降级上报，不抛


# ───────────────────────── ⑦ 接线守卫（防「恒假标签」族：闸门在、调用点被摘） ─────────────────────────

def test_core_loop_wires_record_run_exit_at_exit_reason():
    """接线守卫：core_loop 收尾路径必须真的调 `record_run_exit(_exit_reason, ...)`。

    这是**接线断言**（非行为证明）——防未来重构把调用点静默摘掉而单测仍全绿
    （= 闸门在、无人调 = 恒假，2026-09-26/27 两犯同族）。行为由 ①–⑥ 覆盖。
    """
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "agent" / "core_loop.py"
    text = src.read_text(encoding="utf-8")
    assert "from agent.run_health import record_run_exit" in text
    assert "_record_run_exit(\n                    _exit_reason," in text
