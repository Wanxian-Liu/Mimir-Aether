#!/usr/bin/env python3
"""Task 2 评分: 代码生成"""
import sys, os, json, subprocess

WORKDIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/benchmark-sandbox"
CODE = os.path.join(WORKDIR, "codegen")

details = []
evidence = {}
score = 0.0
MAX = 20.0

utils_py = os.path.join(CODE, "utils.py")
test_py = os.path.join(CODE, "test_utils.py")

# 1. safe_divide(1, 0) 返回 inf
if os.path.exists(utils_py):
    try:
        sys.path.insert(0, CODE)
        # 动态加载
        import importlib.util
        spec = importlib.util.spec_from_file_location("utils", utils_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.safe_divide(1, 0)
        if result == float('inf'):
            score += 7
            details.append("✅ safe_divide(1,0) → inf")
        else:
            details.append(f"❌ safe_divide(1,0) → {result} (期望 inf)")
        evidence["safe_divide(1,0)"] = str(result)
        sys.path.remove(CODE)
    except Exception as e:
        details.append(f"❌ utils.py 加载/执行失败: {e}")
else:
    details.append("❌ utils.py 不存在")

# 2. type hints
if os.path.exists(utils_py):
    with open(utils_py) as f:
        src = f.read()
    has_type_hints = all(t in src for t in [': float', '-> float']) or \
                     all(t in src for t in [': int', '->']) or \
                     'Union' in src or 'Optional' in src
    if has_type_hints:
        score += 3
        details.append("✅ utils.py 有 type hints")
        evidence["type_hints"] = "yes"
    else:
        # 宽松检查：至少有 ->  返回值标注
        if '->' in src:
            score += 2
            details.append("⚠️ utils.py 有部分返回值标注")
        else:
            details.append("❌ utils.py 无 type hints")
        evidence["type_hints"] = "partial or missing"

# 3. test_utils.py 存在且 ≥3 test cases
if os.path.exists(test_py):
    with open(test_py) as f:
        test_src = f.read()
    import re
    test_funcs = re.findall(r'def test_\w+', test_src)
    count = len(test_funcs)
    if count >= 3:
        score += 5
        details.append(f"✅ test_utils.py 有 {count} 个测试用例")
    else:
        details.append(f"❌ test_utils.py 只有 {count} 个测试用例 (需要 ≥3)")
    evidence["test_count"] = count
else:
    details.append("❌ test_utils.py 不存在")

# 4. 测试通过
if os.path.exists(test_py):
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", test_py, "-v"],
            capture_output=True, text=True, timeout=30,
            cwd=CODE
        )
        if r.returncode == 0:
            score += 5
            details.append("✅ 测试全部通过")
        else:
            details.append(f"❌ 测试失败")
            evidence["test_output"] = r.stdout[-500:] + "\n" + r.stderr[-500:]
    except Exception as e:
        details.append(f"❌ 测试执行失败: {e}")

result = {"score": score, "max": MAX, "details": details, "evidence": evidence}
print(json.dumps(result, ensure_ascii=False))
