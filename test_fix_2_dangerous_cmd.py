#!/usr/bin/env python3
"""
Test Fix 2: 危险命令检测增强
验证mimicore/mini_agent/hooks.py中的_is_dangerous_command函数
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mimicore.mini_agent.hooks import DefaultBeforeToolCallHook, HookContext, ToolCall

def test_dangerous_commands():
    """测试危险命令检测"""
    hook = DefaultBeforeToolCallHook()
    context = HookContext(session_id="test")
    
    # 危险命令测试用例 (应该返回True)
    dangerous_cases = [
        ("rm -rf /", "rm with -rf"),
        ("rm  -rf /", "rm with double space and -rf"),
        ("dd if=/dev/zero of=/dev/null", "dd command"),
        ("mkfs.ext4 /dev/sda", "mkfs command"),
        ("shred /dev/sda", "shred command"),
        ("rm -r /", "rm with -r"),
        ("rm -f /", "rm with -f"),
    ]
    
    # 安全命令测试用例 (应该返回False)
    safe_cases = [
        ("ls -la", "list directory"),
        ("cat /etc/passwd", "read passwd file"),
        ('echo "hello"', "echo hello"),
        ("pwd", "print working directory"),
        ("whoami", "show current user"),
    ]
    
    print("=== Test: Dangerous Command Detection ===\n")
    
    all_passed = True
    
    print("--- Dangerous commands (should return True) ---")
    for cmd, desc in dangerous_cases:
        tool_call = ToolCall(name="exec", arguments={"command": cmd})
        result = hook._is_dangerous_command(cmd)
        status = "✅ PASS" if result == True else "❌ FAIL"
        if result != True:
            all_passed = False
        print(f"  {status}: {desc}")
        print(f"       Command: {cmd}")
        print(f"       Result: {result}\n")
    
    print("--- Safe commands (should return False) ---")
    for cmd, desc in safe_cases:
        result = hook._is_dangerous_command(cmd)
        status = "✅ PASS" if result == False else "❌ FAIL"
        if result != False:
            all_passed = False
        print(f"  {status}: {desc}")
        print(f"       Command: {cmd}")
        print(f"       Result: {result}\n")
    
    return all_passed


def test_full_hook_flow():
    """测试完整的hook流程"""
    hook = DefaultBeforeToolCallHook()
    context = HookContext(session_id="test")
    
    print("--- Full Hook Flow Test ---")
    
    # 测试危险命令被hook拦截
    dangerous_cmd = "rm -rf /"
    tool_call = ToolCall(name="exec", arguments={"command": dangerous_cmd})
    result = hook.handle(context, tool_call)
    
    if result.denied:
        print(f"✅ PASS: Dangerous command 'rm -rf /' was denied by hook")
    else:
        print(f"❌ FAIL: Dangerous command 'rm -rf /' was NOT denied by hook")
        return False
    
    # 测试安全命令被hook放行
    safe_cmd = "ls -la"
    tool_call_safe = ToolCall(name="exec", arguments={"command": safe_cmd})
    result_safe = hook.handle(context, tool_call_safe)
    
    if not result_safe.denied:
        print(f"✅ PASS: Safe command 'ls -la' was allowed by hook")
    else:
        print(f"❌ FAIL: Safe command 'ls -la' was incorrectly denied")
        return False
    
    return True


if __name__ == "__main__":
    results = []
    results.append(test_dangerous_commands())
    results.append(test_full_hook_flow())
    
    print("=" * 50)
    if all(results):
        print("✅ Fix 2: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ Fix 2: SOME TESTS FAILED")
        sys.exit(1)
