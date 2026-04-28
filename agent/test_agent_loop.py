"""
MimirAether Agent Loop 集成测试

测试MimirAetherAgentLoop的完整执行流程：
- 基本对话（无工具调用）
- 单工具调用
- 多工具调用
- 工具错误处理
- SimpleAgentLoop同步包装器
"""

import sys
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent_loop import (
    MimirAetherAgentLoop, SimpleAgentLoop, AgentResult,
    tool_schema, STRING_PARAM,
)


# ============================================================================
# Mock 工具
# ============================================================================

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


# ============================================================================
# 测试1: 基本对话
# ============================================================================

def test_basic_conversation():
    print("\n[测试1] 基本对话（无工具调用）")

    async def chat_fn(messages):
        return MockResponse([MockChoice(MockMessage(content="你好，我是Mimir。"))])

    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=[], max_turns=5)
    result = asyncio.run(loop.run([{"role": "user", "content": "Hello"}]))

    assert isinstance(result, AgentResult)
    assert result.turns_used == 1
    assert result.finished_naturally is True
    assert len(result.tool_errors) == 0
    assert result.messages[-1]["content"] == "你好，我是Mimir。"
    print("  ✅ 通过")


# ============================================================================
# 测试2: 单工具调用
# ============================================================================

def test_single_tool_call():
    print("\n[测试2] 单工具调用")

    call_count = [0]

    async def chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            tc = MockMessage(tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "echo", "arguments": json.dumps({"text": "hello"})}
            }])
            return MockResponse([MockChoice(tc)])
        else:
            return MockResponse([MockChoice(MockMessage(content="Done!"))])

    tools = [tool_schema("echo", "Echo back text", {
        "type": "object", "properties": {"text": STRING_PARAM}, "required": ["text"]
    })]

    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=tools, max_turns=5)
    async def echo_handler(name, args, session_id):
        return json.dumps({"echo": args["text"]})
    loop.register_tool("echo", echo_handler)
    result = asyncio.run(loop.run([{"role": "user", "content": "echo test"}]))

    assert result.turns_used == 2
    assert result.finished_naturally is True
    assert len(result.tool_errors) == 0
    tool_msgs = [m for m in result.messages if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    assert "hello" in tool_msgs[0]["content"]
    print("  ✅ 通过")


# ============================================================================
# 测试3: 未知工具
# ============================================================================

def test_unknown_tool():
    print("\n[测试3] 未知工具调用")

    call_count = [0]
    async def chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            tc = MockMessage(tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "nonexistent", "arguments": "{}"}
            }])
            return MockResponse([MockChoice(tc)])
        else:
            return MockResponse([MockChoice(MockMessage(content='Done'))])

    loop = MimirAetherAgentLoop(chat_fn=chat_fn, max_turns=5)
    result = asyncio.run(loop.run([{"role": "user", "content": "test"}]))

    assert len(result.tool_errors) >= 1
    assert result.tool_errors[0].tool_name == "nonexistent"
    assert "Unknown tool" in result.tool_errors[0].error
    print("  ✅ 通过")


# ============================================================================
# 测试4: 工具异常
# ============================================================================

def test_tool_execution_error():
    print("\n[测试4] 工具执行异常")

    call_count = [0]
    async def chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            tc = MockMessage(tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "crash_tool", "arguments": "{}"}
            }])
            return MockResponse([MockChoice(tc)])
        else:
            return MockResponse([MockChoice(MockMessage(content="Recovered!"))])

    tools = [tool_schema("crash_tool", "Crashes", {"type": "object", "properties": {}})]
    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=tools, max_turns=5)
    async def crash_handler(name, args, session_id):
        raise RuntimeError("Simulated crash")
    loop.register_tool("crash_tool", crash_handler)
    result = asyncio.run(loop.run([{"role": "user", "content": "test"}]))

    assert len(result.tool_errors) == 1
    assert result.tool_errors[0].tool_name == "crash_tool"
    assert "RuntimeError" in result.tool_errors[0].error
    print("  ✅ 通过")


