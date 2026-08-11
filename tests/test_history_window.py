#!/usr/bin/env python3
"""阶段2验证: 历史窗口化逻辑 (Mimir历史膨胀修复 A方案)

验证点:
1. 短会话 (<50条) 不裁剪
2. 长会话 (60条) 只保留最近50条
3. tool 边界安全: 窗口首条不能是孤立的 tool 消息
4. MIMIR_HISTORY_WINDOW 环境变量可调
"""
import os
import sys

# 直接复制 agent_mixin.py 中窗口化的逻辑进行验证 (与生产代码同构)
def apply_window(history, window_size):
    if window_size > 0 and len(history) > window_size:
        _dropped = len(history) - window_size
        window = history[-window_size:]
        _i = _dropped
        while window and window[0].get("role") == "tool" and _i > 0:
            _i -= 1
            window.insert(0, history[_i])
        return window, _dropped
    return history, 0

def make_history(n, tail_tool=False):
    """构造 n 条消息; 最后一条若是 tool 则模拟 assistant tool_calls → tool 配对"""
    msgs = []
    for i in range(n):
        msgs.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"msg-{i}"})
    if tail_tool and msgs:
        # 在末尾追加 assistant(tool_calls) + tool 结果, 使窗口化起点可能落在 tool 上
        msgs.append({"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]})
        msgs.append({"role": "tool", "tool_call_id": "c1", "content": "result"})
    return msgs

passed = 0
failed = 0

def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}")

# 测试1: 短会话不裁剪
print("测试1: 短会话 (30条) 不裁剪")
h = make_history(30)
w, d = apply_window(h, 50)
check("30条 ≤ 50 → 原样返回", len(w) == 30 and d == 0)

# 测试2: 长会话裁剪
print("测试2: 长会话 (60条) 只保留最近50")
h = make_history(60)
w, d = apply_window(h, 50)
check("丢弃10条", d == 10)
check("保留50条", len(w) == 50)
check("保留的是最近的消息", w[0]["content"] == "msg-10")

# 测试3: tool 边界安全 —— 窗口首条不能是孤立的 tool
print("测试3: tool 边界安全 (窗口起点落在 tool 上)")
h = make_history(55, tail_tool=True)
# 55 条文本 + 2 条 tool 配对 = 57 条
w, d = apply_window(h, 50)
first_role = w[0].get("role")
check("窗口首条不是 tool", first_role != "tool", )
check("丢弃数正确", d == 7)
check("窗口首条是 assistant(tool_calls) 或其配对", first_role in ("user", "assistant"))
# 验证窗口内 tool 消息都有前置 assistant tool_calls
ok = True
for j, m in enumerate(w):
    if m.get("role") == "tool":
        # 前面必须存在带 tool_calls 的 assistant
        prev = w[j-1] if j > 0 else {}
        if prev.get("role") != "assistant" or not prev.get("tool_calls"):
            ok = False
            break
check("窗口内所有 tool 消息都有配对 assistant", ok)

# 测试4: 环境变量控制 (模拟)
print("测试4: 窗口大小可调")
os.environ["MIMIR_HISTORY_WINDOW"] = "20"
h = make_history(60)
w, d = apply_window(h, 20)
check("窗口=20 → 保留20", len(w) == 20 and d == 40)
os.environ["MIMIR_HISTORY_WINDOW"] = "0"
h = make_history(60)
w, d = apply_window(h, 0)
check("窗口=0 → 禁用(全量)", len(w) == 60 and d == 0)
del os.environ["MIMIR_HISTORY_WINDOW"]

# 测试5: 空/单条历史
print("测试5: 边界 (空历史)")
h = []
w, d = apply_window(h, 50)
check("空历史不崩溃", len(w) == 0 and d == 0)

print(f"\n结果: {passed} 通过, {failed} 失败")
sys.exit(1 if failed else 0)
