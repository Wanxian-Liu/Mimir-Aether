"""RS14-D1: 压缩质量记录仪器化的回归测试（四方终审 §13.2 P0）。

背景（RS14 §0 E5 盘上实测）：`compression_quality.jsonl` 275 条全 rollback，且
`missing[:5]` 截断 + 无 `entity_count` ⇒ 历史保留率**不可复算**；无 `summary_elapsed_s`
/ `requested_max_tokens` ⇒ Q3 耗时只能拿「30.9s 超时截断值」反推（循环论证）。

本文件 5 组断言：
1. applied 路径落盘（历史只有 rollback ⇒ C1 生效后回滚率→0 将无数据可算）；
2. 率**可独立复算**：rate == (entity_count - missing_count) / entity_count；
3. `missing` 全量（>5 不截断）+ 上限 + `missing_capped`；
4. 索引统计 / 摘要耗时 / 请求预算 / `gate_version` 均落盘；
5. cooldown 早退不泄漏上一轮耗时（防「读数不可信」再生）。
"""
import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import pytest

import agent.context_compressor as CC
from agent.context_compressor import (
    CompressionResult,
    ContextCompressorV2,
    MimirContextCompressor,
)

_REQUIRED_D1_FIELDS = [
    "entity_count", "missing_count", "index_items", "index_chars", "index_capped",
    "summary_elapsed_s", "requested_max_tokens", "gate_version",
]


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


def _quality_records(tmp_path):
    """conftest 已把 MIMIR_AETHER_HOME 指向 tmp home ⇒ 记录落 tmp，不污染生产。"""
    p = tmp_path / "mimir_aether_home" / "data" / "compression_quality.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").strip().splitlines() if l.strip()]


def _mock_base_compress(post_msgs, result):
    return patch.object(
        ContextCompressorV2, "compress", new=AsyncMock(return_value=(post_msgs, result))
    )


@pytest.fixture
def verify_on(monkeypatch):
    monkeypatch.setenv("MIMIR_COMPRESS_VERIFY", "1")
    return True


# ── 1 + 2: applied 路径落盘 + 率可复算 ──────────────────────────────────────

class TestAppliedPathRecords:
    def test_applied_record_has_d1_fields_and_recomputable_rate(self, verify_on, tmp_path):
        c = _mk()
        _result = CompressionResult(
            original_count=400, compressed_count=35, summary="s",
            pruned_tool_count=2, summary_mode="llm",
        )
        pre = [{"role": "assistant", "content": "discussions/a.md commit abc1234"}]
        post = list(pre) + [{"role": "user", "content": "tail"}]
        with _mock_base_compress(post, _result):
            asyncio.run(c.compress(pre))

        recs = _quality_records(tmp_path)
        assert len(recs) == 1, f"applied 路径未落盘（历史只有 rollback）: {recs}"
        rec = recs[0]
        assert rec["outcome"] == "applied"
        for f in _REQUIRED_D1_FIELDS:
            assert f in rec, f"D-1 字段缺失: {f}"
        assert rec["gate_version"] == CC.ENTITY_GATE_VERSION
        assert rec["entity_count"] == 2
        assert rec["missing_count"] == 0
        assert rec["entity_retention_rate"] == pytest.approx(
            (rec["entity_count"] - rec["missing_count"]) / rec["entity_count"]
        )


# ── 3: missing 全量 + 上限 + capped 标记 ────────────────────────────────────

