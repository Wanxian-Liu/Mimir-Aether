"""R5 / RS5：压缩口径统一（2026-09-13 · 刘哥批准 R5 方案 ①）

回归背景（实测，非推测）：
  同一阈值上挂着两套**不可比**的口径 ——
    · 闸门 `needs_compression()` 用 `last_prompt_tokens`（API prompt_tokens，含 system/记忆注入）
    · `compress()` 未收到 `current_tokens` 时用 `_estimate_tokens(messages)`（字符粗估）
  症状：上层开门、下层关门 ⇒ **永真 noop**。
  09-13 同日配对铁证（12:28:54）：闸门侧 API 165,785 ≥ 120,000 开门，
  内层 81,250 < 120,000 关门 ⇒ `skip + noop`，日志字段自证 `current_tokens=None`。
  当日累计：`[COMPRESS] skip=268 / abort(noop)=268 / result=0`。

本测试锁定：
  1. 行为：同一批小消息，传 current_tokens（≥阈值）→ 真压缩；不传 → noop（旧行为不变）
  2. 诊断：日志 current_tokens 字段随之改变（可观测）
  3. 契约：两处生产调用点（core_loop 预压缩 / agent_loop 行内）都传了 API 口径
  4. 回退：last_prompt_tokens 为 0/缺失时传 None → 退回粗估（不因缺数而误压）
"""
import asyncio
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

import agent.context_compressor as cc

_REPO = Path(__file__).resolve().parents[2]


def _make_compressor(context_length=2000, threshold_percent=0.5):
    return cc.MimirContextCompressor(
        model="test-model",
        context_length=context_length,
        threshold_percent=threshold_percent,
    )


def _messages(n=16, chars=20):
    out = []
    for i in range(n):
        out.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"m{i}-" + ("x" * chars),
            "id": f"m{i}",
        })
    return out


@pytest.fixture(autouse=True)
def _stub_summary(monkeypatch):
    """拦截 LLM 摘要（不打网络）；保留 compress 的阈值/边界逻辑。"""
    def _stub(self, *a, **k):
        async def _inner():
            return "STUB-SUMMARY", "stub"
        return _inner()
    return _stub


def test_caliber_unified_actually_compresses(monkeypatch):
    """核心回归：闸门开 + 传同一口径 ⇒ 不再永真 noop。"""
    comp = _make_compressor()
    comp.threshold_tokens = 1000
    msgs = _messages()

    async def _stub_llm(content, budget):
        return "STUB-SUMMARY"

    monkeypatch.setattr(comp, "_call_summary_llm", _stub_llm, raising=False)

    rough = comp._estimate_tokens(msgs)
    assert rough < comp.threshold_tokens, "夹具前提：粗估必须低于阈值（否则测不到口径差异）"

    # 旧行为：不传 current_tokens → 内层用粗估 → noop
    out_none, res_none = asyncio.run(comp.compress(msgs))
    assert res_none.original_count == res_none.compressed_count, "不传口径时应保持旧 noop 行为"
    assert len(out_none) == len(msgs)

    # 新行为：传 API 口径（≥阈值）→ 真压缩
    out_ct, res_ct = asyncio.run(comp.compress(msgs, current_tokens=5000))
    assert res_ct.compressed_count < res_ct.original_count, (
        "传了 API 口径仍 noop —— 口径统一未生效（RS5 回归）"
    )
    assert len(out_ct) < len(msgs)


def test_compressor_accepts_none_and_zero_as_fallback():
    """缺数（0/None）→ 退回粗估，不得被当成『已达阈值』。"""
    comp = _make_compressor()
    comp.threshold_tokens = 1000
    msgs = _messages()
    for val in (None, 0):
        out, res = asyncio.run(comp.compress(msgs, current_tokens=val))
        assert res.original_count == res.compressed_count, f"current_tokens={val} 不应触发压缩"


def test_skip_log_carries_passed_caliber(caplog, monkeypatch):
    """诊断契约：日志 current_tokens 字段必须反映实参（RS5 取证靠它）。"""
    comp = _make_compressor(context_length=1000, threshold_percent=0.9)
    msgs = _messages(n=6, chars=10)
    with caplog.at_level(logging.INFO, logger=cc.logger.name):
        asyncio.run(comp.compress(msgs, current_tokens=4321))
    # 契约落在 **trigger/skip** 行上（abort 行按设计不含该字段——09-13 取证即由此踩空）
    lines = [r.getMessage() for r in caplog.records if "[COMPRESS] " in r.getMessage()]
    caliber_lines = [
        m for m in lines
        if m.startswith("[COMPRESS] trigger") or m.startswith("[COMPRESS] skip")
    ]
    assert caliber_lines, "必须打 [COMPRESS] trigger/skip 行"
    assert "current_tokens=4321" in caliber_lines[-1], "日志未反映传入口径 → 取证会再次踩空"


# ── 契约：两处生产调用点 ────────────────────────────────────────────────
_CALL_SITES = [
    ("agent/core_loop.py", "预压缩"),
    ("agent/agent_loop.py", "行内压缩"),
]

_PATTERN = re.compile(
    r"current_tokens\s*=\s*getattr\(\s*self\.compressor\s*,\s*[\"']last_prompt_tokens[\"']"
)


@pytest.mark.parametrize("rel,label", _CALL_SITES)
def test_production_call_sites_pass_api_caliber(rel, label):
    src = (_REPO / rel).read_text(encoding="utf-8")
    assert _PATTERN.search(src), (
        f"{rel}（{label}）未把 API 口径传给 compress() —— RS5 会复发（上层开门/下层关门）"
    )


def test_no_other_bare_compress_call_in_agent_paths():
    """类风险全量扫：agent/ 内不得再有『无口径』的 await ...compress(...) 调用。"""
    offenders = []
    for rel, _label in _CALL_SITES:
        src = (_REPO / rel).read_text(encoding="utf-8")
        for m in re.finditer(r"await\s+self\.compressor\.compress\(\s*([^)]*)\)", src):
            args = m.group(1)
            if "current_tokens" not in args:
                offenders.append(f"{rel}: {m.group(0)[:80]}")
    assert not offenders, "仍有无口径的压缩调用点：" + "; ".join(offenders)
