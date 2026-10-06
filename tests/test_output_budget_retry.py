"""B1/B2 静默白跑修复 · 回归用例（2026-10-06）

病灶：`callers_mixin.py:700` 非 claude 硬编码 4096；思考型模型长上下文下把 4096 全给
`reasoning_content` ⇒ `content_len=0` + `finish_reason=length` ⇒ 空正文判死（静默死）。

修复：
- B1 空正文 ⇒ 自动关思考（thinking={"type":"disabled"}，2026-10-06 实测唯一给出 finish_reason=stop 的臂）重发一次
- B2 撞 length ⇒ max_tokens 自适应 ×2 重发一次
- 重发仍失败 ⇒ **出声**（ERROR 日志 OUTPUT_HEALTH_RETRY_FAILED），不静默退出

用受控差分：同一 fake 只换 attempt-1 返回值，观察"是否重发 / 重发参数"。
"""
import asyncio
import logging

import pytest

from agent import callers_mixin as cm


# ---------------------------------------------------------------- 纯函数层

@pytest.mark.parametrize("resp,expected", [
    # 正常
    ({"content": "答案", "finish_reason": "stop"}, cm.OUTPUT_HEALTH_OK),
    # B1：真空正文（无 tool_calls）
    ({"content": "", "finish_reason": "stop"}, cm.OUTPUT_HEALTH_EMPTY),
    ({"content": "   ", "finish_reason": "stop"}, cm.OUTPUT_HEALTH_EMPTY),
    ({"content": None, "finish_reason": "stop"}, cm.OUTPUT_HEALTH_EMPTY),
    # B2：有正文但撞顶
    ({"content": "半段", "finish_reason": "length"}, cm.OUTPUT_HEALTH_TRUNCATED),
    # B1+B2 合流：事故签名（探针复现 finish_reason=length content_len=0）
    ({"content": "", "finish_reason": "length"}, cm.OUTPUT_HEALTH_EMPTY_TRUNCATED),
    # 有工具调用 ⇒ 空正文是正常的（模型在干活）
    ({"content": "", "finish_reason": "tool_calls",
      "tool_calls": [{"id": "x", "function": {"name": "read_file"}}]}, cm.OUTPUT_HEALTH_OK),
    # 工具调用 + 撞顶 ⇒ 仍要补预算
    ({"content": "", "finish_reason": "length",
      "tool_calls": [{"id": "x", "function": {"name": "read_file"}}]}, cm.OUTPUT_HEALTH_TRUNCATED),
])
def test_classify_output_health(resp, expected):
    assert cm.classify_output_health(resp) == expected


def test_plan_output_retry_b1_only():
    """B1：只关思考，不加预算。"""
    p = cm.plan_output_retry(cm.OUTPUT_HEALTH_EMPTY, 4096, 128000)
    assert p["disable_thinking"] is True
    assert p["max_tokens"] == 4096


def test_plan_output_retry_b2_only():
    """B2：只加倍，不动思考开关。"""
    p = cm.plan_output_retry(cm.OUTPUT_HEALTH_TRUNCATED, 4096, 128000)
    assert p["disable_thinking"] is False
    assert p["max_tokens"] == 8192


def test_plan_output_retry_both():
    """事故签名：加倍 + 关思考。"""
    p = cm.plan_output_retry(cm.OUTPUT_HEALTH_EMPTY_TRUNCATED, 4096, 128000)
    assert p["disable_thinking"] is True
    assert p["max_tokens"] == 8192


def test_plan_output_retry_capped_by_context():
    """加倍不得越过上下文可给的量（且绝不小于原值）。"""
    p = cm.plan_output_retry(cm.OUTPUT_HEALTH_TRUNCATED, 4096, 8000)
    assert p["max_tokens"] >= 4096


# ---------------------------------------------------------------- 集成层

