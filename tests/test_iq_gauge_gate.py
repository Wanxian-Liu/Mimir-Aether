"""闸 B（量具健康前置门）回归用例 —— 台账 T-A1。

判据语义：量具不健康 ⇒ 必须输出 NO-SCORE（不出分），不得给一个不可信的分。
本文件只测纯函数 evaluate_gauges()，不碰机器态（swap/load 随环境变，不可作断言）。
"""
import json
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import iq_reeval_ready_probe as probe  # noqa: E402


def _seed(d: Path, now: float, ages=(0.5, 0.5, 0.5)):
    (d / "feedback_events.jsonl").write_text(
        json.dumps({"ts": now - ages[0] * 3600, "event_type": "pipeline_close"}) + "\n",
        encoding="utf-8")
    (d / "verification_results.jsonl").write_text(
        json.dumps({"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S",
                                              time.localtime(now - ages[1] * 3600)),
                    "passed": True}) + "\n", encoding="utf-8")
    (d / "compression_quality.jsonl").write_text(
        json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S",
                                       time.localtime(now - ages[2] * 3600)),
                    "entity_retention_rate": 1.0}) + "\n", encoding="utf-8")


@pytest.fixture()
def now():
    return time.time()


def test_positive_all_healthy_passes(tmp_path, now):
    """正控：三量具齐全新鲜 ⇒ 放行（ok=True，无理由）。"""
    _seed(tmp_path, now)
    ok, details, reasons = probe.evaluate_gauges(str(tmp_path), now=now)
    assert ok is True
    assert reasons == []
    assert len(details) == 3
    assert all(d["status"] == "ok" for d in details)


def test_negative_missing_file_blocks(tmp_path, now):
    """负控 1：缺一份 ⇒ 拦住，且理由指向缺失的那份。"""
    _seed(tmp_path, now)
    (tmp_path / "verification_results.jsonl").unlink()
    ok, _, reasons = probe.evaluate_gauges(str(tmp_path), now=now)
    assert ok is False
    assert any("verification_results.jsonl" in r and "不存在" in r for r in reasons)


def test_negative_stale_blocks(tmp_path, now):
    """负控 2：停更超阈值 ⇒ 拦住（分不可信的前提条件）。"""
    _seed(tmp_path, now, ages=(0.5, 0.5, 500.0))
    ok, details, reasons = probe.evaluate_gauges(str(tmp_path), now=now)
    assert ok is False
    assert any("停更" in r for r in reasons)
    stale = [d for d in details if d["gauge"] == "compression_quality.jsonl"][0]
    assert stale["status"] == "stale"


def test_negative_corrupt_blocks(tmp_path, now):
    """负控 3：尾段坏行率超 1% ⇒ 拦住。"""
    _seed(tmp_path, now)
    with open(tmp_path / "feedback_events.jsonl", "a", encoding="utf-8") as f:
        for _ in range(10):
            f.write("{not json\n")
    ok, _, reasons = probe.evaluate_gauges(str(tmp_path), now=now)
    assert ok is False
    assert any("坏行" in r for r in reasons)


def test_negative_schema_blocks(tmp_path, now):
    """负控 4：缺关键字段 ⇒ 拦住（字段没了 = schema 漂移，读数不可信）。"""
    _seed(tmp_path, now)
    (tmp_path / "compression_quality.jsonl").write_text(
        json.dumps({"ts": now}) + "\n", encoding="utf-8")
    ok, _, reasons = probe.evaluate_gauges(str(tmp_path), now=now)
    assert ok is False
    assert any("entity_retention_rate" in r for r in reasons)


def test_negative_empty_blocks(tmp_path, now):
    """负控 5：空文件 ⇒ 拦住。"""
    _seed(tmp_path, now)
    (tmp_path / "feedback_events.jsonl").write_text("", encoding="utf-8")
    ok, _, reasons = probe.evaluate_gauges(str(tmp_path), now=now)
    assert ok is False
    assert any("为空" in r for r in reasons)


def test_thresholds_are_bounded():
    """阈值不得被写成「无限大」（否则新鲜度判据恒过 = 假绿口）。"""
    for name, _ts_key, _required, max_age_h in probe.GAUGES:
        assert 0 < max_age_h <= 168, "%s 阈值异常: %r" % (name, max_age_h)


def test_cli_selftest_passes():
    """CLI 自检自身必须全绿（正控 + 5 个负控）。"""
    assert probe.main(["--selftest"]) == 0


def test_cli_no_score_when_gauge_broken(tmp_path):
    """端到端：量具坏 ⇒ CLI 输出 NO-SCORE 且 rc=1（不是 NOT-READY）。"""
    rc = probe.main(["--skip-machine", "--data-dir", str(tmp_path)])
    assert rc == 1
