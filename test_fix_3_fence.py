#!/usr/bin/env python3
"""
Test Fix 3: fence_checkpoint参数验证
验证mimicore/gateway/gateway.py中的fence_checkpoint函数
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mimicore.gateway.gateway import fence_checkpoint

def test_fence_checkpoint():
    """测试围栏检查点参数验证"""
    print("=== Test: fence_checkpoint Parameter Validation ===\n")
    
    all_passed = True
    
    # 测试1: 非法operation（如"hack"）应返回 {"allowed": False}
    print("--- Test 1: Invalid operation 'hack' ---")
    result = fence_checkpoint("/tmp/test.txt", "hack", "testuser")
    print(f"  Result: {result}")
    if result.get("allowed") == False and "Invalid operation" in result.get("reason", ""):
        print("  ✅ PASS: Invalid operation correctly rejected\n")
    else:
        print("  ❌ FAIL: Invalid operation not rejected\n")
        all_passed = False
    
    # 测试2: 非法user格式（如"user; rm -rf"）应返回 {"allowed": False}
    print("--- Test 2: Invalid user format 'user; rm -rf' ---")
    result = fence_checkpoint("/tmp/test.txt", "read", "user; rm -rf")
    print(f"  Result: {result}")
    if result.get("allowed") == False and "Invalid user format" in result.get("reason", ""):
        print("  ✅ PASS: Invalid user format correctly rejected\n")
    else:
        print("  ❌ FAIL: Invalid user format not rejected\n")
        all_passed = False
    
    # 测试3: 合法参数应正常通过 (fence disabled状态下返回allowed=True)
    print("--- Test 3: Valid parameters ---")
    result = fence_checkpoint("/tmp/test.txt", "read", "valid_user_123")
    print(f"  Result: {result}")
    if result.get("allowed") == True:
        print("  ✅ PASS: Valid parameters correctly allowed\n")
    else:
        print("  ❌ FAIL: Valid parameters incorrectly rejected\n")
        all_passed = False
    
    # 测试4: 另一个合法operation - "write"
    print("--- Test 4: Valid operation 'write' ---")
    result = fence_checkpoint("/tmp/test.txt", "write", "admin_user")
    print(f"  Result: {result}")
    if result.get("allowed") == True:
        print("  ✅ PASS: Valid operation 'write' correctly allowed\n")
    else:
        print("  ❌ FAIL: Valid operation 'write' incorrectly rejected\n")
        all_passed = False
    
    # 测试5: 另一个合法operation - "delete"
    print("--- Test 5: Valid operation 'delete' ---")
    result = fence_checkpoint("/tmp/test.txt", "delete", "admin")
    print(f"  Result: {result}")
    if result.get("allowed") == True:
        print("  ✅ PASS: Valid operation 'delete' correctly allowed\n")
    else:
        print("  ❌ FAIL: Valid operation 'delete' incorrectly rejected\n")
        all_passed = False
    
    # 测试6: 测试cleanup operation
    print("--- Test 6: Valid operation 'cleanup' ---")
    result = fence_checkpoint("/tmp/test.txt", "cleanup", "system")
    print(f"  Result: {result}")
    if result.get("allowed") == True:
        print("  ✅ PASS: Valid operation 'cleanup' correctly allowed\n")
    else:
        print("  ❌ FAIL: Valid operation 'cleanup' incorrectly rejected\n")
        all_passed = False
    
    # 测试7: 测试check operation
    print("--- Test 7: Valid operation 'check' ---")
    result = fence_checkpoint("/tmp/test.txt", "check", "auditor")
    print(f"  Result: {result}")
    if result.get("allowed") == True:
        print("  ✅ PASS: Valid operation 'check' correctly allowed\n")
    else:
        print("  ❌ FAIL: Valid operation 'check' incorrectly rejected\n")
        all_passed = False
    
    return all_passed


if __name__ == "__main__":
    result = test_fence_checkpoint()
    
    print("=" * 50)
    if result:
        print("✅ Fix 3: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ Fix 3: SOME TESTS FAILED")
        sys.exit(1)
