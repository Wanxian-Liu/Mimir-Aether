"""auto_tuner 量具存活闸测试（IQ 批1③ 消费端补口 · 2026-09-20）。

命题：**建了闸不等于拦住了** —— `auto_tuner` 会用量具计数写真实 threshold override，
所以它必须在量具非 live 时**不调参**（fail-closed + 发声）。

孪生臂：
  A  量具停摆（末条事件 ts 为 35 天前）→ 期望 **无任何 override** + WARNING
  A2 量具缺失                            → 期望 **无任何 override** + WARNING
  B  孪生对照（同一批计数但 ts=现在）    → 期望 **有 override**（证明闸不误拦）
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from agent import auto_tuner as at
from agent import tuned_thresholds as tt


def _write_events(tmp_path: Path, n: int, ts: float) -> None:
    p = tmp_path / "data" / "feedback_events.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"ts": ts, "event_type": "tool_failure", "payload": {"tool_name": "read_file"}}
        for _ in range(n)
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _arm(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_TUNER", "1")
    tt.reset_overrides_for_tests()


def test_arm_a_stale_instrument_blocks_tuning(monkeypatch, tmp_path, caplog):
    _arm(monkeypatch, tmp_path)
    _write_events(tmp_path, 5, time.time() - 35 * 86400)  # 停摆 35 天
    caplog.set_level(logging.WARNING)

    changes = at.run_tune_after_pipeline_close(
        {"degraded_tools": [("read_file", 0.2)] * 2, "errors": ["e1", "e2"]}
    )
    assert changes == [], "停摆量具的计数不得用于写 override"
    assert any("INSTRUMENT-GATE" in r.message for r in caplog.records)
    # 台账不得被写（闸必须在写之前）
    assert not (tmp_path / "data" / "tune_audit.jsonl").exists()


def test_arm_a2_absent_instrument_blocks_tuning(monkeypatch, tmp_path, caplog):
    _arm(monkeypatch, tmp_path)
    caplog.set_level(logging.WARNING)

    changes = at.run_tune_after_pipeline_close({"errors": ["e1", "e2"]})
    assert changes == []
    assert any("INSTRUMENT-GATE" in r.message for r in caplog.records)


def test_arm_b_twin_live_instrument_still_tunes(monkeypatch, tmp_path):
    """孪生对照：同计数 + 新鲜量具 ⇒ 闸不误拦。"""
    _arm(monkeypatch, tmp_path)
    _write_events(tmp_path, 5, time.time())

    changes = at.run_tune_after_pipeline_close(
        {"degraded_tools": [("read_file", 0.2)], "errors": ["e1", "e2"]}
    )
    assert changes, "新鲜量具下必须仍能调参"
    audit = (tmp_path / "data" / "tune_audit.jsonl").read_text(encoding="utf-8")
    assert "compressor.threshold_percent" in audit or "degeneration" in audit
