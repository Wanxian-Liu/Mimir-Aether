"""决定 1(b)：compressor 原样返回时不得记 applied（2026-09-17）。"""
from __future__ import annotations

import pathlib
from types import SimpleNamespace

from agent.context_compressor import quality_outcome_for

SRC = pathlib.Path(__file__).resolve().parents[2] / "agent/context_compressor.py"


def test_equal_counts_is_noop():
    """本次实验的真实形状：56 → 56 却曾被记 applied。"""
    assert quality_outcome_for(SimpleNamespace(compressed_count=56, original_count=56)) == "noop"


def test_real_compression_is_applied():
    assert quality_outcome_for(SimpleNamespace(compressed_count=7, original_count=56)) == "applied"


def test_missing_fields_falls_back_to_applied():
    """保守：字段缺失/非法时不改变旧行为（避免把真压缩标成 noop）。"""
    assert quality_outcome_for(SimpleNamespace()) == "applied"
    assert quality_outcome_for(SimpleNamespace(compressed_count=None, original_count=None)) == "applied"
    assert quality_outcome_for(SimpleNamespace(compressed_count="x", original_count=1)) == "applied"


def test_zero_zero_is_noop():
    assert quality_outcome_for(SimpleNamespace(compressed_count=0, original_count=0)) == "noop"


def test_applied_call_site_uses_the_helper():
    src = SRC.read_text(encoding="utf-8")
    assert "outcome=quality_outcome_for(result)," in src
    assert 'outcome="applied")' not in src


def test_noop_outcome_does_not_arm_pending_settlement():
    """语义：noop 不应挂账（否则 T20-c 结算率分母继续失真）。"""
    src = SRC.read_text(encoding="utf-8")
    idx = src.find('if outcome == "applied":')
    assert idx > 0, "挂账分支缺失"
    # 挂账块必须仍以 applied 为条件（noop 走不到）
    assert "_pending_post_measure = {" in src[idx: idx + 1200]
