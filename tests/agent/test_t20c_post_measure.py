"""T20-c: post 实计口径 —— 「挂账—结算」两段式的回归测试。

背景（B 组设计 · `notes/2026-09-16-B组设计-压缩闭环.md`）：
台账 `prompt_tokens_after` = `result.compressed_tokens`（**内部估算**），不是实计
⇒ 净收益只能两端估算相减，**符号可能整错**（T2/T3/T4 因此阻塞）。

修法：`applied` 时**挂账**（记 pre 实计 + 摘要自身开销），等**下一次真实调用**的
`usage.prompt_tokens`（API 实计）**结算**。

本文件 5 组断言：
1. 结算数学：`net = (pre_actual - post_actual) - summary_total`，符号正确；
2. 三条防线：无账不结 / 过期不结 / 非实计不结（**宁可漏，不可错配**）；
3. 单飞与健壮：一账最多结一次；任何畸形输入都不得抛异常（埋点绝不阻断主循环）；
4. 挂账侧：applied 挂账、rollback 不挂；
5. 结构闸：`callers_mixin` 里必须**真的接了**结算调用（AST 级，禁「写了没接线」）。
"""
import ast
import json
import pathlib
import time

import pytest

import agent.context_compressor as CC
from agent.context_compressor import CompressionResult, MimirContextCompressor


def _mk(**kw):
    defaults = dict(
        model="test-model", context_length=8000, threshold_percent=0.5,
        protect_first_n=3, protect_last_n=6, tail_token_budget=2000,
        api_key="fake-key", base_url="http://127.0.0.1:9",
    )
    defaults.update(kw)
    c = MimirContextCompressor(**defaults)
    c.update_model("test-model", defaults["context_length"])
    return c


def _ledger_records():
    """走**真源**取台账路径（不硬编码 tmp 结构）⇒ conftest 改 HOME 也自动跟随。"""
    from mimir_constants import get_mimir_home
    p = get_mimir_home() / "data" / "compression_quality.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _arm(c, **kw):
    base = dict(
        of_ts="2026-09-16T00:00:00", pre_actual=100_000, pre_estimate=100_500,
        estimate_after=40_000, summary_total_tokens=5_000, summary_prompt_tokens=4_800,
        summary_mode="llm", gate_version="v1", armed_at=time.time(),
        compressed_count=35, original_count=400,
    )
    base.update(kw)
    c._pending_post_measure = base
    return base


# ── 1. 结算数学 ─────────────────────────────────────────────────────────────

class TestNetMath:
    def test_positive_net(self):
        c = _mk(); _arm(c)
        c.settle_post_measure(90_000, 40)
        recs = _ledger_records()
        assert len(recs) == 1
        r = recs[0]
        assert r["kind"] == "post_measure"          # ← 判别键（老消费者只看有无此键）
        assert r["settle_reason"] == "settled"
        assert r["actual_delta_tokens"] == 10_000
        assert r["net_tokens"] == 5_000             # 10000 - 5000（摘要自身开销）
        assert r["net_sign"] == "positive"
        assert r["post_message_count"] == 40

    def test_negative_net(self):
        c = _mk(); _arm(c)
        c.settle_post_measure(98_000, 40)
        r = _ledger_records()[0]
        assert r["actual_delta_tokens"] == 2_000
        assert r["net_tokens"] == -3_000            # 省得比摘要成本还少 ⇒ 净亏
        assert r["net_sign"] == "negative"

    def test_zero_net_is_labelled_zero_not_positive(self):
        """边界：净收益恰为 0 不得被算成「正」（否则符号统计会偏乐观）。"""
        c = _mk(); _arm(c, summary_total_tokens=10_000)
        c.settle_post_measure(90_000, 40)
        r = _ledger_records()[0]
        assert r["net_tokens"] == 0
        assert r["net_sign"] == "zero"

    def test_estimate_error_recorded(self):
        """副产品：估算值 vs 实计的偏离，本身是「量具准不准」的读数。"""
        c = _mk(); _arm(c, estimate_after=40_000)
        c.settle_post_measure(45_000, 40)
        r = _ledger_records()[0]
        assert r["estimate_error_tokens"] == 5_000

    def test_summary_cost_missing_treated_as_zero_but_delta_still_recorded(self):
        c = _mk(); _arm(c, summary_total_tokens=None)
        c.settle_post_measure(90_000, 40)
        r = _ledger_records()[0]
        assert r["actual_delta_tokens"] == 10_000
        assert r["net_tokens"] == 10_000            # 缺成本 ⇒ 按 0，但字段仍显式在


# ── 2. 三条防线（宁可漏，不可错配）─────────────────────────────────────────

class TestThreeDefenses:
    def test_no_pending_settles_nothing(self):
        """防线①：无账不结（绝大多数调用属此，开销 = 一次属性判空）。"""
        c = _mk()
        assert getattr(c, "_pending_post_measure", None) is None
        c.settle_post_measure(90_000, 40)
        assert _ledger_records() == []

    def test_expired_is_recorded_but_not_settled(self):
        """防线②：超 TTL ⇒ 记 expired、post 留空，**不做跨时段错配**。"""
        c = _mk(); _arm(c, armed_at=time.time() - 10_000)
        c.settle_post_measure(90_000, 40)
        r = _ledger_records()[0]
        assert r["settle_reason"] == "expired"
        assert r["post_actual_prompt_tokens"] is None
        assert r["actual_delta_tokens"] is None
        assert r["net_sign"] == "unmeasured"
        assert r["pending_age_s"] > 1800

    def test_ttl_is_env_tunable(self, monkeypatch):
        monkeypatch.setenv("MIMIR_POST_MEASURE_TTL_S", "99999")
        c = _mk(); _arm(c, armed_at=time.time() - 10_000)
        c.settle_post_measure(90_000, 40)
        assert _ledger_records()[0]["settle_reason"] == "settled"

    def test_non_actual_marks_unmeasured(self):
        """防线③：pt 来自粗估兜底 ⇒ 不算实计（否则把估算误差记成压缩收益）。"""
        c = _mk(); _arm(c)
        c.settle_post_measure(90_000, 40, is_actual=False)
        r = _ledger_records()[0]
        assert r["settle_reason"] == "unmeasured"
        assert r["net_tokens"] is None
        assert r["net_sign"] == "unmeasured"


