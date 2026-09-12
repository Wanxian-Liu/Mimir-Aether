"""B9（2026-09-13）：阈值按「有效窗口」定 —— 一等公民上限。

上游用例（``tests/agent/test_compress_threshold_source.py``）锁定了
``env 绝对值 > percent`` 的解析顺序；本用例锁定**在其上再叠的一层**有效窗口上限：

    threshold_tokens = min(configured, cap, floor(0.75 x context_length))

* ``cap`` 来自 tuned 键 ``compressor.effective_window_tokens``；
  **键缺失 ⇒ 整层不生效**（严格向后兼容：现有行为与既有断言不变）。
* ``source`` **只追加不重写**（既有断言匹配前缀 ``env:...`` 仍成立）。
* 上限生效时打 ``[COMPRESS-CAP]`` INFO 日志：context_length / configured / cap /
  window_ratio / 最终值 / 取胜原因（「哪一项取胜」可取证）。
"""

import json
import logging
import os
from pathlib import Path

import pytest

import agent.context_compressor as cc
from agent.context_compressor import (
    MimirContextCompressor,
    apply_effective_window_cap,
    resolve_effective_window_cap,
    resolve_threshold_tokens,
)

CAP_KEY = "compressor.effective_window_tokens"
_ENV_ABS_KEY = "MIMIR_COMPRESS_THRESHOLD_TOKENS"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in (_ENV_ABS_KEY, "MIMIR_COMPRESS_THRESHOLD"):
        monkeypatch.delenv(key, raising=False)


def _with_cap(monkeypatch, cap):
    """把 tuned overrides 钉到指定上限（``None`` ⇒ 键缺失）。"""
    import agent.tuned_thresholds as tt

    monkeypatch.setattr(
        tt, "load_overrides", lambda: {} if cap is None else {CAP_KEY: int(cap)}
    )


# ── 硬判据 1：真实旁路窗口 (163840) + env 350000 ⇒ ≤ 122880 且 ≠ 350000 ────────
def test_hard_criterion_ctx_163840_env_350000(monkeypatch):
    _with_cap(monkeypatch, 120_000)
    monkeypatch.setenv(_ENV_ABS_KEY, "350000")
    tokens, source = resolve_threshold_tokens(163_840, 0.35)
    assert tokens <= 122_880, f"未按有效窗口夹紧：{tokens}"
    assert tokens != 350_000, "env 绝对值仍然裸奔（上限没生效）"
    assert tokens == 120_000
    assert source == f"env:{_ENV_ABS_KEY} +cap:effective_window_tokens"


# ── 硬判据 2：ctx=1000000 + env 350000 ⇒ cap 取胜 = 120000 ────────────────────
def test_hard_criterion_ctx_1m_env_350000_cap_wins(monkeypatch):
    _with_cap(monkeypatch, 120_000)
    monkeypatch.setenv(_ENV_ABS_KEY, "350000")
    tokens, source = resolve_threshold_tokens(1_000_000, 0.35)
    assert tokens == 120_000
    assert "+cap:effective_window_tokens" in source
    # 既有断言匹配前缀 —— 追加不重写（回归护栏）
    assert source.startswith(f"env:{_ENV_ABS_KEY}")


# ── ① cap 取胜（percent 链路上同样生效）──────────────────────────────────────
def test_cap_wins_on_percent_path(monkeypatch):
    _with_cap(monkeypatch, 120_000)
    tokens, source = resolve_threshold_tokens(1_000_000, 0.35)
    assert tokens == 120_000
    assert source == "explicit x 1000000 +cap:effective_window_tokens"


# ── ② 0.75×ctx 夹紧取胜 ─────────────────────────────────────────────────────
def test_window_ratio_wins_when_smaller_than_cap(monkeypatch):
    _with_cap(monkeypatch, 120_000)
    monkeypatch.setenv(_ENV_ABS_KEY, "350000")
    tokens, source = resolve_threshold_tokens(100_000, 0.35)
    # 0.75 x 100000 = 75000 < cap 120000 ⇒ ratio 取胜
    assert tokens == 75_000
    assert source.endswith("+cap:window_ratio")
    assert source.startswith(f"env:{_ENV_ABS_KEY}")


