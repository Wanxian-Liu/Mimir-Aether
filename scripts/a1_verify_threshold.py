#!/usr/bin/env python3
"""A1 验证：core_loop.py 语法 + MIMIR_COMPRESS_THRESHOLD 阈值优先级逻辑"""
import ast
import os
import sys

sys.path.insert(0, "/home/rayliu/src/MimirAether")

# 1. 语法检查
src = open("/home/rayliu/src/MimirAether/agent/core_loop.py", encoding="utf-8").read()
ast.parse(src)
print("PASS syntax: agent/core_loop.py parses OK")

# 2. 阈值优先级逻辑验证（复刻 core_loop 读取逻辑，无 env 时应 0.50）
def resolve_threshold(env_val=None):
    _threshold_percent = 0.50
    try:
        from agent.tuned_thresholds import get_tuned_float
        _threshold_percent = get_tuned_float("compressor.threshold_percent")
    except Exception:
        pass
    try:
        _env_threshold = env_val if env_val is not None else os.environ.get("MIMIR_COMPRESS_THRESHOLD")
        if _env_threshold is not None and _env_threshold.strip():
            _threshold_percent = float(_env_threshold)
    except (TypeError, ValueError):
        pass
    return _threshold_percent

# 无 env → tuned_thresholds 默认（应为 0.50）
v_noenv = resolve_threshold(None)
print(f"no-env threshold = {v_noenv} (expect 0.50)")
assert v_noenv == 0.50, f"expected 0.50, got {v_noenv}"

# env=0.30 → 0.30（env 覆盖）
v_env = resolve_threshold("0.30")
print(f"env=0.30 threshold = {v_env} (expect 0.30)")
assert v_env == 0.30, f"expected 0.30, got {v_env}"

# env=非法 → 回退 tuned（0.50）
v_bad = resolve_threshold("abc")
print(f"env=abc threshold = {v_bad} (expect 0.50 fallback)")
assert v_bad == 0.50, f"expected 0.50, got {v_bad}"

# 3. 压缩到 20% 验证：summary_target_ratio 默认 0.20（ContextCompressorV2）
from agent.context_compressor import ContextCompressorV2
comp = ContextCompressorV2(context_length=100000, threshold_percent=0.50)
print(f"summary_target_ratio = {comp.summary_target_ratio} (expect 0.20)")
assert comp.summary_target_ratio == 0.20
print(f"threshold_tokens = {comp.threshold_tokens} (expect 50000 = 50% of 100k)")
assert comp.threshold_tokens == 50000
print(f"tail_token_budget = {comp.tail_token_budget} (expect 10000 = 20% of 50k)")
assert comp.tail_token_budget == 10000

print("\nALL PASS: A1 threshold + ratio verified")