# ============================================================================
# 测试5: API失败
# ============================================================================

def test_api_call_failure():
    print("\n[测试5] API调用失败")

    async def chat_fn(messages):
        raise ConnectionError("Network failure")

    loop = MimirAetherAgentLoop(chat_fn=chat_fn, max_turns=5)
    result = asyncio.run(loop.run([{"role": "user", "content": "test"}]))
    assert result.finished_naturally is False
    print("  ✅ 通过")


# ============================================================================
# 测试6: max_turns
# ============================================================================

def test_max_turns():
    print("\n[测试6] max_turns限制")

    async def chat_fn(messages):
        tc = MockMessage(tool_calls=[{
            "id": "call_1", "type": "function",
            "function": {"name": "echo", "arguments": json.dumps({"text": "x"})}
        }])
        return MockResponse([MockChoice(tc)])

    tools = [tool_schema("echo", "Echo", {
        "type": "object", "properties": {"text": STRING_PARAM}, "required": ["text"]
    })]
    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=tools, max_turns=3)
    async def echo_handler(name, args, session_id):
        return json.dumps({"echo": args["text"]})
    loop.register_tool("echo", echo_handler)
    result = asyncio.run(loop.run([{"role": "user", "content": "test"}]))

    assert result.turns_used == 3
    assert result.finished_naturally is False
    print("  ✅ 通过")


# ============================================================================
# 测试7: SimpleAgentLoop
# ============================================================================

def test_simple_agent_loop():
    print("\n[测试7] SimpleAgentLoop同步包装器")

    def sync_chat_fn(messages):
        return MockResponse([MockChoice(MockMessage(content="Sync response"))])

    agent = SimpleAgentLoop(chat_fn=sync_chat_fn, max_turns=5)
    result = agent.run([{"role": "user", "content": "test"}])

    assert isinstance(result, AgentResult)
    assert result.turns_used == 1
    assert result.finished_naturally is True
    print("  ✅ 通过")


# ============================================================================
# 测试8: SimpleAgentLoop + 工具
# ============================================================================

def test_simple_agent_loop_with_tool():
    print("\n[测试8] SimpleAgentLoop + 工具")

    call_count = [0]
    def sync_chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            tc = MockMessage(tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "calc", "arguments": json.dumps({"expr": "2+2"})}
            }])
            return MockResponse([MockChoice(tc)])
        else:
            return MockResponse([MockChoice(MockMessage(content="4"))])

    tools = [tool_schema("calc", "Calculate", {
        "type": "object", "properties": {"expr": STRING_PARAM}, "required": ["expr"]
    })]
    agent = SimpleAgentLoop(chat_fn=sync_chat_fn, tools=tools, max_turns=5)

    @agent.tool("calc")
    def calc_handler(args):
        return json.dumps({"result": eval(args["expr"])})

    result = agent.run([{"role": "user", "content": "2+2"}])
    assert result.turns_used == 2
    tool_msgs = [m for m in result.messages if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    print("  ✅ 通过")


# ============================================================================
# 测试9: reasoning
# ============================================================================

def test_reasoning_extraction():
    print("\n[测试9] reasoning内容提取")

    async def chat_fn(messages):
        return MockResponse([MockChoice(
            MockMessage(content="A", reasoning_content="Let me think...")
        )])

    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=[])
    result = asyncio.run(loop.run([{"role": "user", "content": "test"}]))
    assert len(result.reasoning_per_turn) == 1
    assert result.reasoning_per_turn[0] == "Let me think..."
    print("  ✅ 通过")


# ============================================================================
# 主函数
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MimirAether Agent Loop 集成测试")
    print("=" * 60)

    tests = [
        test_basic_conversation,
        test_single_tool_call,
        test_unknown_tool,
        test_tool_execution_error,
        test_api_call_failure,
        test_max_turns,
        test_simple_agent_loop,
        test_simple_agent_loop_with_tool,
        test_reasoning_extraction,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ 失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    if failed > 0:
        sys.exit(1)
