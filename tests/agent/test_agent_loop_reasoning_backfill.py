"""400C — thinking 模式历史 assistant 缺 reasoning_content → 发请求前补空串。

真因（B4-b DRIVE 连续 FAIL）：core_loop 注入 conversation_history 时只构造
Message(role, content)（不传 reasoning_content）→ callers_mixin
._needs_reasoning_propagation() 在新会话首 turn 恒 False → 注入消息发出的 dict
无该键；而同请求里本轮新 assistant 带键（空串）→ DeepSeek thinking 模式 400
"The reasoning_content in the thinking mode must be passed back to the API"。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_AGENT_TESTS = Path(__file__).resolve().parent
if str(_AGENT_TESTS) not in sys.path:
    sys.path.insert(0, str(_AGENT_TESTS))

from agent.agent_loop import (  # noqa: E402
    MimirAetherAgentLoop,
    _backfill_missing_reasoning_content,
    _model_needs_reasoning_content,
)
from llm_mocks import MockChoice, MockMessage, MockResponse  # noqa: E402


def test_new_session_injected_history_gets_reasoning_key():
    """新会话首 turn：注入历史 assistant（无键）→ 请求面必须带 reasoning_content 键。"""
    seen = []

    async def chat_fn(messages):
        seen.append([dict(m) for m in messages])
        return MockResponse([MockChoice(MockMessage(content="ok"))])

    loop = MimirAetherAgentLoop(
        chat_fn=chat_fn, tools=[], max_turns=3, model="deepseek-chat"
    )
    asyncio.run(loop.run([
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},  # 注入历史：无 reasoning_content 键
        {"role": "user", "content": "go on"},
    ]))

    assert seen, "model_call not invoked"
    assistants = [m for m in seen[0] if m.get("role") == "assistant"]
    assert assistants, "injected assistant message missing from request"
    assert all("reasoning_content" in m for m in assistants)
    assert all(m["reasoning_content"] == "" for m in assistants)


def test_existing_value_preserved_missing_key_backfilled():
    """已有值不覆盖（保护 _last_reasoning 补偿 + S2 前缀冻结）；缺键者补空串。"""
    seen = []

    async def chat_fn(messages):
        seen.append([dict(m) for m in messages])
        return MockResponse([MockChoice(MockMessage(content="ok"))])

    loop = MimirAetherAgentLoop(
        chat_fn=chat_fn, tools=[], max_turns=2, model="deepseek-chat"
    )
    asyncio.run(loop.run([
        {"role": "assistant", "content": "old A", "reasoning_content": "old-reasoning"},
        {"role": "assistant", "content": "old B"},
        {"role": "user", "content": "continue"},
    ]))

    a1, a2 = seen[0][0], seen[0][1]
    assert a1["reasoning_content"] == "old-reasoning"
    assert a2["reasoning_content"] == ""


def test_non_thinking_model_untouched():
    """非 thinking 模型 / 未知模型名 → 一个字节都不加（保守不补）。"""
    msgs = [{"role": "assistant", "content": "x"}]
    assert _backfill_missing_reasoning_content(msgs, "gpt-4o") == 0
    assert "reasoning_content" not in msgs[0]
    assert _model_needs_reasoning_content("deepseek-chat")
    assert _model_needs_reasoning_content("kimi-k2")
    assert not _model_needs_reasoning_content(None)
    assert not _model_needs_reasoning_content("")


def test_env_gate_off_disables_backfill(monkeypatch):
    monkeypatch.setenv("MIMIR_BACKFILL_REASONING_CONTENT", "0")
    msgs = [{"role": "assistant", "content": "x"}]
    assert _backfill_missing_reasoning_content(msgs, "deepseek-chat") == 0
    assert "reasoning_content" not in msgs[0]


def test_env_gate_default_on(monkeypatch):
    monkeypatch.delenv("MIMIR_BACKFILL_REASONING_CONTENT", raising=False)
    msgs = [{"role": "assistant", "content": "x"}]
    assert _backfill_missing_reasoning_content(msgs, "deepseek-chat") == 1
    assert msgs[0]["reasoning_content"] == ""
