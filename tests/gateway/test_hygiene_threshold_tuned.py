"""卫生压缩阈值走 tuned 键（刘哥 2026-09-16 令：20万 -> 30万，热调不需重启）。

守的是什么不变量：
  1. 真源唯一 = tuned 键 `compressor.hygiene_token_threshold`（有界、每轮读盘）；
  2. 键缺失/值非法/导入失败 ⇒ **回退历史默认 200_000**（不抛：别把压缩路径变脆）；
  3. 源码里**不再有**裸常量赋值（防「改回去」或「两处真源」）；
  4. 该常量确实被用作触发判据（不是只改了个没人用的变量）。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from gateway.router import agent_route_mixin as mixin

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MIXIN = REPO_ROOT / "gateway" / "router" / "agent_route_mixin.py"
TUNED = REPO_ROOT / "agent" / "tuned_thresholds.py"


# ---------------------------------------------------------------- 真源与回退
def test_returns_tuned_value(monkeypatch) -> None:
    """键存在 ⇒ 用键值（这里钉 300_000 = 刘哥令的目标值）。"""
    import agent.tuned_thresholds as tt

    monkeypatch.setattr(tt, "get_tuned_int", lambda key: 300_000)
    assert mixin._hygiene_token_threshold() == 300_000


@pytest.mark.parametrize("boom", [KeyError("missing"), ValueError("bad"), ImportError("no")])
def test_falls_back_to_historical_default(monkeypatch, boom) -> None:
    """键缺失 / 值非法 ⇒ 回退 200_000，且**不抛**。"""
    import agent.tuned_thresholds as tt

    def _raise(key):
        raise boom

    monkeypatch.setattr(tt, "get_tuned_int", _raise)
    assert mixin._hygiene_token_threshold() == 200_000


def test_default_constant_is_historical_value() -> None:
    assert mixin._HYGIENE_TOKEN_THRESHOLD_DEFAULT == 200_000


# ---------------------------------------------------------------- 结构不变量
def test_source_has_no_hardcoded_trigger_literal() -> None:
    """`_compress_token_threshold = <数字>` 这种裸常量赋值必须消失（两处真源 = 事故土壤）。"""
    src = MIXIN.read_text(encoding="utf-8")
    assert "_compress_token_threshold = _hygiene_token_threshold()" in src
    offenders = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "_compress_token_threshold" \
                        and isinstance(node.value, ast.Constant):
                    offenders.append(node.lineno)
    assert offenders == [], f"仍是裸常量（行 {offenders}）——调阈值会又变成改码+重启"


def test_constant_is_actually_used_as_trigger() -> None:
    """真被当判据用（防「改了没人用的变量」）。"""
    tree = ast.parse(MIXIN.read_text(encoding="utf-8"))
    uses = [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Compare)
            and any(isinstance(c, ast.Name) and c.id == "_compress_token_threshold"
                    for c in [n.left, *n.comparators])]
    assert uses, "整份源码里没有 _compress_token_threshold 的比较用法"


def test_registry_key_is_bounded() -> None:
    """注册表必须有界（bounded）且默认值 = 历史值。"""
    from agent.tuned_thresholds import _REGISTRY

    spec = _REGISTRY["compressor.hygiene_token_threshold"]
    assert spec["default"] == 200_000
    assert spec["min"] < spec["max"]
    assert spec["min"] <= 300_000 <= spec["max"], "刘哥令的目标值必须落在合法区间内"
    assert spec["type"] == "int"
    assert "compressor.hygiene_token_threshold" in TUNED.read_text(encoding="utf-8")
