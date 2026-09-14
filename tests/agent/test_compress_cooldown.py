"""T16 压缩冷却闸测试（2026-09-14）。

覆盖（D3：`agent/compress_cooldown.py` 289 行此前 tests/ 树零引用）：
  ① 退避序列  600 → 1200 → 2400 → 3600（封顶）
  ② attempt_id 去重：同一次 compress() 内多条失败只计 1
  ③ 成功应用清零
  ④ 状态损坏 fail-open（不得把压缩长期停摆）
  ⑤ ALERT 每档只打一次
  ⑥ env 开关 / env 覆盖 base·max
  ⑦ **与 needs_compression() 的接线**——证明热环真的被挡住（T16 的核心 DoD）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import compress_cooldown as cc  # noqa: E402
from agent.context_compressor import ContextCompressorV2  # noqa: E402

_ENV_KEYS = (
    "MIMIR_COMPRESS_COOLDOWN",
    "MIMIR_COMPRESS_COOLDOWN_BASE",
    "MIMIR_COMPRESS_COOLDOWN_MAX",
)


@pytest.fixture()
def cooldown(tmp_path, monkeypatch):
    """隔离状态文件 + 清空相关 env。"""
    monkeypatch.setattr(cc, "state_path", lambda: tmp_path / "ops" / "compress_cooldown.json")
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    return cc


class _FakeCompressor:
    """只带 needs_compression() 需要的三个属性（其余不重要）。"""

    def __init__(self, tokens=200_000, threshold=120_000):
        self.last_prompt_tokens = tokens
        self.threshold_tokens = threshold
        self._cooldown_logged_until = None


# ── ① 退避序列 ───────────────────────────────────────────────────────────
def test_backoff_sequence_exponential_and_capped(cooldown):
    assert [cooldown.delay_for(n) for n in (1, 2, 3, 4, 5)] == [600.0, 1200.0, 2400.0, 3600.0, 3600.0]


def test_env_overrides_base_and_max(cooldown, monkeypatch):
    monkeypatch.setenv("MIMIR_COMPRESS_COOLDOWN_BASE", "30")
    assert cooldown.delay_for(1) == 30.0
    assert cooldown.delay_for(3) == 120.0
    monkeypatch.setenv("MIMIR_COMPRESS_COOLDOWN_MAX", "60")
    assert cooldown.delay_for(3) == 60.0


def test_max_never_below_base(cooldown, monkeypatch):
    """max < base 是误配 ⇒ 必须夹到 >= base，否则退避会倒挂。"""
    monkeypatch.setenv("MIMIR_COMPRESS_COOLDOWN_BASE", "900")
    monkeypatch.setenv("MIMIR_COMPRESS_COOLDOWN_MAX", "10")
    assert cooldown.max_delay_s() >= cooldown.base_delay_s() == 900.0


def test_bad_env_values_fall_back_to_defaults(cooldown, monkeypatch):
    monkeypatch.setenv("MIMIR_COMPRESS_COOLDOWN_BASE", "abc")
    assert cooldown.base_delay_s() == cc.BASE_DELAY_S_DEFAULT


# ── ② 冷却是「未应用」的产物 ─────────────────────────────────────────────
def test_missing_state_is_not_cooling(cooldown):
    cooling, st = cooldown.is_cooling()
    assert cooling is False
    assert st["consecutive_failures"] == 0


def test_record_failure_arms_cooldown(cooldown):
    st = cooldown.record_failure("entity_retention_low(rate=0.45)")
    assert st["consecutive_failures"] == 1
    assert st["last_reason"] == "entity_retention_low(rate=0.45)"
    cooling, cur = cooldown.is_cooling()
    assert cooling is True
    assert cur["remaining_s"] > 0


def test_cooldown_expires_by_clock(cooldown):
    cooldown.record_failure("x")
    cooling, _ = cooldown.is_cooling(now=cooldown.state()["cooldown_until_epoch"] + 1.0)
    assert cooling is False


# ── ③ attempt_id 去重 ───────────────────────────────────────────────────
def test_same_attempt_id_counts_once(cooldown):
    """同一次 compress() 内「摘要降级 + 闸门回滚」会报两次 ⇒ 只能计 1，否则退避跳级。"""
    cooldown.record_failure("summary_degraded", attempt_id="pid-1-aaa")
    cooldown.record_failure("entity_retention_low", attempt_id="pid-1-aaa")
    assert cooldown.state()["consecutive_failures"] == 1
    assert cooldown.state()["total_failures"] == 1


def test_different_attempt_ids_advance(cooldown):
    cooldown.record_failure("a", attempt_id="pid-1-aaa")
    cooldown.record_failure("b", attempt_id="pid-1-bbb")
    st = cooldown.state()
    assert st["consecutive_failures"] == 2
    assert st["total_failures"] == 2
    assert st["cooldown_delay_s"] == 1200.0


# ── ④ 成功清零 ──────────────────────────────────────────────────────────
def test_success_clears_cooldown(cooldown):
    cooldown.record_failure("a")
    cooldown.record_failure("b")
    st = cooldown.record_success(attempt_id="pid-9-zzz")
    assert st["consecutive_failures"] == 0
    assert st["cooldown_until_epoch"] == 0.0
    cooling, cur = cooldown.is_cooling()
    assert cooling is False
    assert cur["total_successes"] == 1
    assert cur["last_applied_epoch"] is not None


def test_reset_clears_everything(cooldown):
    cooldown.record_failure("a")
    cooldown.reset()
    st = cooldown.state()
    assert st["consecutive_failures"] == 0 and st["total_failures"] == 0


# ── ⑤ 损坏状态 fail-open（显式设计选择）──────────────────────────────────
def test_corrupt_state_fails_open(cooldown):
    """冷却是省 token 的优化，不是安全闸：读不出 ⇒ 退回「无冷却」，绝不阻断压缩。"""
    p = cooldown.state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ this is not json", encoding="utf-8")
    cooling, st = cooldown.is_cooling()
    assert cooling is False
    assert st["read_error"]


def test_non_object_state_fails_open(cooldown):
    p = cooldown.state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("[1, 2, 3]", encoding="utf-8")
    cooling, st = cooldown.is_cooling()
    assert cooling is False
    assert st["read_error"] == "state_not_object"


def test_unknown_fields_are_tolerated(cooldown):
    p = cooldown.state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"consecutive_failures": 2, "future_field": 1}), encoding="utf-8")
    st = cooldown.state()
    assert st["consecutive_failures"] == 2 and "future_field" in st


# ── ⑥ env 关闸（回滚通路）──────────────────────────────────────────────
def test_env_killswitch_disables_cooldown(cooldown, monkeypatch):
    cooldown.record_failure("a")
    monkeypatch.setenv("MIMIR_COMPRESS_COOLDOWN", "0")
    cooling, st = cooldown.is_cooling()
    assert cooling is False
    assert st["enabled"] is False
    assert st["consecutive_failures"] == 1  # 状态保留，只是不生效


# ── ⑦ ALERT 每档只打一次 ────────────────────────────────────────────────
def test_alert_emitted_once_per_threshold(cooldown, caplog):
    with caplog.at_level("WARNING", logger="agent.compress_cooldown"):
        for i in range(cc.ALERT_AFTER_FAILURES):
            cooldown.record_failure("r%d" % i)
        _first = sum(1 for r in caplog.records if "COOLDOWN-ALERT" in r.getMessage())
        cooldown.record_failure("again")   # n=6 != alert_emitted_for(5) ⇒ 会再打一次
        _second = sum(1 for r in caplog.records if "COOLDOWN-ALERT" in r.getMessage())
    assert _first == 1
    assert _second == 2
    assert cooldown.state()["alert_emitted_for"] == cc.ALERT_AFTER_FAILURES + 1


# ── ⑧ 接线：热环真的被挡住（T16 的核心 DoD）────────────────────────────
def test_needs_compression_blocks_during_cooldown(cooldown):
    """T18 根因：回滚 ⇒ tokens 不变 ⇒ 下一 turn 必然重触发。冷却必须挡住它。"""
    fake = _FakeCompressor()
    assert ContextCompressorV2.needs_compression(fake) is True    # 未冷却是正常触发
    cooldown.record_failure("entity_retention_low(rate=0.45)", attempt_id="pid-1-a")
    assert ContextCompressorV2.needs_compression(fake) is False   # 冷却窗口内不再触发


def test_needs_compression_below_threshold_unaffected(cooldown):
    """未越线时冷却无关——方向也要验，不得因冷却状态存在就把 False 变 True。"""
    cooldown.record_failure("a")
    assert ContextCompressorV2.needs_compression(_FakeCompressor(tokens=10_000)) is False


def test_needs_compression_recovers_after_success(cooldown):
    """冷却可恢复：成功应用后热环闸解除，否则压缩会被永久停摆。"""
    fake = _FakeCompressor()
    cooldown.record_failure("a")
    assert ContextCompressorV2.needs_compression(fake) is False
    cooldown.record_success()
    assert ContextCompressorV2.needs_compression(fake) is True


def test_needs_compression_fail_open_on_broken_state(cooldown):
    """状态文件损坏时 needs_compression 必须仍能正常判断（不得抛异常）。"""
    p = cooldown.state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("<<<garbage>>>", encoding="utf-8")
    assert ContextCompressorV2.needs_compression(_FakeCompressor()) is True
