"""档2-② 压缩阈值单一真源测试（2026-09-11 上下文/Memory 体检修复）

回归背景：阈值解析此前散落三处且互相架空——
  · core_loop:    MIMIR_COMPRESS_THRESHOLD(percent) > tuned > 默认 0.50
  · __init__:     MIMIR_COMPRESS_THRESHOLD_TOKENS(absolute) 直接覆盖 threshold_tokens
  · update_model: 用 percent 重算 → **静默丢弃** absolute 覆盖（clobber）
症状与窗口问题同源："配置改了不生效 / 不知道谁赢"。

本测试锁定：
  1. resolve_threshold_percent 优先级 env > tuned > 默认，非法 env 降级不抛
  2. resolve_threshold_tokens 绝对 env 优先，非法/0 降级回百分比
  3. MimirContextCompressor 记录 threshold_source 并应用 env 覆盖
  4. update_model 不再 clobber env 绝对覆盖
  5. compress 输出 [COMPRESS] trigger/skip 与 no-op abort 行（可观测性）
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

import agent.context_compressor as cc
from agent.context_compressor import (
    MimirContextCompressor,
    resolve_threshold_percent,
    resolve_threshold_tokens,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """两个阈值 env 一律清空，保证用例确定性（生产 shell 可能导出它们）。"""
    monkeypatch.delenv("MIMIR_COMPRESS_THRESHOLD", raising=False)
    monkeypatch.delenv("MIMIR_COMPRESS_THRESHOLD_TOKENS", raising=False)
    monkeypatch.delenv("MIMIR_COMPRESS_VERIFY", raising=False)


# ── 1. resolve_threshold_percent ────────────────────────────────────────
def test_percent_env_wins_over_tuned(monkeypatch):
    monkeypatch.setenv("MIMIR_COMPRESS_THRESHOLD", "0.42")
    percent, source = resolve_threshold_percent()
    assert percent == pytest.approx(0.42)
    assert source == "env:MIMIR_COMPRESS_THRESHOLD"


def test_percent_uses_tuned_when_env_absent(monkeypatch):
    import agent.tuned_thresholds as tt

    monkeypatch.setattr(tt, "get_tuned_float", lambda key, default=None: 0.35)
    percent, source = resolve_threshold_percent()
    assert percent == pytest.approx(0.35)
    assert source == "tuned:compressor.threshold_percent"


def test_percent_default_when_tuned_unavailable(monkeypatch):
    import agent.tuned_thresholds as tt

    def _boom(*a, **kw):
        raise RuntimeError("no tuned file")

    monkeypatch.setattr(tt, "get_tuned_float", _boom)
    percent, source = resolve_threshold_percent()
    assert percent == pytest.approx(0.50)
    assert source == "default:0.50"


def test_percent_invalid_env_keeps_lower_layer():
    """非法 env 值 → 不抛异常，且结果与"没有该 env"完全一致（降级到下层）。"""
    baseline = resolve_threshold_percent(env={})
    percent, source = resolve_threshold_percent(env={"MIMIR_COMPRESS_THRESHOLD": "abc"})
    assert (percent, source) == baseline


# ── 2. resolve_threshold_tokens ─────────────────────────────────────────
def test_tokens_absolute_env_wins(monkeypatch):
    monkeypatch.setenv("MIMIR_COMPRESS_THRESHOLD_TOKENS", "12345")
    tokens, source = resolve_threshold_tokens(1_000_000, 0.35)
    assert tokens == 12345
    assert source == "env:MIMIR_COMPRESS_THRESHOLD_TOKENS"


def test_tokens_zero_env_falls_back_to_percent(monkeypatch):
    monkeypatch.setenv("MIMIR_COMPRESS_THRESHOLD_TOKENS", "0")
    tokens, source = resolve_threshold_tokens(1_000_000, 0.35)
    assert tokens == 350_000
    assert source == "explicit x 1000000"


def test_tokens_invalid_env_falls_back_to_percent(monkeypatch):
    monkeypatch.setenv("MIMIR_COMPRESS_THRESHOLD_TOKENS", "eighty-thousand")
    tokens, source = resolve_threshold_tokens(1_000_000, 0.35)
    assert tokens == 350_000
    assert source == "explicit x 1000000"


def test_tokens_none_percent_uses_percent_chain(monkeypatch):
    monkeypatch.setenv("MIMIR_COMPRESS_THRESHOLD", "0.10")
    tokens, source = resolve_threshold_tokens(1000)
    assert tokens == 100
    assert source == "env:MIMIR_COMPRESS_THRESHOLD x 1000"


# ── 3./4. 压缩器实例行为 ────────────────────────────────────────────────
def _make_compressor(**kw):
    params = dict(
        model="test-model",
        context_length=1_000_000,
        threshold_percent=0.35,
        protect_first_n=3,
        protect_last_n=6,
        tail_token_budget=2000,
        api_key="fake-key",
        base_url="http://127.0.0.1:9",
    )
    params.update(kw)
    return MimirContextCompressor(**params)


def test_compressor_records_source_and_applies_env(monkeypatch):
    monkeypatch.setenv("MIMIR_COMPRESS_THRESHOLD_TOKENS", "80000")
    comp = _make_compressor()
    assert comp.threshold_tokens == 80000
    assert comp.threshold_source == "env:MIMIR_COMPRESS_THRESHOLD_TOKENS"


def test_compressor_source_is_explicit_when_no_absolute_env():
    comp = _make_compressor(threshold_percent=0.35)
    assert comp.threshold_tokens == 350_000
    assert comp.threshold_source == "explicit x 1000000"


def test_update_model_does_not_clobber_env_override(monkeypatch):
    """核心回归：env 绝对覆盖必须活过 update_model 重算（修复前被静默抹掉）。"""
    monkeypatch.setenv("MIMIR_COMPRESS_THRESHOLD_TOKENS", "80000")
    comp = _make_compressor(context_length=8000)
    assert comp.threshold_tokens == 80000
    comp.update_model("test-model", 1_000_000)
    assert comp.threshold_tokens == 80000, "update_model 抹掉了 env 绝对阈值（clobber 未修）"
    assert comp.threshold_source == "env:MIMIR_COMPRESS_THRESHOLD_TOKENS"


def test_update_model_recomputes_when_no_env():
    """无 env 时 update_model 仍按 percent 重算（原行为不变）。"""
    comp = _make_compressor(context_length=8000, threshold_percent=0.35)
    comp.update_model("test-model", 1_000_000)
    assert comp.threshold_tokens == 350_000


# ── 5. 可观测性（trigger / skip / noop abort）───────────────────────────
def _small_messages(n=6, chars=20):
    out = []
    for i in range(n):
        out.append(
            {"role": "user" if i % 2 == 0 else "assistant", "content": "x" * chars}
        )
    return out


def test_compress_logs_skip_when_below_threshold(caplog):
    """低于阈值：应打 [COMPRESS] skip 行（此前静默）。"""
    comp = _make_compressor(context_length=1_000_000, threshold_percent=0.90)
    msgs = _small_messages()

    async def _run():
        return await comp.compress(msgs)

    with caplog.at_level(logging.INFO, logger=cc.logger.name):
        asyncio.run(_run())

    text = caplog.text
    assert "[COMPRESS] skip layer=agent" in text
    assert "source=" in text


def test_compress_logs_noop_or_skip_never_fake_success(caplog):
    """消息数未降且未修剪 → 必须报 abort reason=noop 或 skip，不能冒充成功。"""
    comp = _make_compressor(context_length=1000, threshold_percent=0.9)
    msgs = _small_messages(n=4, chars=10)

    async def _run():
        return await comp.compress(msgs)

    with caplog.at_level(logging.INFO, logger=cc.logger.name):
        asyncio.run(_run())

    assert ("[COMPRESS] skip layer=agent" in caplog.text) or (
        "[COMPRESS] abort layer=agent reason=noop" in caplog.text
    )
