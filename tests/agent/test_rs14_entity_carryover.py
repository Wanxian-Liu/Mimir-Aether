"""RS14: 压缩实体携带（C1）与摘要输出预算夹紧（C2）的回归测试。

背景：2026-09-14 实测 —— `compression_quality.jsonl` 187/187 全部 rollback，
`entity_retention_rate >= 0.80` 的行数为 0（历史最高 0.75）。根因两条：
  C1 实体按整段 pre 收集，而中间段必被摘要替换 ⇒ 结构上不可能达标；
  C2 摘要请求 `max_tokens*2`（上限 8000 ⇒ 16000）撞 30s 硬超时 ⇒ 95% 降级模板。
"""
import asyncio
import json
import logging

import pytest

import agent.context_compressor as CC
from agent.context_compressor import ContextCompressorV2, MimirContextCompressor


def _mk():
    c = MimirContextCompressor(
        model="deepseek/deepseek-flash", context_length=1000000, threshold_percent=0.12
    )
    c.update_model("deepseek/deepseek-flash", 1000000)
    return c


# ── C1: _collect_entities / _entity_index_block ────────────────────────────

def test_collect_entities_dedup_and_sorted():
    c = _mk()
    msgs = [
        {"role": "assistant", "content": "see commit a1b2c3d and commit a1b2c3d"},
        {"role": "user", "content": "~/wiki/concepts/x.md 讨论卡 discussions/a-b.md"},
    ]
    got = c._collect_entities(msgs)
    assert got == sorted(set(got)), "must be deduped + sorted"
    assert "commit a1b2c3d" in got
    assert "discussions/a-b.md" in got


def test_entity_index_block_empty_when_no_entities():
    c = _mk()
    assert c._entity_index_block([{"role": "user", "content": "hello there"}]) == ""


def test_entity_index_block_has_heading_and_items():
    c = _mk()
    block = c._entity_index_block([{"role": "assistant", "content": "commit a1b2c3d"}])
    assert CC.ENTITY_INDEX_HEADING in block
    assert "- commit a1b2c3d" in block


def test_entity_index_truncates_by_items_and_warns(caplog):
    c = _mk()
    payload = " ".join(f"commit {i:07x}" for i in range(200))
    with caplog.at_level(logging.WARNING):
        block = c._entity_index_block([{"role": "assistant", "content": payload}])
    items = [ln for ln in block.splitlines() if ln.startswith("- ")]
    assert len(items) == CC._ENTITY_INDEX_MAX_ITEMS
    assert "entity index truncated" in caplog.text


def test_entity_index_truncates_by_chars():
    c = _mk()
    long_ents = " ".join("discussions/" + "x" * 300 + f"{i}.md" for i in range(40))
    block = c._entity_index_block([{"role": "assistant", "content": long_ents}])
    assert len(block) <= CC._ENTITY_INDEX_MAX_CHARS + 200  # 仅标题/换行开销


# ── C1: 保留率闸门（核心回归） ─────────────────────────────────────────────

def _pre_with_middle_entities():
    """实体只出现在中间段（头 3 条与末尾都无实体）——复现生产形态。"""
    head = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "go"}]
    middle = [{"role": "assistant", "content": f"done discussions/card-{i}.md commit {i:07x}"}
              for i in range(20)]
    tail = [{"role": "assistant", "content": "recent"}, {"role": "user", "content": "?"}]
    return head + middle + tail


def test_retention_fails_without_carryover_control():
    """对照：无索引块时必然低于阈值（证明这个测试不是同义反复）。"""
    c = _mk()
    pre = _pre_with_middle_entities()
    post = pre[:3] + [{"role": "assistant", "content": "[CONTEXT COMPACTION]"}] + pre[-2:]
    rate, _ = c._verify_entity_retention(pre, post)
    assert rate < 0.80


def test_retention_passes_with_carryover():
    c = _mk()
    pre = _pre_with_middle_entities()
    summary = "[CONTEXT COMPACTION]\nstub"
    post = pre[:3] + [
        {"role": "assistant", "content": summary + c._entity_index_block(pre)}
    ] + pre[-2:]
    rate, missing = c._verify_entity_retention(pre, post)
    assert rate >= 0.80, f"missing={missing[:3]}"
    assert missing == []


