# Task 2: 代码生成 (Code Generation)

> 权重: 20% | 满分: 20

## 任务描述

在 `/tmp/benchmark-sandbox/codegen` 下完成。

### 背景

有一个有 bug 的 Python 模块：

```python
# utils.py
def divide(a, b):
    return a / b

def safe_divide(a, b):
    if b == 0:
        return None
    return divide(a, b)
```

### 子任务

1. **修复 bug**：`safe_divide` 当 b=0 应该返回 `float('inf')` 而非 `None`（根据 issue 要求），并添加 type hints
2. **写测试**：创建 `test_utils.py`，至少 3 个 test case（正常除法、除零、负数）
3. **跑测试并确保通过**

## 评分标准

| # | 检查点 | 分值 |
|---|--------|------|
| 1 | `utils.py` — `safe_divide(1, 0)` 返回 `float('inf')` | 7 |
| 2 | `utils.py` — 有 type hints | 3 |
| 3 | `test_utils.py` 存在且 ≥3 test cases | 5 |
| 4 | 测试全部通过 | 5 |

**最高: 20 分**
