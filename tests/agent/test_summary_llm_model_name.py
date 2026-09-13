"""F-A 回归单测 — 摘要 LLM 模型名归一 + 失败可见化（2026-09-14）。

背景（本 bug 的完整链条，全部盘上实证）：
  压缩器 `_call_summary_llm` 把 `self.summary_model`（= `deepseek/deepseek-flash`，
  provider 命名空间形式）原样发往官方 `api.deepseek.com`，而官方 API 只认裸名：
      HTTP 400 "The supported API model names are deepseek-flash, deepseek-v4-pro,
               but you passed deepseek/deepseek-flash."
  → 非 200 分支只 `logger.debug` → 返回 None → `_generate_summary` 静默降级模板摘要
  → 模板摘要只保留 ~37% 实体 → 质量闸门（≥80%）回滚 → **上下文永不压缩**
  （生产实测：11 次 result 全 `mode=template`、0 次 `mode=llm`、0 条告警）。

本测试锁三件：
  ① 模型名必须归一到裸名（复用公共实现，不新造归一逻辑）
  ② 摘要 LLM 的任何失败都必须**可见**（WARNING + reason），不得再静默
  ③ 模板降级本身保留（合法降级路径），但必须留痕
"""
import asyncio
import logging

import pytest

from agent.context_compressor import ContextCompressorV2, _resolve_api_model_name


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    monkeypatch.delenv("MIMIR_COMPRESS_THRESHOLD_TOKENS", raising=False)
    monkeypatch.delenv("MIMIR_COMPRESS_VERIFY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


# ---------------------------------------------------------------- (1) 归一

def test_namespaced_model_is_stripped():
    """官方 API 400 的那个真实入参必须被归一。"""
    assert _resolve_api_model_name("deepseek/deepseek-flash") == "deepseek-flash"


def test_bare_model_unchanged():
    assert _resolve_api_model_name("deepseek-flash") == "deepseek-flash"
    assert _resolve_api_model_name("deepseek-v4-pro") == "deepseek-v4-pro"


def test_non_provider_colon_form_unchanged():
    """Ollama 风格 model:tag 不是 provider 前缀，不得被削。"""
    assert _resolve_api_model_name("qwen3.5:27b") == "qwen3.5:27b"


def test_known_provider_prefixes_stripped():
    assert _resolve_api_model_name("anthropic/claude-opus-4.6") == "claude-opus-4.6"
    assert _resolve_api_model_name("local:my-model") == "my-model"


def test_empty_model_safe():
    assert _resolve_api_model_name("") == ""


# ---------------------------------------------------------------- fake aiohttp

class _FakeResp:
    def __init__(self, status, text_body="", json_body=None):
        self.status = status
        self._text = text_body
        self._json = json_body

    async def text(self):
        return self._text

    async def json(self):
        return self._json

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


_CAPTURED = {}


class _FakeSession:
    """捕获 payload；按 _CAPTURED['mode'] 决定响应形态。"""

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, url, json=None, headers=None):
        _CAPTURED["url"] = url
        _CAPTURED["payload"] = json
        mode = _CAPTURED.get("mode", "ok")
        if mode == "http400":
            return _FakeResp(400, text_body='{"error":{"message":"bad model"}}')
        if mode == "boom":
            raise RuntimeError("connection reset")
        return _FakeResp(200, json_body={"choices": [{"message": {"content": "## Goal\nok"}}]})


def _patch_aiohttp(monkeypatch, mode="ok"):
    _CAPTURED.clear()
    _CAPTURED["mode"] = mode
    import agent.context_compressor as cc
    monkeypatch.setattr(cc.aiohttp, "ClientSession", _FakeSession)


def _make(model="deepseek/deepseek-flash", api_key="test-key"):
    return ContextCompressorV2(model=model, context_length=1_000_000, api_key=api_key)


# ---------------------------------------------------------------- (2) payload 用裸名

def test_payload_uses_normalized_model(monkeypatch):
    _patch_aiohttp(monkeypatch, "ok")
    c = _make()
    out = asyncio.run(c._call_summary_llm("some turns", 100))
    assert out == "## Goal\nok"
    assert _CAPTURED["payload"]["model"] == "deepseek-flash", _CAPTURED["payload"]["model"]
    assert _CAPTURED["url"].endswith("/v1/chat/completions")


# ---------------------------------------------------------------- (3) 失败可见

def test_http_error_logs_warning_and_records_reason(monkeypatch, caplog):
    _patch_aiohttp(monkeypatch, "http400")
    c = _make()
    with caplog.at_level(logging.WARNING):
        out = asyncio.run(c._call_summary_llm("some turns", 100))
    assert out is None
    assert c._last_summary_error == "http_400"
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "summary LLM rejected" in joined and "400" in joined


def test_exception_logs_warning_and_records_reason(monkeypatch, caplog):
    _patch_aiohttp(monkeypatch, "boom")
    c = _make()
    with caplog.at_level(logging.WARNING):
        out = asyncio.run(c._call_summary_llm("some turns", 100))
    assert out is None
    assert c._last_summary_error == "exc_RuntimeError"
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "summary LLM call failed" in joined


def test_missing_api_key_is_visible(monkeypatch, caplog):
    _patch_aiohttp(monkeypatch, "ok")
    c = _make(api_key="")
    with caplog.at_level(logging.WARNING):
        out = asyncio.run(c._call_summary_llm("some turns", 100))
    assert out is None
    assert c._last_summary_error == "no_api_key"
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "no API key" in joined


def test_template_degrade_is_visible_with_reason(monkeypatch, caplog):
    """模板降级仍允许（合法降级），但必须是可见的。"""
    _patch_aiohttp(monkeypatch, "http400")
    c = _make()
    turns = [{"role": "user", "content": "hello world"},
             {"role": "assistant", "content": "hi there"}]
    with caplog.at_level(logging.WARNING):
        summary, mode = asyncio.run(c._generate_summary(turns))
    assert mode == "template"
    assert summary  # 降级仍有内容
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "degraded to template" in joined and "http_400" in joined


def test_llm_mode_still_works_and_no_degrade_warning(monkeypatch, caplog):
    """正常路径不得打降级告警（防告警噪声）。"""
    _patch_aiohttp(monkeypatch, "ok")
    c = _make()
    turns = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
    with caplog.at_level(logging.WARNING):
        summary, mode = asyncio.run(c._generate_summary(turns))
    assert mode == "llm"
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "degraded to template" not in joined
