#!/usr/bin/env python3
"""A1: 对齐 tuned_thresholds override 到刘哥拍板值 0.50（50% 触发）"""
import sys
sys.path.insert(0, "/home/rayliu/src/MimirAether")

from agent.tuned_thresholds import set_override, get_tuned_float, load_overrides

entry = set_override(
    "compressor.threshold_percent",
    0.50,
    reason="A1 刘哥拍板: 上下文>50% 触发压缩 -> 压到 20% (默认 MIMIR_COMPRESS_THRESHOLD=0.50)",
)
print("set_override entry:", entry)

overrides = load_overrides()
print("current overrides:", overrides)
v = get_tuned_float("compressor.threshold_percent")
print("get_tuned_float(compressor.threshold_percent) =", v)
assert v == 0.50, f"expected 0.50, got {v}"
print("PASS: override aligned to 0.50")
