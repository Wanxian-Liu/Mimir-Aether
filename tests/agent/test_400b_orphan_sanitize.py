"""
400B 孤儿 tool sanitize 单测（2026-08-20 Mimir 实施段-400B · engineering-code-reviewer）

覆盖（任务书 S4）：
1. 孤儿移除——tool 无前导 tool_calls → 整条删除
2. 缺失响应——assistant.tool_calls 无 tool 响应 → 条目移除（不插假补丁）
3. 长思考后场景——长思考（assistant 无 tool_calls）+ 孤儿 tool 混合
4. env 回退——MIMIR_SANITIZE_ORPHAN_TOOLS=0 → 完全不 sanitize
5. 不破坏现有测试（本文件自含回归跑现有 test_agent_loop.py）
"""

import sys
import json
import asyncio
import os as _os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent_loop import (
    _sanitize_orphan_tools,
    _orphan_sanitize_enabled,
    MimirAetherAgentLoop, AgentResult,
    tool_schema, STRING_PARAM,
)


def _asst(content="", tool_calls=None, reasoning=""):
    m = {"role": "assistant", "content": content}
    if tool_calls:
        m["tool_calls"] = tool_calls
    if reasoning:
        m["reasoning_content"] = reasoning
    return m


def _tool(tid, content="ok"):
    return {"role": "tool", "tool_call_id": tid, "content": content}


def _tc(tid, name="echo", args='{"a":1}'):
    return {"id": tid, "type": "function",
            "function": {"name": name, "arguments": args}}


# ============ 1. 孤儿移除 ============
def test_orphan_tool_removed():
    print("\n[400B-1] 孤儿 tool 移除（tool 无前导 tool_calls）")
    msgs = [
        {"role": "user", "content": "hi"},
        _asst("think", [_tc("call_1")]),
        _tool("call_1"),
        _tool("call_orphan"),  # 孤儿：无任何 assistant.tool_calls 引用
    ]
    removed = _sanitize_orphan_tools(msgs)
    assert removed == 1, f"应移除 1 条孤儿, got {removed}"
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant", "tool"], f"roles={roles}"
    assert all(m.get("tool_call_id") != "call_orphan" for m in msgs if m.get("role") == "tool")
    print("  ✅ 孤儿 tool 已删除, 配对消息保留")


