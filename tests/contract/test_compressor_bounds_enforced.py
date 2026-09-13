"""RS3 契约：压缩器 ``tail_token_budget`` 不得越出 ``COMPRESSOR_BOUNDS``。

四方裁决 2026-09-13 · 5 项（Loki 判据 + Mimir §8.3 修正）：

  ① default policy 各键落在 bounds 内
  ② ``__init__`` 的 env/cap 分支后 ``tail <= 8000``
  ③ ``update_model`` 分支同断言（修「重算抹掉夹紧」）
  ④ ``clamp_compressor_key`` 越界输入被夹（上/下界各一）
  ⑤ **反向断言**：源码内每一处 ``self.tail_token_budget =`` 都经夹紧
     （AST 扫描 ⇒ 防「同型绕过」再现，不是只测当前两处）

背景：修前实测 ``threshold_tokens=120000 → tail=24000``（0.20×120000）越出
bounds max 8000，并把 ``soft_ceiling`` 顶到 36000（应为 12000）。
"""
import ast
from pathlib import Path

import pytest

from agent.decision_compressor_policy import (
    COMPRESSOR_BOUNDS,
    clamp_compressor_key,
    compressor_init_kwargs_from_policy,
)

REPO = Path(__file__).resolve().parents[2]
COMPRESSOR_SRC = REPO / "agent" / "context_compressor.py"


# ── ① default policy 各键落在 bounds 内 ─────────────────────────────────────
def test_1_default_policy_within_bounds():
    policy = compressor_init_kwargs_from_policy()
    for key, spec in COMPRESSOR_BOUNDS.items():
        if key not in policy:
            continue
        val = policy[key]
        assert spec["min"] <= val <= spec["max"], (
            "%s=%s 越出 bounds [%s, %s]" % (key, val, spec["min"], spec["max"])
        )


# ── ④ clamp 越界输入被夹 ────────────────────────────────────────────────────
def test_4_clamp_both_directions():
    spec = COMPRESSOR_BOUNDS["tail_token_budget"]
    assert clamp_compressor_key("tail_token_budget", 999_999) == spec["max"]
    assert clamp_compressor_key("tail_token_budget", -5) == spec["min"]
    assert clamp_compressor_key("tail_token_budget", spec["default"]) == spec["default"]


# ── ②③ 真实实例：env 分支与 update_model 分支 ───────────────────────────────
def _make(monkeypatch, tokens=120000):
    monkeypatch.setenv("MIMIR_COMPRESS_THRESHOLD_TOKENS", str(tokens))
    from agent.context_compressor import MimirContextCompressor

    return MimirContextCompressor(
        model="deepseek/deepseek-flash",
        context_length=1_000_000,
        threshold_percent=0.35,
        **compressor_init_kwargs_from_policy(),
    )


def test_2_env_branch_tail_within_bounds(monkeypatch):
    c = _make(monkeypatch)
    assert c.threshold_tokens == 120000
    assert c.tail_token_budget <= COMPRESSOR_BOUNDS["tail_token_budget"]["max"]
    assert c.tail_token_budget == 8000, "120000×0.20=24000 必须被夹到 bounds max 8000"


def test_3_update_model_branch_tail_within_bounds(monkeypatch):
    c = _make(monkeypatch)
    c.update_model("deepseek/deepseek-flash", 1_000_000)
    assert c.tail_token_budget <= COMPRESSOR_BOUNDS["tail_token_budget"]["max"]
    assert c.threshold_tokens == 120000


def test_3b_soft_ceiling_derived_correctly(monkeypatch):
    c = _make(monkeypatch)
    assert int(c.tail_token_budget * 1.5) == 12000, "soft_ceiling 应为 8000×1.5=12000"


# ── ⑤ 反向断言：源码内无绕过（AST，不是正则）────────────────────────────────
def test_5_no_bypass_assignment_in_source():
    tree = ast.parse(COMPRESSOR_SRC.read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "tail_token_budget"
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                v = node.value
                ok = (
                    isinstance(v, ast.Call)
                    and isinstance(v.func, ast.Name)
                    and v.func.id == "clamp_compressor_key"
                )
                if not ok:
                    offenders.append(node.lineno)
    assert not offenders, (
        "以下行绕过 clamp_compressor_key 直接赋值 self.tail_token_budget: %s" % offenders
    )


def test_5b_same_pattern_scan_other_files():
    """同型绕过扫描（RS3 判据 3 精神）：全仓搜 ``tail_token_budget`` 的非夹紧赋值。"""
    offenders = []
    for path in (REPO / "agent").rglob("*.py"):
        if path.name == "context_compressor.py":
            continue  # 已被 test_5 覆盖
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr == "tail_token_budget":
                    v = node.value
                    if not (
                        isinstance(v, ast.Call)
                        and isinstance(v.func, ast.Name)
                        and v.func.id == "clamp_compressor_key"
                    ):
                        offenders.append("%s:%s" % (path.name, node.lineno))
    assert not offenders, "agent/ 内存在绕过夹紧的 tail_token_budget 赋值: %s" % offenders
