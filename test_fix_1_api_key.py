#!/usr/bin/env python3
"""
Test Fix 1: API Key环境变量读取
验证run_service.py在缺少DEEPSEEK_API_KEY时的错误处理
"""
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent


def test_missing_api_key():
    """测试：移除环境变量运行，应报清晰错误"""
    # 创建一个临时脚本来测试
    test_script = """
import sys
import os
# 清除环境变量
if 'DEEPSEEK_API_KEY' in os.environ:
    del os.environ['DEEPSEEK_API_KEY']

# 重新导入（会触发错误）
sys.path.insert(0, '.')
try:
    import run_service
except ValueError as e:
    print("SUCCESS:", str(e))
except SystemExit as e:
    print("FAIL: SystemExit raised")
except Exception as e:
    print("FAIL: Wrong exception:", type(e).__name__, str(e))
"""
    
    # 写入临时测试文件
    with open('/tmp/test_api_key.py', 'w') as f:
        f.write(test_script)
    
    result = subprocess.run(
        [sys.executable, '/tmp/test_api_key.py'],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    
    print("=== Test 1: Missing API Key ===")
    print(f"stdout: {result.stdout}")
    print(f"stderr: {result.stderr}")
    
    if "SUCCESS" in result.stdout and "DEEPSEEK_API_KEY" in result.stdout:
        print("✅ PASS: 缺少API Key时抛出清晰错误\n")
        return True
    else:
        print("❌ FAIL: 错误处理不正确\n")
        return False


def test_with_api_key():
    """测试：设置环境变量后应正常"""
    test_script = """
import os
os.environ['DEEPSEEK_API_KEY'] = 'test_key_12345'

sys.path.insert(0, '.')
try:
    import run_service
    # 检查api_key是否被正确读取
    if run_service.api_key == 'test_key_12345':
        print("SUCCESS: API Key correctly loaded")
    else:
        print("FAIL: API Key not loaded correctly")
except Exception as e:
    print("FAIL:", type(e).__name__, str(e))
"""
    
    with open('/tmp/test_api_key_with_env.py', 'w') as f:
        f.write(test_script)
    
    result = subprocess.run(
        [sys.executable, '/tmp/test_api_key_with_env.py'],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    
    print("=== Test 2: With API Key ===")
    print(f"stdout: {result.stdout}")
    print(f"stderr: {result.stderr}")
    
    if "SUCCESS" in result.stdout:
        print("✅ PASS: 设置API Key后正常工作\n")
        return True
    else:
        print("❌ FAIL: 环境变量读取失败\n")
        return False


if __name__ == "__main__":
    results = []
    results.append(test_missing_api_key())
    results.append(test_with_api_key())
    
    print("=" * 50)
    if all(results):
        print("✅ Fix 1: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ Fix 1: SOME TESTS FAILED")
        sys.exit(1)