class _FakeCallers(cm.CallersMixin):
    """只换 `_builtin_call_model_with_tokens_once`，观察重发行为。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.attempt_args = []
        self.stream_callback = None
        self._current_streamed_text = ""
        self._stream_needs_break = False

    async def _builtin_call_model_with_tokens_once(self, messages, session_id, **kw):
        self.attempt_args.append(kw)
        assert self._responses, "调用次数超出给定序列（说明发生了计划外重发）"
        self._last_attempt_max_tokens = kw.get("max_tokens_override") or 4096
        self._last_attempt_context_length = 128000
        resp = self._responses.pop(0)
        if self.stream_callback and str(resp.get("content") or "").strip():
            self._fire_stream_delta(resp["content"])   # 模拟生产端流式外发
        return resp, 1.0


def _run(fake):
    backend = cm._BuiltinLlmBackend(fake)
    return asyncio.new_event_loop().run_until_complete(
        backend.call_model_with_tokens([{"role": "user", "content": "hi"}], "sid")
    )


def test_ok_no_retry():
    fake = _FakeCallers([{"content": "答案", "finish_reason": "stop"}])
    resp, _ = _run(fake)
    assert resp["content"] == "答案"
    assert len(fake.attempt_args) == 1, "正常返回不得触发重发"


def test_b1_empty_triggers_thinking_off_retry():
    fake = _FakeCallers([
        {"content": "", "finish_reason": "stop"},
        {"content": "复活", "finish_reason": "stop"},
    ])
    resp, _ = _run(fake)
    assert resp["content"] == "复活"
    assert len(fake.attempt_args) == 2
    assert fake.attempt_args[1]["disable_thinking"] is True
    assert fake.attempt_args[1]["max_tokens_override"] == 4096, "B1 不加预算"


def test_b2_length_doubles_budget():
    fake = _FakeCallers([
        {"content": "半段", "finish_reason": "length"},
        {"content": "完整", "finish_reason": "stop"},
    ])
    resp, _ = _run(fake)
    assert resp["content"] == "完整"
    assert len(fake.attempt_args) == 2
    assert fake.attempt_args[1]["max_tokens_override"] == 8192
    assert fake.attempt_args[1]["disable_thinking"] is False, "B2 不动思考开关"


def test_incident_signature_doubles_and_disables_thinking():
    """本次事故签名：finish_reason=length + content_len=0。"""
    fake = _FakeCallers([
        {"content": "", "finish_reason": "length"},
        {"content": "复活", "finish_reason": "stop"},
    ])
    resp, _ = _run(fake)
    assert resp["content"] == "复活"
    assert fake.attempt_args[1]["max_tokens_override"] == 8192
    assert fake.attempt_args[1]["disable_thinking"] is True


def test_tool_calls_not_retried():
    fake = _FakeCallers([
        {"content": "", "finish_reason": "tool_calls",
         "tool_calls": [{"id": "c1", "function": {"name": "read_file", "arguments": "{}"}}]},
    ])
    resp, _ = _run(fake)
    assert resp["tool_calls"]
    assert len(fake.attempt_args) == 1, "有工具调用不得重发（会重复执行工具）"


def test_retry_still_empty_speaks_up(caplog):
    """B1 尾句：重发仍空 ⇒ 必须出声（不许静默退出）。"""
    fake = _FakeCallers([
        {"content": "", "finish_reason": "length"},
        {"content": "", "finish_reason": "length"},
    ])
    with caplog.at_level(logging.ERROR):
        resp, _ = _run(fake)
    assert len(fake.attempt_args) == 2, "只重发一次，不得无限重试"
    assert any("OUTPUT_HEALTH_RETRY_FAILED" in r.getMessage() for r in caplog.records), \
        "重发仍失败必须打 ERROR（出声）"


def test_retry_streaming_suppressed_when_partial_already_emitted():
    """attempt-1 已流式外发部分正文 ⇒ 重发必须抑制流式，避免重复投递。"""
    fake = _FakeCallers([
        {"content": "半段", "finish_reason": "length"},
        {"content": "完整版", "finish_reason": "stop"},
    ])
    fake._current_streamed_text = "半段"      # 模拟已外发
    seen = []
    fake.stream_callback = lambda t: seen.append(t)
    resp, _ = _run(fake)
    assert resp["content"] == "完整版"
    assert seen == ["半段"], "只有 attempt-1 外发；重发期间被抑制（防重复投递）"
    assert "完整版" not in "".join(seen)


def test_thinking_off_params_payload():
    """关思考注入的线上参数 = 实测唯一给出 finish_reason=stop 的那组。"""
    payload = {}
    cm.apply_thinking_off(payload)
    assert payload.get("thinking") == {"type": "disabled"}
