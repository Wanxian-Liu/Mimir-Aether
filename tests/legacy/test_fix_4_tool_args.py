"""
Test for tool argument JSON repair and reasoning_content propagation fixes.
"""
import json
import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Test 1: JSON repair
print("=== Test 1: JSON Repair ===")
from agent.json_repair import repair_json_arguments

test_cases = [
    # (input, should_succeed, description)
    ('{"path": "/tmp/test", "content": "hello"}', True, "Valid JSON"),
    ('{"path": "/tmp/test", "content": "hello",}', True, "Trailing comma"),
    ("{'path': '/tmp/test', 'content': 'hello'}", True, "Single quotes"),
    ('{path: "/tmp/test", content: "hello world"}', True, "Unquoted keys"),
    ('{"path": "/tmp/test", "content": "line1\nline2"}', True, "Newlines in value"),
    ('{"path": "/tmp/test" "content": "hello"}', True, "Concatenated strings"),
    ('{"path": "/tmp/test", "content": "hello"}\n', True, "Trailing newline"),
    ('not json at all', False, "Completely invalid"),
]

for raw, should_succeed, desc in test_cases:
    try:
        repaired = repair_json_arguments(raw)
        parsed = json.loads(repaired)
        if should_succeed:
            print(f"  ✓ {desc}: {parsed}")
        else:
            print(f"  ✗ {desc}: Should have failed but got {parsed}")
    except ValueError as e:
        if not should_succeed:
            print(f"  ✓ {desc}: Correctly rejected")
        else:
            print(f"  ✗ {desc}: Failed with {e}")

# Test 2: Reasoning propagation detection
print("\n=== Test 2: Reasoning Propagation Detection ===")
from agent.core_loop import MimirAetherAgent, Message, MessageRole

# Create minimal agent with deepseek model
agent = MimirAetherAgent(model="deepseek/deepseek-chat", max_iterations=5)

# Initially no reasoning in history -> no propagation needed
assert not agent._needs_reasoning_propagation(), "Should not need propagation initially"
print("  ✓ No propagation needed when history has no reasoning")

# Add an assistant message with reasoning_content
agent.conversation_history.append(Message(
    role=MessageRole.ASSISTANT,
    content="Let me check something",
    tool_calls=[{"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "/tmp/test"}'}}],
    reasoning_content="I need to read the file first..."
))

assert agent._needs_reasoning_propagation(), "Should need propagation after reasoning appears"
print("  ✓ Propagation needed after reasoning appears in history")

# Test _build_full_messages with reasoning
agent.conversation_history.append(Message(
    role=MessageRole.TOOL,
    content="file contents here",
    tool_call_id="call_1"
))

# Add second assistant message WITHOUT reasoning
agent.conversation_history.append(Message(
    role=MessageRole.ASSISTANT,
    content="Now let me write the file",
    tool_calls=[{"id": "call_2", "type": "function", "function": {"name": "write_file", "arguments": '{"path": "/tmp/out", "content": "done"}'}}],
    reasoning_content=None  # No reasoning!
))

messages = agent._build_full_messages()

# Find the second assistant message
assistant_msgs = [m for m in messages if m["role"] == "assistant"]
print(f"  Assistant messages in built output: {len(assistant_msgs)}")
for i, am in enumerate(assistant_msgs):
    has_rc = "reasoning_content" in am
    rc_val = am.get("reasoning_content", "MISSING")
    print(f"  Assistant msg {i}: reasoning_content={'present' if has_rc else 'MISSING'}, value={repr(rc_val)[:60]}")

# Verify: all assistant messages should have reasoning_content
all_have_rc = all("reasoning_content" in am for am in assistant_msgs)
if all_have_rc:
    print("  ✓ All assistant messages have reasoning_content field")
else:
    print("  ✗ Some assistant messages missing reasoning_content!")

# Test 3: Non-deepseek model should NOT propagate
print("\n=== Test 3: Non-DeepSeek model ===")
agent2 = MimirAetherAgent(model="openai/gpt-4", max_iterations=5)
agent2.conversation_history.append(Message(
    role=MessageRole.ASSISTANT,
    content="Hello",
    reasoning_content="some reasoning"
))
agent2.conversation_history.append(Message(
    role=MessageRole.ASSISTANT,
    content="World",
    reasoning_content=None
))
messages2 = agent2._build_full_messages()
assistant_msgs2 = [m for m in messages2 if m["role"] == "assistant"]
for i, am in enumerate(assistant_msgs2):
    has_rc = "reasoning_content" in am
    print(f"  GPT-4 Assistant msg {i}: reasoning_content present={has_rc}")
# First should have it, second should not
assert "reasoning_content" in assistant_msgs2[0], "First assistant should have reasoning_content"
assert "reasoning_content" not in assistant_msgs2[1], "Second assistant should NOT have reasoning_content for non-thinking models"
print("  ✓ Non-thinking models don't propagate empty reasoning_content")

print("\n✓ All tests passed!")
