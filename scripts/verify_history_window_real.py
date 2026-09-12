#!/usr/bin/env python3
"""阶段2验证(真实数据): 历史窗口化前后对比 (Mimir历史膨胀修复 A方案)

用 ~/.mimiraether/data/sessions/ 下的真实 transcript 模拟 load_transcript,
应用 agent_mixin.py 的窗口化逻辑, 对比:
  1. 消息数: 全量 vs 窗口化
  2. 字符数: 全量 vs 窗口化 (token 粗估 = chars/4)
  3. 窗口首条不是孤立 tool 消息 (边界安全)
"""
import json
import os
import sys

def load_transcript(path):
    """模拟 session_store.load_transcript: JSONL 每行一个消息 dict"""
    msgs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(m, dict) and "role" in m:
                msgs.append(m)
    return msgs

def apply_window(history, window_size):
    """与 agent_mixin.py 窗口化逻辑同构"""
    if window_size > 0 and len(history) > window_size:
        _dropped = len(history) - window_size
        window = history[-window_size:]
        _i = _dropped
        while window and window[0].get("role") == "tool" and _i > 0:
            _i -= 1
            window.insert(0, history[_i])
        return window, _dropped
    return history, 0

def est_tokens(msgs):
    """与 model_metadata.estimate_messages_tokens_rough 同构: (sum(len(str(msg)))+3)//4"""
    total = sum(len(str(m)) + 3 for m in msgs)
    return total // 4

SESSIONS_DIR = os.path.expanduser("~/.mimiraether/data/sessions")
WINDOW = 50

# 找最大的 3 个 transcript
candidates = []
for fname in sorted(os.listdir(SESSIONS_DIR)):
    if fname.endswith(".jsonl"):
        p = os.path.join(SESSIONS_DIR, fname)
        candidates.append((os.path.getsize(p), p))
candidates.sort(reverse=True)
candidates = candidates[:3]

print(f"窗口大小: {WINDOW} | 样本: 最大的 {len(candidates)} 个真实 transcript\n")
print(f"{'文件':<32} {'全量':>6} {'窗口':>6} {'丢弃':>6} {'全量tok':>10} {'窗口tok':>10} {'降幅':>7} {'首条安全':>6}")
print("-" * 100)

for size, path in candidates:
    h = load_transcript(path)
    w, d = apply_window(h, WINDOW)
    full_tok = est_tokens(h)
    win_tok = est_tokens(w)
    pct = (1 - win_tok / full_tok) * 100 if full_tok else 0
    first_safe = "✅" if not w or w[0].get("role") != "tool" else "❌"
    fname = os.path.basename(path)
    print(f"{fname:<32} {len(h):>6} {len(w):>6} {d:>6} {full_tok:>10,} {win_tok:>10,} {pct:>6.1f}% {first_safe:>6}")
    # 详细: 首条信息
    if w:
        first = w[0]
        print(f"    └─ 窗口首条: role={first.get('role')!r} content={str(first.get('content'))[:60]!r}")

# 汇总
print("\n汇总(3个大会话平均):")
tot_full = tot_win = 0
for size, path in candidates:
    h = load_transcript(path)
    w, d = apply_window(h, WINDOW)
    tot_full += est_tokens(h)
    tot_win += est_tokens(w)
avg_pct = (1 - tot_win / tot_full) * 100 if tot_full else 0
print(f"  全量总 token 估算: {tot_full:,} → 窗口化: {tot_win:,} (平均降 {avg_pct:.1f}%)")
print(f"  结论: 每轮喂模型的 token 从全量级降至 ~50条窗口级")