class TestMissingNotTruncated:
    def test_rollback_record_keeps_more_than_five_missing(self, verify_on, tmp_path):
        """历史 `missing[:5]` ⇒ 7 条缺失只剩 5 条。现在必须全量。"""
        c = _mk()
        pre = [{"role": "assistant", "content": f"discussions/card-{i}.md"} for i in range(7)]
        post = [{"role": "assistant", "content": "compacted, no entities"}]
        _result = CompressionResult(
            original_count=7, compressed_count=1, summary="s",
            pruned_tool_count=0, summary_mode="template",
        )
        with _mock_base_compress(post, _result):
            asyncio.run(c.compress(pre))

        rec = _quality_records(tmp_path)[0]
        assert rec["outcome"] == "rollback"
        assert rec["entity_count"] == 7 and rec["missing_count"] == 7
        assert len(rec["missing"]) == 7, "missing 仍被截断（应全量）"
        assert rec["missing_capped"] is False
        assert rec["entity_retention_rate"] == pytest.approx(0.0)
        assert rec["entity_retention_rate"] == pytest.approx(
            (rec["entity_count"] - rec["missing_count"]) / rec["entity_count"]
        )

    def test_missing_list_capped_at_limit_with_flag(self, verify_on, tmp_path):
        c = _mk()
        n = CC._QUALITY_MISSING_MAX_ITEMS + 25
        pre = [{"role": "assistant", "content": f"commit {i:07x}"} for i in range(n)]
        post = [{"role": "assistant", "content": "no entities"}]
        _result = CompressionResult(
            original_count=n, compressed_count=1, summary="s", summary_mode="template",
        )
        with _mock_base_compress(post, _result):
            asyncio.run(c.compress(pre))

        rec = _quality_records(tmp_path)[0]
        assert rec["entity_count"] == n and rec["missing_count"] == n
        assert len(rec["missing"]) == CC._QUALITY_MISSING_MAX_ITEMS
        assert rec["missing_capped"] is True


# ── 4: 索引统计 / 耗时 / 请求预算 / 闸门版本 ────────────────────────────────

class TestIndexAndSummaryTelemetry:
    def test_index_block_records_stats(self):
        c = _mk()
        c._entity_index_block([{"role": "assistant", "content": "commit abc1234\ncommit def5678"}])
        st = c._last_index_stats
        assert st["index_items"] == 2 and st["entity_total"] == 2
        assert st["index_capped"] is False and st["index_chars"] > 0

    def test_index_stats_flag_capping(self):
        c = _mk()
        payload = " ".join(f"commit {i:07x}" for i in range(CC._ENTITY_INDEX_MAX_ITEMS + 10))
        c._entity_index_block([{"role": "assistant", "content": payload}])
        assert c._last_index_stats["index_capped"] is True
        assert c._last_index_stats["index_items"] == CC._ENTITY_INDEX_MAX_ITEMS

    def test_call_summary_llm_records_requested_budget(self, monkeypatch):
        c = _mk()
        c.api_key = "test-key"

        class _Resp:
            status = 200

            async def json(self):
                return {"choices": [{"message": {"content": "S"}}]}

            async def text(self):
                return ""

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        class _Session:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def post(self, url, json=None, headers=None):
                return _Resp()

        monkeypatch.setattr(CC.aiohttp, "ClientSession", _Session)
        monkeypatch.delenv(CC._SUMMARY_MAX_OUTPUT_TOKENS_ENV, raising=False)
        asyncio.run(c._generate_summary([{"role": "assistant", "content": "commit abc1234"}]))
        # budget*2 被夹到默认上限 ⇒ 落盘的必须是「实际发出的预算」
        # 落盘关系必须自洽：requested = min(raw, cap)
        assert c._last_summary_budget_raw > 0
        assert c._last_summary_requested_max_tokens == min(
            c._last_summary_budget_raw, CC._SUMMARY_MAX_OUTPUT_TOKENS_DEFAULT
        )
        assert c._last_summary_elapsed_s is not None and c._last_summary_elapsed_s >= 0
        assert c._last_summary_attempts == 1

    def test_call_summary_llm_clamp_is_recorded(self, monkeypatch):
        """budget 8000 ⇒ 原始请求 16000；落盘 requested 必须是夹紧后的 4000。"""
        c = _mk()
        c.api_key = "test-key"

        class _Resp:
            status = 200

            async def json(self):
                return {"choices": [{"message": {"content": "S"}}]}

            async def text(self):
                return ""

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        class _Session:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def post(self, url, json=None, headers=None):
                return _Resp()

        monkeypatch.setattr(CC.aiohttp, "ClientSession", _Session)
        monkeypatch.delenv(CC._SUMMARY_MAX_OUTPUT_TOKENS_ENV, raising=False)
        asyncio.run(c._call_summary_llm("prompt", 8000))
        assert c._last_summary_budget_raw == 16000
        assert c._last_summary_requested_max_tokens == CC._SUMMARY_MAX_OUTPUT_TOKENS_DEFAULT

    def test_cooldown_early_return_does_not_leak_stale_timing(self, monkeypatch):
        """cooldown 早退时耗时必须为 None —— 否则记录会带上一轮的残留读数。"""
        c = _mk()
        c._last_summary_elapsed_s = 42.0
        c._last_summary_requested_max_tokens = 4096
        c._summary_failure_cooldown_until = time.monotonic() + 100
        out, mode = asyncio.run(c._generate_summary([{"role": "assistant", "content": "x"}]))
        assert (out, mode) == (None, "none")
        assert c._last_summary_elapsed_s is None
        assert c._last_summary_requested_max_tokens is None
        assert c._last_summary_attempts == 0


