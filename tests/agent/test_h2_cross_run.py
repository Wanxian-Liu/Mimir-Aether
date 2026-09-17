"""H2: 跨 run「挂账—结算」—— 治「applied 78 / settled 1」（结算率 1.3%）。

真因（2026-09-17 定案）：`gateway/platforms/api_server.py:1538` 在 `_run_agent()`
**体内**建 agent ⇒ 每 run 一个新 compressor ⇒ 挂账（`_pending_post_measure`）是
**实例字段** ⇒ **跨 run 结算结构上不可能**（98.7% 的压缩收益永无 post 实计）。

本文件 7 组断言：
1. 跨 run 认领并结算（`settle_source=cross_run`）；
2. **会话隔离**（负控）：另一个会话不得认领，且不得吞掉原账；
3. fail-closed：未绑定会话 ⇒ 不落盘、不可认领（禁「全进程一个槽」退化）；
4. TTL 随**来源**取（跨 run 2000s 仍有效；同 run 2000s 过期）+ env 可调；
5. 连续性闸：transcript 比压缩完成时更短 ⇒ `discontinuous`，不作收益结算；
6. 单飞：跨 run 一账只结一次；同 run 结掉后**必须消费掉落盘副本**；
7. 结构闸：接线真的在（AST 级），认领靠原子 `os.replace`。
"""
import ast
import json
import time
from pathlib import Path

import agent.context_compressor as CC
from agent.context_compressor import MimirContextCompressor

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _arm(c, **kw):
    base = dict(
        of_ts="2026-09-17T00:00:00", pre_actual=100_000, pre_estimate=100_500,
        estimate_after=40_000, summary_total_tokens=5_000, summary_prompt_tokens=4_800,
        summary_mode="llm", gate_version="v1", armed_at=time.time(),
        compressed_count=35, original_count=400,
    )
    base.update(kw)
    c._pending_post_measure = base
    return base


def _rows():
    from mimir_constants import get_mimir_home
    p = get_mimir_home() / "data" / "compression_quality.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _post_rows():
    return [r for r in _rows() if r.get("kind") == "post_measure"]


def _armed_new_run(session, **arm_kw):
    """造「上个 run 挂好账、本 run 是全新实例」的场景（真因的最小复现）。"""
    a = _mk()
    a.bind_session(session)
    pend = _arm(a, **arm_kw)
    assert a._persist_pending(pend) is True
    b = _mk()
    b.bind_session(session)
    assert getattr(b, "_pending_post_measure", None) is None   # 内存确实为空
    return b


# ── 1. 跨 run 认领并结算 ────────────────────────────────────────────────────
def test_cross_run_claim_settles_with_source_label():
    b = _armed_new_run("sess-A")
    b.settle_post_measure(60_000, message_count=40, is_actual=True)

    rows = _post_rows()
    assert len(rows) == 1, rows
    r = rows[0]
    assert r["settle_reason"] == "settled"
    assert r["settle_source"] == "cross_run"
    assert r["claim_why"] == "ok"
    assert r["actual_delta_tokens"] == 40_000
    assert r["net_tokens"] == 35_000
    assert r["net_sign"] == "positive"


# ── 2. 会话隔离（负控）── 最要紧的一条 ─────────────────────────────────────
def test_other_session_neither_claims_nor_swallows_the_account():
    b_other = _armed_new_run("sess-A")
    b_other.bind_session("sess-B")           # 换成另一个会话
    b_other.settle_post_measure(60_000, message_count=40, is_actual=True)
    assert _post_rows() == [], "B 会话不应认领 A 会话的账"

    # 并且 A 的账**仍在盘上**（没被 B 吞掉/静默删除）
    c = _mk()
    c.bind_session("sess-A")
    c.settle_post_measure(60_000, message_count=40, is_actual=True)
    rows = _post_rows()
    assert len(rows) == 1 and rows[0]["settle_source"] == "cross_run"


# ── 3. fail-closed：未绑定会话 ─────────────────────────────────────────────
def test_unbound_session_persists_nothing_and_claims_nothing():
    a = _mk()                                # 刻意不 bind
    _arm(a)
    assert a._pending_store_path() is None
    assert a._persist_pending(a._pending_post_measure) is False

    b = _mk()                                # 也未绑定
    b.settle_post_measure(60_000, message_count=40, is_actual=True)
    assert _post_rows() == []


