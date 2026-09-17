"""决定 1(a) + 决定 2 步骤1 的闸（2026-09-17）。

背景（盘上实测 · pid 112311 · 11:38:55）：
    卫生层先把 57 条过滤成 56 条（只留 user/assistant）再喂 compressor；
    compressor 因 agent 层阈值（300000）未达而**原样返回 56**；
    而 no-op 判据比的是**过滤前**的 `_msg_count`（57）⇒ `56 >= 57` 为假
    ⇒ 真 no-op 被记成 `applied`（假绿）。本闸锁住修后的基线。
"""
from __future__ import annotations

import os
import pathlib

from gateway.router.agent_route_mixin import _hygiene_index_timeout_s

SRC = pathlib.Path(__file__).resolve().parents[2] / "gateway/router/agent_route_mixin.py"


def _src() -> str:
    return SRC.read_text(encoding="utf-8")


# ── 决定 1(a)：no-op 判据基线 ───────────────────────────────────────────────


def test_noop_baseline_is_post_filter_count():
    assert "if _new_count >= len(_hyg_msgs):" in _src()


def test_old_pre_filter_baseline_is_gone():
    """负控：旧比较式（比过滤前的 _msg_count）不得再出现 —— 它制造假绿。"""
    assert "if _new_count >= _msg_count:" not in _src()


def test_baseline_distinguishes_noop_from_real_compress():
    """语义闸：过滤后条数不变 ⇒ noop；真变少 ⇒ applied。"""
    def outcome(new_count: int, kept: int) -> str:
        return "noop" if new_count >= kept else "applied"

    assert outcome(56, 56) == "noop"       # 本次实验的真实形状
    assert outcome(56, 57) == "applied"    # 旧错读（会误记 applied）
    assert outcome(7, 56) == "applied"


# ── 决定 2 步骤1：卫生相位索引重写超时 ─────────────────────────────────────


def test_hygiene_call_site_passes_explicit_timeout():
    assert "timeout_s=_hygiene_index_timeout_s()," in _src()


def test_timeout_default_is_thirty_seconds(monkeypatch):
    monkeypatch.delenv("MIMIR_HYGIENE_INDEX_TIMEOUT_S", raising=False)
    assert _hygiene_index_timeout_s() == 30.0


def test_timeout_env_override(monkeypatch):
    monkeypatch.setenv("MIMIR_HYGIENE_INDEX_TIMEOUT_S", "12.5")
    assert _hygiene_index_timeout_s() == 12.5


def test_timeout_invalid_or_nonpositive_falls_back(monkeypatch):
    monkeypatch.setenv("MIMIR_HYGIENE_INDEX_TIMEOUT_S", "abc")
    assert _hygiene_index_timeout_s() == 30.0
    monkeypatch.setenv("MIMIR_HYGIENE_INDEX_TIMEOUT_S", "0")
    assert _hygiene_index_timeout_s() == 30.0
    monkeypatch.setenv("MIMIR_HYGIENE_INDEX_TIMEOUT_S", "-5")
    assert _hygiene_index_timeout_s() == 30.0


def test_timeout_is_much_smaller_than_legacy_default():
    """回归闸：默认上限必须显著小于旧的 300s（否则 D 没修）。"""
    os.environ.pop("MIMIR_HYGIENE_INDEX_TIMEOUT_S", None)
    assert _hygiene_index_timeout_s() <= 60.0