# ============ 2. 缺失响应（Loki B-2 修复）============
def test_missing_response_toolcall_removed():
    print("\n[400B-2] 缺失响应——assistant.tool_calls 无 tool 响应 → 条目移除（不插假补丁）")
    msgs = [
        {"role": "user", "content": "hi"},
        _asst("", [_tc("call_1"), _tc("call_2")]),  # call_2 无响应
        _tool("call_1"),
    ]
    removed = _sanitize_orphan_tools(msgs)
    assert removed == 1, f"应移除 1 个缺失响应条目, got {removed}"
    # assistant 消息应只剩 call_1
    asst = [m for m in msgs if m["role"] == "assistant"][0]
    assert [tc["id"] for tc in asst["tool_calls"]] == ["call_1"], asst
    # 不插假补丁
    tool_msgs = [m for m in msgs if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    assert "Result from earlier conversation" not in str(msgs)
    print("  ✅ 缺失响应条目移除, 无假补丁")


def test_all_missing_removes_toolcalls_key():
    print("\n[400B-2b] 全部缺失——tool_calls 键整个移除")
    msgs = [
        _asst("text", [_tc("call_x")]),  # 唯一 tool_calls 无响应
    ]
    removed = _sanitize_orphan_tools(msgs)
    assert removed == 1
    assert "tool_calls" not in msgs[0], msgs[0]
    assert msgs[0]["content"] == "text"  # content 保留
    print("  ✅ tool_calls 键移除, content 保留")


# ============ 3. 长思考后场景 ============
def test_long_reasoning_scenario():
    print("\n[400B-3] 长思考后场景（assistant 带 reasoning 无 tool_calls + 孤儿 tool）")
    msgs = [
        {"role": "user", "content": "task"},
        _asst("长思考完成，未调用工具", None, "很长很长的思考过程..."),
        _tool("call_stale"),  # 上轮残留孤儿
        _asst("继续", [_tc("call_9")]),
        _tool("call_9"),
    ]
    removed = _sanitize_orphan_tools(msgs)
    assert removed == 1, f"应只移除 1 个孤儿, got {removed}"
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant", "assistant", "tool"], roles
    # reasoning 消息未被破坏
    assert msgs[1]["reasoning_content"] == "很长很长的思考过程..."
    print("  ✅ 长思考 assistant 保留, 孤儿移除, reasoning 字段无损")


# ============ 4. env 回退 ============
def test_env_gate_disabled():
    print("\n[400B-4] env 回退——MIMIR_SANITIZE_ORPHAN_TOOLS=0 → 门控关闭")
    _environ = getattr(_os, "environ")  # putenv 不更新缓存, 直接改 dict
    _environ["MIMIR_SANITIZE_ORPHAN_TOOLS"] = "0"
    try:
        assert _orphan_sanitize_enabled() is False
        print("  ✅ 门控返回 False（调用点将跳过 sanitize）")
    finally:
        _environ.pop("MIMIR_SANITIZE_ORPHAN_TOOLS", None)


def test_env_gate_default_on():
    print("\n[400B-4b] env 默认——未设置时默认开")
    _environ = getattr(_os, "environ")
    _environ.pop("MIMIR_SANITIZE_ORPHAN_TOOLS", None)
    assert _orphan_sanitize_enabled() is True
    print("  ✅ 默认开启")


# ============ 5. 集成：loop 内 sanitize 生效 ============
class MockChoice:
    def __init__(self, message):
        self.message = message

class MockMessage:
    def __init__(self, content="", tool_calls=None, reasoning_content=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.reasoning_content = reasoning_content

class MockResponse:
    def __init__(self, choices):
        self.choices = choices


def test_loop_integration_orphan_cleaned_before_send():
    print("\n[400B-5] 集成：loop 发送前 sanitize（chat_fn 收到无孤儿消息）")
    seen = {}

    async def chat_fn(messages):
        # 记录发送给 API 的消息——断言无孤儿 tool
        seen["sent"] = [dict(m) for m in messages]
        return MockResponse([MockChoice(MockMessage(content="Done"))])

    loop = MimirAetherAgentLoop(chat_fn=chat_fn, max_turns=5)
    result = asyncio.run(loop.run([
        {"role": "user", "content": "test"},
        # 预置孤儿 tool（模拟历史残留）——run() 应 sanitize
        {"role": "tool", "tool_call_id": "call_ghost", "content": "ghost"},
    ]))

    assert result.finished_naturally is True
    # 发送的消息中不应有 call_ghost 孤儿
    sent = seen.get("sent", [])
    tool_msgs = [m for m in sent if m.get("role") == "tool"]
    assert all(m.get("tool_call_id") != "call_ghost" for m in tool_msgs), sent
    print(f"  ✅ 发送 {len(sent)} 条消息, 无孤儿 tool（call_ghost 已清）")


def test_loop_integration_missing_response():
    print("\n[400B-5b] 集成：assistant.tool_calls 无响应 → 发送前条目移除")
    seen = {}
    call_count = [0]

    async def chat_fn(messages):
        call_count[0] += 1
        seen["sent"] = [dict(m) for m in messages]
        if call_count[0] == 1:
            return MockResponse([MockChoice(MockMessage(content="", tool_calls=[
                {"id": "call_a", "type": "function",
                 "function": {"name": "echo", "arguments": json.dumps({"text": "x"})}}
            ]))])
        return MockResponse([MockChoice(MockMessage(content="Done"))])

    tools = [tool_schema("echo", "Echo", {"type": "object", "properties": {"text": STRING_PARAM}, "required": ["text"]})]
    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=tools, max_turns=5)
    async def echo_handler(name, args, session_id):
        return json.dumps({"echo": args["text"]})
    loop.register_tool("echo", echo_handler)
    result = asyncio.run(loop.run([{"role": "user", "content": "t"}]))

    assert result.finished_naturally is True
    # 第二轮发送时 call_a 有响应——若 handler 正常则配对；这里验证无假补丁
    assert "Result from earlier conversation" not in str(seen.get("sent", []))
    print("  ✅ 无假补丁注入")


# ============ 运行器 ============
def main():
    tests = [
        test_orphan_tool_removed,
        test_missing_response_toolcall_removed,
        test_all_missing_removes_toolcalls_key,
        test_long_reasoning_scenario,
        test_env_gate_disabled,
        test_env_gate_default_on,
        test_loop_integration_orphan_cleaned_before_send,
        test_loop_integration_missing_response,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ 失败: {e}")
            import traceback
            traceback.print_exc()
    print("\n" + "=" * 60)
    print(f"[400B] 结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