def test_verify_returns_one_when_no_entities():
    c = _mk()
    rate, missing = c._verify_entity_retention(
        [{"role": "user", "content": "nothing here"}], [{"role": "user", "content": "x"}]
    )
    assert rate == 1.0 and missing == []


# ── C1: 两条摘要路径都携带 ────────────────────────────────────────────────

def test_generate_summary_llm_path_carries_entities(monkeypatch):
    c = _mk()
    async def _fake(content, max_tokens):
        return "## Goal\nstuff"
    monkeypatch.setattr(c, "_call_summary_llm", _fake)
    text, mode = asyncio.run(c._generate_summary(
        [{"role": "assistant", "content": "commit deadbee"}]
    ))
    assert mode == "llm"
    assert CC.ENTITY_INDEX_HEADING in text
    assert "commit deadbee" in text


def test_generate_summary_template_path_carries_entities(monkeypatch):
    c = _mk()
    async def _boom(content, max_tokens):
        raise RuntimeError("simulated llm outage")
    monkeypatch.setattr(c, "_call_summary_llm", _boom)
    text, mode = asyncio.run(c._generate_summary(
        [{"role": "assistant", "content": "commit deadbee"}]
    ))
    assert mode == "template"
    assert CC.ENTITY_INDEX_HEADING in text
    assert "commit deadbee" in text
    # 索引块不得污染 _previous_summary（否则会逐轮累积）
    assert CC.ENTITY_INDEX_HEADING not in (c._previous_summary or "")


# ── C2: 摘要输出预算夹紧 ──────────────────────────────────────────────────

def test_resolve_summary_max_output_default(monkeypatch):
    monkeypatch.delenv(CC._SUMMARY_MAX_OUTPUT_TOKENS_ENV, raising=False)
    assert CC._resolve_summary_max_output() == CC._SUMMARY_MAX_OUTPUT_TOKENS_DEFAULT


def test_resolve_summary_max_output_env_and_invalid(monkeypatch):
    monkeypatch.setenv(CC._SUMMARY_MAX_OUTPUT_TOKENS_ENV, "1234")
    assert CC._resolve_summary_max_output() == 1234
    monkeypatch.setenv(CC._SUMMARY_MAX_OUTPUT_TOKENS_ENV, "not-an-int")
    assert CC._resolve_summary_max_output() == CC._SUMMARY_MAX_OUTPUT_TOKENS_DEFAULT
    monkeypatch.setenv(CC._SUMMARY_MAX_OUTPUT_TOKENS_ENV, "-5")
    assert CC._resolve_summary_max_output() == CC._SUMMARY_MAX_OUTPUT_TOKENS_DEFAULT


def test_call_summary_llm_clamps_payload_max_tokens(monkeypatch):
    """budget 8000 ⇒ 原请求 16000；现在必须被夹到默认上限。"""
    c = _mk()
    c.api_key = "test-key"
    captured = {}

    class _Resp:
        status = 200
        async def json(self):
            return {"choices": [{"message": {"content": "SUM"}}]}
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
            captured["payload"] = json
            return _Resp()

    monkeypatch.setattr(CC.aiohttp, "ClientSession", _Session)
    monkeypatch.delenv(CC._SUMMARY_MAX_OUTPUT_TOKENS_ENV, raising=False)
    out = asyncio.run(c._call_summary_llm("prompt", 8000))
    assert out == "SUM"
    assert captured["payload"]["max_tokens"] == CC._SUMMARY_MAX_OUTPUT_TOKENS_DEFAULT


def test_call_summary_llm_keeps_small_budget(monkeypatch):
    """未超上限时不夹紧（小预算保持原样）。"""
    c = _mk()
    c.api_key = "test-key"
    captured = {}

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
            captured["payload"] = json
            return _Resp()

    monkeypatch.setattr(CC.aiohttp, "ClientSession", _Session)
    asyncio.run(c._call_summary_llm("prompt", 100))
    assert captured["payload"]["max_tokens"] == 200


# ── 端到端：索引块随压缩写回，且不影响 JSON 可序列化 ──────────────────────

def test_entity_index_block_json_serializable():
    c = _mk()
    block = c._entity_index_block([{"role": "assistant", "content": "commit abc1234"}])
    assert json.loads(json.dumps({"content": block}))["content"] == block