# ── ③ 键缺失 ⇒ 与旧行为完全一致（含 ratio 项也不生效）────────────────────────
def test_key_absent_is_bitwise_backward_compatible(monkeypatch):
    _with_cap(monkeypatch, None)
    assert resolve_effective_window_cap() is None

    monkeypatch.setenv(_ENV_ABS_KEY, "350000")
    tokens, source = resolve_threshold_tokens(163_840, 0.35)
    assert tokens == 350_000, "键缺失时不应夹紧（0.75×ctx 项也必须不生效）"
    assert source == f"env:{_ENV_ABS_KEY}"

    # 去掉 env 后：小 ctx 的 percent 结果不得被 0.75×ctx 静默夹紧
    monkeypatch.delenv(_ENV_ABS_KEY, raising=False)
    tokens2, source2 = resolve_threshold_tokens(1_000, 0.35)
    assert tokens2 == 350, "键缺失时小窗口不得被 0.75×ctx 静默夹紧"
    assert "+cap:" not in source2


def test_key_absent_keeps_percent_path_unchanged(monkeypatch):
    _with_cap(monkeypatch, None)
    tokens, source = resolve_threshold_tokens(1_000_000, 0.35)
    assert tokens == 350_000
    assert source == "explicit x 1000000"


# ── ④ 非法 env 仍降级 + WARNING 不抛（有 / 无上限两种情形）───────────────────
@pytest.mark.parametrize("bad", ["abc"])
def test_invalid_env_degrades_and_warns(monkeypatch, caplog, bad):
    """非法 env（非数字）⇒ 降级回 percent + WARNING，不抛。"""
    _with_cap(monkeypatch, None)
    with caplog.at_level(logging.WARNING, logger=cc.logger.name):
        tokens, source = resolve_threshold_tokens(
            1_000_000, 0.35, env={_ENV_ABS_KEY: bad}
        )
    assert tokens == 350_000
    assert source == "explicit x 1000000"
    assert "not an int" in caplog.text, "非法 env 必须留 WARNING 痕迹（不许静默）"


def test_inline_comment_env_warns_and_stays_env(monkeypatch, caplog):
    """带行内注释的 env：剥注释后合法 ⇒ 仍是 env 绝对值（**既有行为**，不改）。"""
    _with_cap(monkeypatch, None)
    with caplog.at_level(logging.WARNING, logger=cc.logger.name):
        tokens, source = resolve_threshold_tokens(
            1_000_000, 0.35, env={_ENV_ABS_KEY: "350000  # was 80000"}
        )
    assert tokens == 350_000, "键缺失时不得引入新夹紧"
    assert source == f"env:{_ENV_ABS_KEY}"
    assert "inline comment" in caplog.text


def test_non_numeric_after_comment_strip_degrades(monkeypatch, caplog):
    """注释剥离后仍非数字 ⇒ 降级回 percent（不抛、不静默变 0）。"""
    _with_cap(monkeypatch, None)
    with caplog.at_level(logging.WARNING, logger=cc.logger.name):
        tokens, source = resolve_threshold_tokens(
            1_000_000, 0.35, env={_ENV_ABS_KEY: "# only a comment"}
        )
    assert tokens == 350_000
    assert source == "explicit x 1000000"


def test_inline_comment_env_degrades_then_capped(monkeypatch, caplog):
    """带行内注释的 env：降级回 percent 后**仍**受上限约束（不绕过）。"""
    _with_cap(monkeypatch, 120_000)
    with caplog.at_level(logging.WARNING, logger=cc.logger.name):
        tokens, source = resolve_threshold_tokens(
            1_000_000, 0.35, env={_ENV_ABS_KEY: "350000  # was 80000"}
        )
    assert tokens == 120_000
    assert "inline comment" in caplog.text
    assert source.endswith("+cap:effective_window_tokens")