# ── 3. 单飞与健壮 ───────────────────────────────────────────────────────────

class TestSingleFlightAndRobustness:
    def test_settles_at_most_once(self):
        c = _mk(); _arm(c)
        c.settle_post_measure(90_000, 40)
        c.settle_post_measure(50_000, 40)           # 无新挂账 ⇒ 不得再写
        assert len(_ledger_records()) == 1
        assert c._pending_post_measure is None

    def test_rearm_overwrites_pending(self):
        """单飞：一个 compressor 同时最多 1 条挂账，后挂账胜出（前一条不当僵尸留下）。"""
        c = _mk(); _arm(c, pre_actual=100_000)
        _arm(c, pre_actual=200_000, summary_total_tokens=0)
        c.settle_post_measure(100_000, 40)
        r = _ledger_records()[0]
        assert r["pre_actual_prompt_tokens"] == 200_000

    @pytest.mark.parametrize("val", [None, "", "abc", -1, 0])
    def test_never_raises_on_garbage(self, val):
        """埋点绝不阻断主循环：畸形入参只能「不结」，不能抛。"""
        c = _mk(); _arm(c)
        c.settle_post_measure(val, None)
        c.settle_post_measure(val, None)            # 无 pending 时同样不得抛

    def test_empty_pending_dict_is_falsy_and_skipped(self):
        c = _mk()
        c._pending_post_measure = {}
        c.settle_post_measure(1, 1)
        assert _ledger_records() == []

    def test_partial_pending_settles_as_unmeasured(self):
        """有账但缺 pre ⇒ 仍写行（可审计），但净收益标 unmeasured（不编数）。"""
        c = _mk()
        c._pending_post_measure = {"of_ts": "x", "armed_at": time.time()}
        c.settle_post_measure(90_000, 40)
        r = _ledger_records()[0]
        assert r["settle_reason"] == "settled"
        assert r["actual_delta_tokens"] is None
        assert r["net_sign"] == "unmeasured"


# ── 4. 挂账侧（arm）────────────────────────────────────────────────────────

class TestArmPath:
    def test_applied_arms_pending(self):
        c = _mk()
        c._pre_tokens_for_ledger = 100_500
        c._pre_tokens_actual_for_ledger = 100_000
        c._last_summary_usage = {
            "prompt_tokens": 4800, "completion_tokens": 200, "total_tokens": 5000,
        }
        res = CompressionResult(
            original_count=400, compressed_count=35, summary="s",
            pruned_tool_count=2, summary_mode="llm",
        )
        c._record_quality_alert(0.9, [], res, outcome="applied")
        pend = c._pending_post_measure
        assert pend is not None
        assert pend["pre_actual"] == 100_000
        assert pend["summary_total_tokens"] == 5000
        assert pend["compressed_count"] == 35

    def test_rollback_does_not_arm(self):
        """回滚 = 压缩未应用 ⇒ 没有「压缩后载荷」可测，不得挂账。"""
        c = _mk()
        res = CompressionResult(
            original_count=400, compressed_count=35, summary="s",
            pruned_tool_count=0, summary_mode="llm",
        )
        c._record_quality_alert(0.1, ["x"], res, outcome="rollback")
        assert getattr(c, "_pending_post_measure", None) is None


# ── 5. 结构闸 ──────────────────────────────────────────────────────────────

class TestStructuralGate:
    def test_callers_mixin_actually_calls_settle(self):
        """禁「写了没接线」：结算调用必须真的出现在 callers_mixin 里。"""
        p = pathlib.Path(CC.__file__).resolve().parent / "callers_mixin.py"
        tree = ast.parse(p.read_text(encoding="utf-8"))
        found = [
            n.attr for n in ast.walk(tree)
            if isinstance(n, ast.Attribute) and n.attr == "settle_post_measure"
        ]
        assert found, f"{p} 里找不到 settle_post_measure 调用 ⇒ T20-c 埋点未接线"

    def test_compress_module_does_not_import_callers_mixin(self):
        """防环：context_compressor 不得 import callers_mixin（本设计靠实例挂账，不靠导入）。"""
        tree = ast.parse(pathlib.Path(CC.__file__).read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                assert "callers_mixin" not in (n.module or "")
            elif isinstance(n, ast.Import):
                for a in n.names:
                    assert "callers_mixin" not in (a.name or "")

    def test_settle_body_never_writes_the_legacy_after_field(self):
        """边界：本卡**只追加** `kind=post_measure` 行，不改已有 `prompt_tokens_after`
        的语义 —— 老字段仍由 `_record_quality_alert` 独占写权。"""
        src = pathlib.Path(CC.__file__).read_text(encoding="utf-8")
        settle_body = src.split("def settle_post_measure", 1)[1].split("\n    def ", 1)[0]
        assert "prompt_tokens_after" not in settle_body
