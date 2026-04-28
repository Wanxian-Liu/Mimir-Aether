"""
MimirAether Agent Loop 边界测试 - Ralph第2轮

测试边界情况和复杂场景：
- 多工具并发调用
- JSON参数解析错误
- 工具无注册处理器
- 嵌套推理提取
"""

import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent_loop import (
    MimirAetherAgentLoop, AgentResult,
    tool_schema, STRING_PARAM,
)


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
# 测试E1: 单轮多工具调用
# ============================================================================

def test_multi_tool_in_single_turn():
    print("\n[E1] 单轮多工具调用 (2 tools)")

    call_count = [0]
    async def chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            tc = MockMessage(tool_calls=[
                {"id": "call_1", "type": "function",
                 "function": {"name": "echo", "arguments": json.dumps({"text": "A"})}},
                {"id": "call_2", "type": "function",
                 "function": {"name": "echo", "arguments": json.dumps({"text": "B"})}},
            ])
            return MockResponse([MockChoice(tc)])
        else:
            return MockResponse([MockChoice(MockMessage(content="Done"))])

    tools = [tool_schema("echo", "Echo", {
        "type": "object", "properties": {"text": STRING_PARAM}, "required": ["text"]
    })]
    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=tools, max_turns=5)
    async def echo_handler(name, args, session_id):
        return json.dumps({"echo": args["text"]})
    loop.register_tool("echo", echo_handler)

    result = asyncio.run(loop.run([{"role": "user", "content": "test"}]))
    tool_msgs = [m for m in result.messages if m["role"] == "tool"]
    assert len(tool_msgs) == 2, f"Expected 2 tool results, got {len(tool_msgs)}"
    assert "A" in tool_msgs[0]["content"]
    assert "B" in tool_msgs[1]["content"]
    assert result.turns_used == 2
    print("  ✅ 通过")


# ============================================================================
# 测试E2: JSON参数解析错误
# ============================================================================

def test_json_parse_error():
    print("\n[E2] JSON参数解析错误")

    call_count = [0]
    async def chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            tc = MockMessage(tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "echo", "arguments": "not-valid-json!!!"}
            }])
            return MockResponse([MockChoice(tc)])
        else:
            return MockResponse([MockChoice(MockMessage(content="Done"))])

    tools = [tool_schema("echo", "Echo", {
        "type": "object", "properties": {"text": STRING_PARAM}
    })]
    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=tools, max_turns=5)
    async def echo_handler(name, args, session_id):
        return json.dumps({"echo": args.get("text", "")})
    loop.register_tool("echo", echo_handler)

    result = asyncio.run(loop.run([{"role": "user", "content": "test"}]))
    assert len(result.tool_errors) >= 1
    assert "JSON" in result.tool_errors[0].error or "Invalid" in result.tool_errors[0].error
    print("  ✅ 通过")


# ============================================================================
# 测试E3: 无处理器注册的工具
# ============================================================================

def test_no_handler_registered():
    print("\n[E3] 无处理器的已注册工具")

    call_count = [0]
    async def chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            tc = MockMessage(tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "orphan_tool", "arguments": "{}"}
            }])
            return MockResponse([MockChoice(tc)])
        else:
            return MockResponse([MockChoice(MockMessage(content="Done"))])

    tools = [tool_schema("orphan_tool", "No handler", {"type": "object", "properties": {}})]
    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=tools, max_turns=5)
    # 不注册工具处理器!
    result = asyncio.run(loop.run([{"role": "user", "content": "test"}]))

    assert len(result.tool_errors) >= 1
    assert "not implemented" in result.tool_errors[0].error.lower()
    print("  ✅ 通过")


# ============================================================================
# 测试E4: 推理提取（多格式）
# ============================================================================

def test_reasoning_formats():
    print("\n[E4] 多格式推理提取")

    # 测试 reasoning_details 格式
    class ReasoningDetail:
        def __init__(self, text):
            self.text = text

    async def chat_fn(messages):
        msg = MockMessage(content="Answer")
        msg.reasoning_details = [ReasoningDetail("thinking in details")]
        return MockResponse([MockChoice(msg)])

    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=[])
    result = asyncio.run(loop.run([{"role": "user", "content": "test"}]))
    assert len(result.reasoning_per_turn) == 1
    assert "thinking in details" in result.reasoning_per_turn[0]
    print("  ✅ 通过")


# ============================================================================
# 测试E5: 无穷循环限制
# ============================================================================

def test_max_turns_enforced():
    print("\n[E5] max_turns=1 强制限制")

    async def chat_fn(messages):
        tc = MockMessage(tool_calls=[{
            "id": "call_1", "type": "function",
            "function": {"name": "echo", "arguments": json.dumps({"text": "x"})}
        }])
        return MockResponse([MockChoice(tc)])

    tools = [tool_schema("echo", "Echo", {
        "type": "object", "properties": {"text": STRING_PARAM}
    })]
    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=tools, max_turns=1)
    async def echo_handler(name, args, session_id):
        return json.dumps({"echo": args["text"]})
    loop.register_tool("echo", echo_handler)

    result = asyncio.run(loop.run([{"role": "user", "content": "test"}]))
    assert result.turns_used == 1
    assert result.finished_naturally is False
    print("  ✅ 通过")


# ============================================================================
# 测试E6: 无tools的Agent
# ============================================================================

def test_no_tools_agent():
    print("\n[E6] 无tools配置")

    async def chat_fn(messages):
        return MockResponse([MockChoice(MockMessage(content="Straight answer"))])

    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=None, max_turns=5)
    result = asyncio.run(loop.run([{"role": "user", "content": "test"}]))
    assert result.turns_used == 1
    assert result.finished_naturally
    assert result.messages[-1]["content"] == "Straight answer"
    print("  ✅ 通过")


# ============================================================================
# 测试E7: register_tools批量注册
# ============================================================================

def test_batch_register():
    print("\n[E7] register_tools批量注册")

    call_count = [0]
    async def chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            tc = MockMessage(tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "tool_b", "arguments": json.dumps({"text": "b"})}
            }])
            return MockResponse([MockChoice(tc)])
        else:
            return MockResponse([MockChoice(MockMessage(content="Done"))])

    tools = [
        tool_schema("tool_a", "A", {"type": "object", "properties": {"text": STRING_PARAM}}),
        tool_schema("tool_b", "B", {"type": "object", "properties": {"text": STRING_PARAM}}),
    ]
    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=tools, max_turns=5)

    tool_map = {}
    async def handler_a(name, args, sid):
        return json.dumps({"tool": "a"})
    async def handler_b(name, args, sid):
        return json.dumps({"tool": "b"})
    tool_map["tool_a"] = handler_a
    tool_map["tool_b"] = handler_b

    loop.register_tools(tool_map)
    result = asyncio.run(loop.run([{"role": "user", "content": "test"}]))
    tool_msgs = [m for m in result.messages if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    assert "b" in tool_msgs[0]["content"]
    assert "tool_b" in loop.valid_tool_names
    assert "tool_a" in loop.valid_tool_names
    print("  ✅ 通过")


# ============================================================================
# 主函数
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Agent Loop 边界测试 - Ralph第2轮")
    print("=" * 60)

    tests = [
        test_multi_tool_in_single_turn,
        test_json_parse_error,
        test_no_handler_registered,
        test_reasoning_formats,
        test_max_turns_enforced,
        test_no_tools_agent,
        test_batch_register,
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
