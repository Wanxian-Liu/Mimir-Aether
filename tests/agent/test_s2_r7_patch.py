"""R7 补丁单测 (2026-09-09 · B6 tool_schema_version + B3/B4 prefix invariant)

覆盖 (四方审计卡 R7 派发 · S2 Debug 轮遗留 L611-617):
- B6: _s2_tiered_frozen 三元组 (model, tool_schema_version, text)
- B3/B4: system 前缀冻结一致性 invariant (cache_boundary)

4 单测全部是行为契约 (测"两个数据怎么关联"), 非 change-detector。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # repo root

import agent.callers_mixin as cm
import tools.registry as _reg

JOINED = "STABLE\n\nCONTEXT\n\nVOLATILE"


class _TieredStub(cm.CallersMixin):
    """最小测试桩: 只实现 _tiered_system_prompt 依赖的成员 (行为契约, 不跑 agent)。"""

    def __init__(self, model: str = "deepseek-chat"):
        self.model = model
        self.system_prompt = "fallback-sp"
        self._s2_tiered_frozen = None
        self._parts_calls = 0

    def _build_system_prompt_parts(self):
        self._parts_calls += 1
        return {"stable": "STABLE", "context": "CONTEXT", "volatile": "VOLATILE"}


def _register_probe(name: str) -> None:
    _reg.registry.register(
        name,
        toolset="test",
        schema={"name": name, "description": "r7 probe"},
        handler=lambda **kw: "ok",
    )


# ── 1. 三级拼接顺序 + 冻结复用 (行为契约: 同 key 不重建) ──
def test_tiered_join_order_and_freeze():
    s = _TieredStub()
    out1 = s._tiered_system_prompt()
    assert out1 == JOINED, f"join order wrong: {out1!r}"
    assert s._parts_calls == 1
    # 同 model 同 schema 版本再调 -> 冻结命中 -> 不重建、字节一致
    out2 = s._tiered_system_prompt()
    assert out2 == out1
    assert s._parts_calls == 1, "frozen cache should short-circuit rebuild"
    assert s._s2_tiered_frozen[0] == "deepseek-chat"
    assert s._s2_tiered_frozen[2] == out1  # 三元组 text 在 idx2


# ── 2. model 变更 -> 冻结失效重建 (B6 key 关联) ──
def test_cache_invalidation_on_model_change():
    s = _TieredStub(model="model-a")
    s._tiered_system_prompt()
    assert s._parts_calls == 1
    s.model = "model-b"  # fallback / restore 换 model
    out = s._tiered_system_prompt()
    assert out == JOINED
    assert s._parts_calls == 2, "model change must invalidate frozen cache"
    assert s._s2_tiered_frozen[0] == "model-b"
    assert s._s2_tiered_frozen[1] == s._tool_schema_version()


# ── 3. B6: 工具 schema 版本 (registry mutation_count) 变更 -> 失效重建 ──
def test_b6_schema_version_invalidation():
    _register_probe("__r7_b6_probe_a__")
    try:
        s = _TieredStub()
        v1 = s._tool_schema_version()
        assert v1.startswith("tsv")
        s._tiered_system_prompt()
        assert s._parts_calls == 1
        assert s._s2_tiered_frozen[1] == v1

        # 注册新工具 -> mutation_count+1 -> schema 版本变 -> 冻结失配
        _register_probe("__r7_b6_probe_b__")
        v2 = s._tool_schema_version()
        assert v2 != v1, "registry mutation must change schema version"

        s._tiered_system_prompt()
        assert s._parts_calls == 2, "schema version change must invalidate frozen cache"
        assert s._s2_tiered_frozen[1] == v2
        assert s._s2_tiered_frozen[0] == s.model
    finally:
        _reg.registry.deregister("__r7_b6_probe_a__")
        _reg.registry.deregister("__r7_b6_probe_b__")


# ── 4. B3/B4: 前缀冻结一致性 invariant (喂坏数据应被拦) ──
def test_b3b4_prefix_invariant_catches_drift():
    s = _TieredStub()
    s._tiered_system_prompt()  # 建立冻结
    frozen_text = s._s2_tiered_frozen[2]

    # 正常: system = 冻结前缀 + 允许的 intent 尾段 -> OK
    ok_msgs = [{"role": "system", "content": frozen_text + "\n\n{intent-tail}"}]
    assert s._s2_prefix_invariant_ok(ok_msgs) is True

    # 喂坏1: 动态内容插到 stable 前缀之前 (B5 时间戳类) -> 必须拦
    bad_msgs = [{"role": "system", "content": "ts-2026-09-09\n\n" + frozen_text}]
    assert s._s2_prefix_invariant_ok(bad_msgs) is False

    # 喂坏2: 前缀完全漂移 (改写) -> 必须拦
    drift_msgs = [{"role": "system", "content": "completely different system"}]
    assert s._s2_prefix_invariant_ok(drift_msgs) is False

    # 无冻结 -> 无锚点可比 -> OK (不误拦)
    s2 = _TieredStub()
    assert s2._s2_prefix_invariant_ok([{"role": "system", "content": "anything"}]) is True

    # 旧二元组冻结 (迁移态, len<3) -> 视为无锚点 -> OK
    s3 = _TieredStub()
    s3._s2_tiered_frozen = ("deepseek-chat", "old-style-text")
    assert s3._s2_prefix_invariant_ok([{"role": "system", "content": "anything"}]) is True

    # 键不匹配 (model 已变, 冻结待重建) -> 不拦 (调用方将重建)
    s4 = _TieredStub(model="model-new")
    s4._s2_tiered_frozen = ("model-old", "tsv1", "stale-frozen-text")
    assert s4._s2_prefix_invariant_ok([{"role": "system", "content": "anything"}]) is True
