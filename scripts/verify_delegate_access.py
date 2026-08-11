#!/usr/bin/env python3
"""验证 delegate_tool.py 中 parent_agent.* 访问是否全部安全（getattr/hasattr 包裹或有属性保证）。"""
import re
import sys

src = open("tools/delegate_tool.py", encoding="utf-8").read()

# 提取每一行,检查裸访问
lines = src.split("\n")
SAFE_ATTRS = {"model", "platform", "valid_tool_names", "_client_kwargs",
              "_active_children", "_memory_manager"}
problems = []
for idx, line in enumerate(lines, 1):
    # 找 parent_agent.xxx
    for m in re.finditer(r"parent_agent\.(\w+)", line):
        attr = m.group(1)
        stripped = line.strip()
        # 裸访问 = 没有 getattr( 或 hasattr( 包裹,也不是注释
        is_comment = stripped.startswith("#")
        is_getattr = "getattr(parent_agent" in stripped
        is_hasattr = "hasattr(parent_agent" in stripped
        if not (is_comment or is_getattr or is_hasattr):
            problems.append((idx, attr, stripped))

print("=== parent_agent.* 裸访问检查 ===")
if problems:
    for idx, attr, line in problems:
        print(f"L{idx}: {attr} -> {line}")
    print(f"FAIL: {len(problems)} 处裸访问")
    sys.exit(1)
else:
    print("PASS: 无裸访问残留")