# ── 5: 端到端（真基类 compress 路径）——索引块真生成 ⇒ 记录里索引统计非零 ────

class TestEndToEndIndexCarryoverRecord:
    """不 mock 基类：真跑 `_generate_summary` → 索引块 → 闸门 → applied 记录。

    这一条是本卡的「判真」测试：它同时证明
      · C1 索引块让中段实体在 post 中真实存在（rate = 1.0）；
      · 记录里的 `index_items` / `index_chars` 来自真实索引生成，不是零值占位。
    """

    def test_real_compress_path_records_real_index_stats(self, verify_on, tmp_path, monkeypatch):
        c = _mk()
        monkeypatch.setenv("MIMIR_COMPRESS_VERIFY", "1")

        async def _fake_summary(content, max_tokens):
            c._last_summary_requested_max_tokens = max_tokens
            return "## Goal\nstub summary"

        monkeypatch.setattr(c, "_call_summary_llm", _fake_summary)

        head = [{"role": "user", "content": "hi"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "go"}]
        middle = [{"role": "assistant", "content": f"done discussions/card-{i}.md commit {i:07x}"}
                  for i in range(30)]
        tail = [{"role": "assistant", "content": "recent"}, {"role": "user", "content": "?"}]
        pre = head + middle + tail

        post, result = asyncio.run(c.compress(pre, current_tokens=10 ** 6))
        # 未回滚：压缩后消息数显著小于 pre
        assert len(post) < len(pre), f"仍未压缩（回滚？）post={len(post)} pre={len(pre)}"
        rec = _quality_records(tmp_path)[0]
        assert rec["outcome"] == "applied", f"应 applied，实际 {rec['outcome']}"
        assert rec["summary_mode"] == "llm"
        assert rec["entity_count"] == 60          # 30 卡路径 + 30 commit
        assert rec["missing_count"] == 0
        assert rec["entity_retention_rate"] == pytest.approx(1.0)
        # 索引块只覆盖**中段**（头/尾消息按设计原样保留）⇒ items 可略小于 entity_count
        assert rec["index_items"] >= 50, f"索引统计疑似零值占位: {rec['index_items']}"
        assert rec["index_capped"] is False
        assert 0 < rec["index_chars"] <= CC._ENTITY_INDEX_MAX_CHARS
        assert rec["gate_version"] == CC.ENTITY_GATE_VERSION
        assert rec["entity_retention_rate"] == pytest.approx(
            (rec["entity_count"] - rec["missing_count"]) / rec["entity_count"]
        )

    def test_no_index_control_group_rolls_back(self, verify_on, tmp_path, monkeypatch):
        """对照组：同一负载但索引块被禁（模拟 C1 未生效）⇒ 必回滚。

        没有这条，上一测试可能因「闸门恒真」而空过。"""
        c = _mk()
        monkeypatch.setattr(c, "_entity_index_block", lambda messages: "")
        c._call_summary_llm = AsyncMock(return_value="## Goal\nstub summary")

        head = [{"role": "user", "content": "hi"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "go"}]
        middle = [{"role": "assistant", "content": f"done discussions/card-{i}.md commit {i:07x}"}
                  for i in range(30)]
        tail = [{"role": "assistant", "content": "recent"}, {"role": "user", "content": "?"}]
        pre = head + middle + tail

        post, result = asyncio.run(c.compress(pre, current_tokens=10 ** 6))
        assert len(post) == len(pre), "对照组装：无索引仍应回滚"
        rec = _quality_records(tmp_path)[0]
        assert rec["outcome"] == "rollback"
        # 无索引 ⇒ 中段实体随摘要丢失（模板摘要会捎带 1~2 个，故非精确 60）
        assert rec["entity_count"] == 60
        assert rec["missing_count"] >= 55
        assert rec["entity_retention_rate"] < 0.20
        assert len(rec["missing"]) == rec["missing_count"], (
            "missing 明细必须全量（这是历史不可复算的病根）"
        )