# ── 4. TTL 随来源取 ────────────────────────────────────────────────────────
def test_cross_run_ttl_is_longer_than_same_run_and_env_tunable(monkeypatch):
    # 2000s 前挂的账：超同 run 的 1800s，但远小于跨 run 默认 21600s ⇒ 应**结算**
    b = _armed_new_run("s1", armed_at=time.time() - 2000)
    b.settle_post_measure(60_000, message_count=40, is_actual=True)
    first = _post_rows()
    assert [r["settle_reason"] for r in first] == ["settled"]
    assert first[0]["ttl_s"] == CC._PENDING_XRUN_TTL_DEFAULT

    # 同一份账，同一会话，env 把跨 run TTL 压到 600s ⇒ 应判**过期**、不结算
    monkeypatch.setenv(CC._PENDING_XRUN_TTL_ENV, "600")
    d = _armed_new_run("s2", armed_at=time.time() - 2000)
    d.settle_post_measure(60_000, message_count=40, is_actual=True)
    second = [r for r in _post_rows() if r.get("settle_source") == "cross_run"]
    assert second[-1]["settle_reason"] == "expired"
    assert second[-1]["post_actual_prompt_tokens"] is None
    assert second[-1]["net_tokens"] is None


def test_same_run_ttl_unchanged_by_h2():
    """H2 不得改同 run 的既有语义（1800s 过期仍是 1800s）。"""
    c = _mk()
    c.bind_session("s3")
    _arm(c, armed_at=time.time() - 2000)
    c.settle_post_measure(60_000, message_count=40, is_actual=True)
    r = _post_rows()[0]
    assert r["settle_source"] == "same_run"
    assert r["settle_reason"] == "expired"
    assert r["ttl_s"] == 1800.0


# ── 5. 连续性闸 ────────────────────────────────────────────────────────────
def test_shorter_transcript_is_discontinuous_not_settled():
    b = _armed_new_run("s4", compressed_count=35)
    b.settle_post_measure(60_000, message_count=10, is_actual=True)   # 10 < 35
    r = _post_rows()[0]
    assert r["settle_reason"] == "discontinuous"
    assert r["post_actual_prompt_tokens"] is None
    assert r["net_tokens"] is None
    assert r["net_sign"] == "unmeasured"


def test_continuity_gate_does_not_apply_to_same_run():
    """同 run 内 message_count 语义不同（可能只传了部分），不得误判 discontinuous。"""
    c = _mk()
    c.bind_session("s5")
    _arm(c, compressed_count=35)
    c.settle_post_measure(60_000, message_count=5, is_actual=True)
    assert _post_rows()[0]["settle_reason"] == "settled"


# ── 6. 单飞 ────────────────────────────────────────────────────────────────
def test_account_settles_exactly_once_across_runs():
    b = _armed_new_run("s6")
    b.settle_post_measure(60_000, message_count=40, is_actual=True)
    c = _mk()
    c.bind_session("s6")
    c.settle_post_measure(50_000, message_count=41, is_actual=True)
    assert len(_post_rows()) == 1, "同一笔账跨 run 被结了两次"


def test_same_run_settle_consumes_the_persisted_copy():
    """同 run 结掉后，那份落盘副本必须被消费 —— 否则后续 run 会再结一遍。"""
    a = _mk()
    a.bind_session("s7")
    pend = _arm(a)
    assert a._persist_pending(pend) is True
    a.settle_post_measure(60_000, message_count=40, is_actual=True)   # 同 run 结掉
    assert [r["settle_source"] for r in _post_rows()] == ["same_run"]

    b = _mk()
    b.bind_session("s7")
    b.settle_post_measure(60_000, message_count=40, is_actual=True)
    assert len(_post_rows()) == 1


# ── 7. 结构闸（禁「写了没接线」） ───────────────────────────────────────────
class TestStructuralGate:
    def test_run_agent_binds_the_session_to_the_compressor(self):
        src = (REPO_ROOT / "run_agent.py").read_text(encoding="utf-8")
        assert "compressor.bind_session(self.session_id)" in src, (
            "会话身份必须在 agent 构造处绑给压缩器，否则跨 run 认领拿不到键"
        )

    def test_arm_path_persists_pending(self):
        src = (REPO_ROOT / "agent" / "context_compressor.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_record_quality_alert")
        seg = ast.get_source_segment(src, fn)
        assert "_persist_pending" in seg, "挂账侧必须落盘（否则账随 run 一起消失）"

    def test_claim_uses_atomic_replace_not_exists_plus_read(self):
        src = (REPO_ROOT / "agent" / "context_compressor.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_claim_pending")
        seg = ast.get_source_segment(src, fn)
        assert "os.replace" in seg, (
            "认领必须靠原子 rename —— exists()+read 会让两个 run 同时拿到同一笔账"
        )

    def test_no_global_slot_fallback(self):
        """未绑定会话必须**不落盘**（禁退化成「全进程一个槽」）。"""
        assert _mk()._pending_store_path() is None

    def test_store_dir_is_not_shared_with_the_ledger_file(self):
        c = _mk()
        c.bind_session("sess-x")
        p = c._pending_store_path()
        assert p is not None and p.parent.name == "pending_post_measure"
        assert p.suffix == ".json"
        assert "compression_quality" not in str(p)
