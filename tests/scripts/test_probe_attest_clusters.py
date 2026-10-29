"""probe_attest_clusters 契约测试（2026-10-29 · 自证账本「聚类→改进清单」）。

关键契约（都来自盘上真实账本 schema，非臆造）：
  * 只聚 `verdict == UNVERIFIED` 的记录；混入的 VERIFIED 不得计入目标数
  * `no_data != no_failure`：空账本 ⇒ status="no_data" / total=None，**不得用 0 充数**
  * 坏行必须显式计入 health.skipped，不得静默吞掉
  * 阈值必须真的生效（抬阈 ⇒ 超阈类减少），不是恒定全报
  * 未归因的新 reason 必须标 "未归因"，不许静默给动作
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "probe_attest_clusters", REPO / "scripts" / "probe_attest_clusters.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _mk(ts, reason, verdict="UNVERIFIED"):
    return {"ts": ts, "reason": reason, "verdict": verdict, "source": "probe_attest"}


SAMPLE = (
    [_mk("2026-10-27T00:00:00", "no_attestation")] * 12
    + [_mk("2026-10-28T00:00:00", "claim_in_code_block")] * 10
    + [_mk("2026-10-27T00:00:00", "positive_control_failed")] * 5
    + [_mk("2026-10-28T00:00:00", "irrelevant", verdict="VERIFIED")] * 3
)


def test_selftest_passes():
    """自带两向自检必须全绿（正控 + 负控）。"""
    assert _mod()._selftest() == 0


def test_only_unverified_counted():
    m = _mod()
    res = m.cluster(SAMPLE, weeks=400, threshold=10)
    assert res["total_target"] == 27  # 12+10+5，VERIFIED 3 条不计
    assert "irrelevant" not in res["by_reason"]


def test_threshold_actually_applies():
    m = _mod()
    low = m.cluster(SAMPLE, weeks=400, threshold=10)
    high = m.cluster(SAMPLE, weeks=400, threshold=11)
    assert len(low["actionable"]) == 2
    assert len(high["actionable"]) == 1
    assert high["actionable"][0]["reason"] == "no_attestation"


def test_empty_ledger_is_no_data_not_zero(tmp_path):
    m = _mod()
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    res = m.analyze(p)
    assert res["status"] == "no_data"
    assert res["n_a"] is True
    assert res["total_target"] is None       # 关键：不用 0 充数
    assert res["semantics"] == "no_data != no_failure"


def test_missing_ledger_is_no_data(tmp_path):
    m = _mod()
    res = m.analyze(tmp_path / "nope.jsonl")
    assert res["status"] == "no_data"
    assert res["total_target"] is None


def test_bad_lines_reported_not_swallowed(tmp_path):
    m = _mod()
    p = tmp_path / "bad.jsonl"
    p.write_text(
        '{"ts":"2026-10-28T00:00:00","verdict":"UNVERIFIED","reason":"no_attestation"}\n'
        'not json\n[1,2,3]\n', encoding="utf-8")
    res = m.analyze(p)
    assert res["health"] == {"lines": 3, "parsed": 1, "skipped": 2}
    assert res["total_target"] == 1


def test_unattributed_reason_flagged():
    m = _mod()
    res = m.cluster([_mk("2026-10-28T00:00:00", "brand_new_reason")], weeks=400, threshold=1)
    assert res["actionable"][0]["upstream"]["level"] == "未归因"


def test_weekly_bucketing():
    m = _mod()
    recs = [_mk("2026-10-27T00:00:00", "r"), _mk("2026-10-28T00:00:00", "r")]
    res = m.cluster(recs, weeks=400, threshold=1)
    # 2026-10-27 与 10-28 同属 ISO 周 44
    assert len(res["actionable"][0]["weekly"]) == 1


def test_main_rc_semantics(tmp_path):
    m = _mod()
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert m.main(["--ledger", str(empty)]) == 1          # no_data ⇒ rc 1
    good = tmp_path / "good.jsonl"
    good.write_text(
        '{"ts":"2026-10-28T00:00:00","verdict":"UNVERIFIED","reason":"x"}\n',
        encoding="utf-8")
    assert m.main(["--ledger", str(good)]) == 0           # ok ⇒ rc 0
    assert m.main(["--ledger", str(good), "--weeks", "-1"]) == 2
