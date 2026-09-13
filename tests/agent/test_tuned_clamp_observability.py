"""RS12 观测性：tuned 夹紧必须留痕（2026-09-13 · 刘哥批准的 RS12 方案 ②）

回归背景（实测，非推测）：
  `~/.mimiraether/data/tuned_thresholds.json` 写 `"compressor.threshold_percent": 0.12`，
  而 `_REGISTRY` 该键 spec 为 `min=0.35` ⇒ `_clamp` **静默**夹到 0.35（无 WARNING、无日志）。
  文件里写 0.12、运行时拿 0.35 —— 属「声明 ≠ 生效」第 3 例
  （前两例：窗口 50/200 双值、B9 env 架空 tuned）。

本测试锁定：
  1. 越界夹紧 → 记一条 INFO，含 requested / clamped / bounds
  2. 同一 (key, value) 只记一次（load_overrides 每次读盘都会进来，不能刷屏）
  3. 界内值 → 完全静默
  4. 通过 override 文件走真实读盘路径时同样可见
  5. 记忆集有界（不随可疑值数量无限增长）
"""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

import agent.tuned_thresholds as tt

_KEY = "compressor.threshold_percent"          # min 0.35 / max 0.70
_INT_KEY = "degeneration.loop_detection.threshold"  # min 2 / max 5 / int


@pytest.fixture(autouse=True)
def _reset_clamp_memo(monkeypatch):
    """模块级去重集跨用例共享 —— 每个用例从空集开始。"""
    monkeypatch.setattr(tt, "_CLAMP_LOGGED", set(), raising=False)


def _write_override(key, value):
    path = tt._overrides_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"overrides": {key: value}}), encoding="utf-8")
    return path


def _clamp_logs(caplog):
    return [r for r in caplog.records if "[TUNED-CLAMP]" in r.getMessage()]


# ── 1. 越界夹紧留痕 ──────────────────────────────────────────────────────
def test_out_of_bounds_clamp_is_logged(caplog):
    with caplog.at_level(logging.INFO, logger=tt.logger.name):
        got = tt._clamp(_KEY, 0.12)
    assert got == pytest.approx(0.35), "越界值应被夹到 min"
    hits = _clamp_logs(caplog)
    assert len(hits) == 1
    msg = hits[0].getMessage()
    assert "requested=0.12" in msg and "clamped=0.35" in msg
    assert "bounds=[0.35, 0.7]" in msg


def test_int_key_clamp_is_logged(caplog):
    with caplog.at_level(logging.INFO, logger=tt.logger.name):
        got = tt._clamp(_INT_KEY, 9)
    assert got == 5
    assert len(_clamp_logs(caplog)) == 1


# ── 2. 同一签名只记一次 ──────────────────────────────────────────────────
def test_same_signature_logged_once(caplog):
    with caplog.at_level(logging.INFO, logger=tt.logger.name):
        for _ in range(5):
            assert tt._clamp(_KEY, 0.12) == pytest.approx(0.35)
    assert len(_clamp_logs(caplog)) == 1, "重复读盘不得重复刷日志"


def test_distinct_signatures_logged_separately(caplog):
    with caplog.at_level(logging.INFO, logger=tt.logger.name):
        tt._clamp(_KEY, 0.12)
        tt._clamp(_KEY, 0.99)
    assert len(_clamp_logs(caplog)) == 2


# ── 3. 界内静默 ─────────────────────────────────────────────────────────
def test_in_bounds_is_silent(caplog):
    with caplog.at_level(logging.INFO, logger=tt.logger.name):
        assert tt._clamp(_KEY, 0.50) == pytest.approx(0.50)
        assert tt._clamp(_INT_KEY, 3) == 3
    assert _clamp_logs(caplog) == [], "界内值不应产生任何日志"


def test_boundary_values_are_silent(caplog):
    with caplog.at_level(logging.INFO, logger=tt.logger.name):
        assert tt._clamp(_KEY, 0.35) == pytest.approx(0.35)
        assert tt._clamp(_KEY, 0.70) == pytest.approx(0.70)
    assert _clamp_logs(caplog) == []


# ── 4. 真实读盘路径可见（RS12 的生产场景）────────────────────────────────
def test_override_file_out_of_bounds_visible_via_get_tuned_float(caplog):
    _write_override(_KEY, 0.12)
    with caplog.at_level(logging.INFO, logger=tt.logger.name):
        value = tt.get_tuned_float(_KEY)
    assert value == pytest.approx(0.35), "运行时取到的是夹紧后的值，不是文件里的 0.12"
    hits = _clamp_logs(caplog)
    assert len(hits) == 1
    assert "requested=0.12" in hits[0].getMessage()


def test_override_file_in_bounds_no_log(caplog):
    _write_override(_KEY, 0.45)
    with caplog.at_level(logging.INFO, logger=tt.logger.name):
        value = tt.get_tuned_float(_KEY)
    assert value == pytest.approx(0.45)
    assert _clamp_logs(caplog) == []


def test_set_override_returns_clamped_and_logs(caplog):
    with caplog.at_level(logging.INFO, logger=tt.logger.name):
        entry = tt.set_override(_KEY, 0.05, reason="rs12-test")
    assert entry["value"] == pytest.approx(0.35)
    assert len(_clamp_logs(caplog)) == 1


# ── 5. 去重集有界 ───────────────────────────────────────────────────────
def test_memo_is_bounded(monkeypatch, caplog):
    monkeypatch.setattr(tt, "_CLAMP_LOGGED", set(), raising=False)
    monkeypatch.setattr(tt, "_CLAMP_LOGGED_MAX", 2, raising=False)
    with caplog.at_level(logging.INFO, logger=tt.logger.name):
        tt._clamp(_KEY, 0.11)
        tt._clamp(_KEY, 0.12)
        tt._clamp(_KEY, 0.13)   # 超出上限：不再新增签名
    assert len(tt._CLAMP_LOGGED) <= 2
    assert tt._clamp(_KEY, 0.13) == pytest.approx(0.35), "夹紧行为不受记忆集影响"