# ── 可观测性：上限生效必须留可取证 INFO 行 ───────────────────────────────────
def test_cap_effect_logged_with_all_fields(monkeypatch, caplog):
    _with_cap(monkeypatch, 120_000)
    with caplog.at_level(logging.INFO, logger=cc.logger.name):
        value, _src = apply_effective_window_cap(350_000, "explicit x 1000000", 1_000_000)
    assert value == 120_000
    text = caplog.text
    assert "[COMPRESS-CAP]" in text
    for frag in (
        "context_length=1000000",
        "configured=350000",
        "cap=120000",
        "window_ratio=750000",
        "final=120000",
        "+cap:effective_window_tokens",
    ):
        assert frag in text, f"缺少取证字段 {frag}\n{text}"


def test_no_cap_log_when_limit_not_effective(monkeypatch, caplog):
    """configured 本就更小 ⇒ 上限未生效 ⇒ 既不夹紧也不打 CAP 日志。"""
    _with_cap(monkeypatch, 120_000)
    with caplog.at_level(logging.INFO, logger=cc.logger.name):
        value, source = apply_effective_window_cap(5_000, "env:X", 1_000_000)
    assert value == 5_000
    assert source == "env:X"
    assert "[COMPRESS-CAP]" not in caplog.text


# ── 真源链路：键「显式置位」才生效（走真实 load_overrides + 盘上文件）────────
def test_cap_is_read_from_real_tuned_file(monkeypatch):
    import agent.tuned_thresholds as tt

    home = Path(os.environ["MIMIR_AETHER_HOME"])
    data = home / "data"
    data.mkdir(parents=True, exist_ok=True)
    tuned = data / "tuned_thresholds.json"

    tuned.write_text(json.dumps({"overrides": {CAP_KEY: 120_000}}), encoding="utf-8")
    assert resolve_effective_window_cap() == 120_000
    monkeypatch.setenv(_ENV_ABS_KEY, "350000")
    assert resolve_threshold_tokens(1_000_000, 0.35)[0] == 120_000

    tuned.unlink()
    assert resolve_effective_window_cap() is None, "键缺失必须不生效"
    assert resolve_threshold_tokens(1_000_000, 0.35)[0] == 350_000
    assert tt.load_overrides() == {}


def test_registry_key_is_bounded():
    """键已注册为一等公民（有界），否则 load_overrides 会把它整条丢掉。"""
    import agent.tuned_thresholds as tt

    assert CAP_KEY in tt.registry_keys()
    spec = tt._REGISTRY[CAP_KEY]
    assert spec["type"] == "int"
    assert spec["min"] <= 120_000 <= spec["max"]


# ── 连带：压缩器实例（__init__ / update_model）真的吃到了上限 ────────────────
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


def test_compressor_init_applies_cap(monkeypatch):
    _with_cap(monkeypatch, 120_000)
    monkeypatch.setenv(_ENV_ABS_KEY, "350000")
    comp = _make_compressor()
    assert comp.threshold_tokens == 120_000
    assert "+cap:" in comp.threshold_source


def test_compressor_update_model_does_not_lose_cap(monkeypatch):
    """update_model 重算后不得把上限抹掉（同 clobber 病）。"""
    _with_cap(monkeypatch, 120_000)
    monkeypatch.setenv(_ENV_ABS_KEY, "350000")
    comp = _make_compressor(context_length=8_000)
    comp.update_model("test-model", 163_840)
    assert comp.threshold_tokens <= 122_880
    assert "+cap:" in comp.threshold_source


def test_compressor_without_key_keeps_old_threshold(monkeypatch):
    _with_cap(monkeypatch, None)
    comp = _make_compressor()
    assert comp.threshold_tokens == 350_000
    assert comp.threshold_source == "explicit x 1000000"
