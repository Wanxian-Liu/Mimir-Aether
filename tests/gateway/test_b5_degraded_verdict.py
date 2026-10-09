"""B5 (2026-10-09 · A 组审计整改 · 作者=Mimir) — cron_mixin 降级版投递判据。

事故：O-11（同日）把 cron 投递判据从「任何失败 ⇒ 事故」改成「只有**意外**失败
⇒ 事故」，但 `gateway/cron_mixin.py` 的 `except`-fallback 在
`cron.delivery_alerts` import 失败时把判据改回原样（fallback 收 `_expected`
却不用它，且 map 退化成 `{}`）⇒ 受控臂（按设计必失败）重新被算成真事故 ⇒
`last_status` 又压成 `delivery_failed` ⇒ 真故障与设计失败再次同形，并且
**看不出这是降级态**（读起来像真故障）。全天零覆盖（原 `# pragma: no cover`）。

定性（b）：保留降级，但
  ① 不抛错 —— 告警路径铁律：a broken target must not silence its own alarm；
     never raises（cron/delivery_alerts.py 头 L10-19）。改成抛错 = 拿更大的事故
     换小的（cron 循环被告警路径自己打断）。
  ② 显式标记降级（verdict["degraded"] / ["degraded_reason"] + 调用点 WARNING）。
  ③ 判据语义不因降级而改变 —— 降级版 expected_failure_map 只读 job spec 纯数据。

本文件给**两向**（§9 档位 ④）：
  - 正控：import 失败 ⇒ degraded 可见 ∧ 受控臂仍不算事故；
  - 负控：import 正常 ⇒ 不误标 degraded（防「永远 degraded」也能过断言）
          且真故障仍算事故。
外加**漂移守卫**：降级版 map 与真函数 map 逐例同值 —— 复制被测试钉死，
防「两份实现漂移」（Code Reviewer 卡 L52 的合规替代）。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import gateway.cron_mixin as cron_mixin  # noqa: E402
from cron.delivery_alerts import (  # noqa: E402
    delivery_verdict as real_verdict,
    expected_failure_map as real_map,
)

BAD = "feishu:oc_0000deadbeef"
OTHER_BAD = "feishu:real-chat"
SPECS = [
    {},
    None,
    {"expected_failures": {BAD: "positive"}},
    {"expected_failure_targets": [BAD]},
    {"expected_failures": {BAD: "positive"}, "expected_failure_targets": [OTHER_BAD]},
    # 畸形 spec ⇒ 什么都不预期（安全方向：宁可警报吵，不可警报哑）
    {"expected_failures": "oops"},
    {"expected_failure_targets": {"a": 1}},
    {"expected_failures": {BAD: "positive"}, "expected_failure_targets": "oops"},
]


# ------------------------------------------------------------ ① 漂移守卫
@pytest.mark.parametrize("spec", SPECS)
def test_degraded_map_matches_real_map(spec):
    """降级版 map 必须与真函数同值 —— 两份实现漂移即红。"""
    assert cron_mixin._degraded_expected_failure_map(spec) == real_map(spec)


# ------------------------------------------------------------ ② 降级版语义
def test_degraded_verdict_control_arm_is_not_an_incident():
    """正控：降级路径下受控臂失败仍不算事故（O-11 意图不因降级复活）。"""
    v = cron_mixin._degraded_delivery_verdict(
        {BAD: "invalid receive_id"},
        real_map({"expected_failures": {BAD: "positive"}}),
        reason="ImportError: boom",
    )
    assert v["ok"] is True
    assert v["control"] == [BAD]
    assert v["unexpected"] == {}
    assert v["degraded"] is True
    assert v["degraded_reason"] == "ImportError: boom"


def test_degraded_verdict_unexpected_failure_is_still_an_incident():
    """负控：降级不是免责 —— 真故障仍算事故。"""
    v = cron_mixin._degraded_delivery_verdict({OTHER_BAD: "HTTP 500"}, {})
    assert v["ok"] is False
    assert set(v["unexpected"]) == {OTHER_BAD}
    assert v["degraded"] is True


# ------------------------------------------------------------ ③ 装载器接线
def test_load_delivery_verdict_healthy_path_is_not_degraded():
    """负控：正常 import ⇒ degraded=None，且用的是真函数（不误标降级）。"""
    dv, efm, degraded = cron_mixin._load_delivery_verdict()
    assert degraded is None
    assert dv is real_verdict
    assert efm is real_map


def test_load_delivery_verdict_import_failure_is_marked_degraded(monkeypatch):
    """正控：import 失败 ⇒ 不抛错，但降级态显式可见（不许静默降级）。"""
    monkeypatch.setitem(sys.modules, "cron.delivery_alerts", None)
    dv, efm, degraded = cron_mixin._load_delivery_verdict()

    assert isinstance(degraded, str) and degraded, "降级原因必须非空"
    spec = {"expected_failures": {BAD: "positive"}}
    assert efm(spec) == real_map(spec), "降级后读不到 spec ⇒ 受控臂会重新变成事故"

    v = dv({BAD: "invalid receive_id"}, efm(spec))
    assert v["ok"] is True
    assert v["degraded"] is True


def test_import_failure_keeps_status_readable(monkeypatch):
    """端到端语义（不启 gateway）：降级下 n8 双控那轮判定仍是 ok=True。

    这正是 B5 的伤害面 —— O-11 之前该轮会把 last_status 压成
    delivery_failed，于是「真故障」与「设计失败」同形。
    """
    monkeypatch.setitem(sys.modules, "cron.delivery_alerts", None)
    dv, efm, _ = cron_mixin._load_delivery_verdict()
    spec = {
        "deliver": ["feishu:oc_0000deadbeef", "local"],
        "expected_failures": {"feishu:oc_0000deadbeef": "positive"},
    }
    v = dv({"feishu:oc_0000deadbeef": "invalid receive_id"}, efm(spec))
    assert v["ok"] is True, "B5：降级路径把 O-11 的修复回滚了"
    assert v["control"] == ["feishu:oc_0000deadbeef"]
