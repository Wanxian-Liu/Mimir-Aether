#!/usr/bin/env python3
"""
会话日志三层聚合器

输入: data/raw_session_logs.jsonl
输出:
  - data/step_aggregation.jsonl    (token级/每行)
  - data/step_window.jsonl         (step级/50条滑动窗口)
  - data/episode_aggregation.jsonl (episode级/会话边界)

纯Python，无外部依赖。
"""

import json
import os
from collections import defaultdict, deque
from statistics import mean

# ── 路径 ──────────────────────────────────────────────
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(BASE, "data", "raw_session_logs.jsonl")
OUT_DIR = os.path.join(BASE, "data")

os.makedirs(OUT_DIR, exist_ok=True)

# ── 读取原始数据 ───────────────────────────────────────
rows = []
with open(INPUT) as f:
    for line in f:
        line = line.strip()
        if line:
            rows.append(json.loads(line))

print(f"[聚合器] 读取 {len(rows)} 条原始日志")

# ════════════════════════════════════════════════════════
# 第1层: Token级聚合 (每行一条)
# ════════════════════════════════════════════════════════
with open(os.path.join(OUT_DIR, "step_aggregation.jsonl"), "w") as f:
    for r in rows:
        out = {
            "level": "token",
            "timestamp": r["timestamp"],
            "session_id": r["session_id"],
            "tool": r["tool"],
            "duration": r["duration"],
            "status": r["status"],
            "tokens": r.get("tokens", 0),
            "model": r.get("model", "unknown"),
        }
        f.write(json.dumps(out) + "\n")

print("[聚合器] 第1层完成 → step_aggregation.jsonl")

# ════════════════════════════════════════════════════════
# 第2层: Step级聚合 (50条滑动窗口)
# ════════════════════════════════════════════════════════
WINDOW_SIZE = 50
window = deque()
window_results = []

for i, r in enumerate(rows):
    window.append(r)
    if len(window) > WINDOW_SIZE:
        window.popleft()

    # 每满一个窗口输出一次 (前49条不足窗口时也输出)
    durations = [w["duration"] for w in window]
    statuses = [w["status"] for w in window]
    tools_in_window = [w["tool"] for w in window]

    error_count = sum(1 for s in statuses if s == "error")
    tool_dist = defaultdict(int)
    for t in tools_in_window:
        tool_dist[t] += 1

    out = {
        "level": "step_window",
        "window_start": i - len(window) + 1,
        "window_end": i,
        "window_size": len(window),
        "avg_duration": round(mean(durations), 4),
        "min_duration": round(min(durations), 4),
        "max_duration": round(max(durations), 4),
        "error_rate": round(error_count / len(window), 4),
        "error_count": error_count,
        "total_tokens": sum(w.get("tokens", 0) for w in window),
        "tool_distribution": dict(tool_dist),
        "unique_tools": len(tool_dist),
        "session_ids_in_window": list(set(w["session_id"] for w in window)),
    }
    window_results.append(out)

with open(os.path.join(OUT_DIR, "step_window.jsonl"), "w") as f:
    for out in window_results:
        f.write(json.dumps(out) + "\n")

print(f"[聚合器] 第2层完成 → step_window.jsonl ({len(window_results)} 窗口)")

# ════════════════════════════════════════════════════════
# 第3层: Episode级聚合 (按会话边界)
# ════════════════════════════════════════════════════════
episodes = defaultdict(list)
for r in rows:
    episodes[r["session_id"]].append(r)

episode_results = []
for sid, session_rows in sorted(episodes.items()):
    durations = [r["duration"] for r in session_rows]
    statuses = [r["status"] for r in session_rows]
    tools_in_ep = [r["tool"] for r in session_rows]
    error_count = sum(1 for s in statuses if s == "error")

    tool_dist = defaultdict(int)
    for t in tools_in_ep:
        tool_dist[t] += 1

    timestamps = [r["timestamp"] for r in session_rows]

    out = {
        "level": "episode",
        "session_id": sid,
        "total_calls": len(session_rows),
        "avg_duration": round(mean(durations), 4),
        "min_duration": round(min(durations), 4),
        "max_duration": round(max(durations), 4),
        "error_rate": round(error_count / len(session_rows), 4),
        "error_count": error_count,
        "total_tokens": sum(r.get("tokens", 0) for r in session_rows),
        "tool_distribution": dict(tool_dist),
        "unique_tools": len(tool_dist),
        "start_time": timestamps[0],
        "end_time": timestamps[-1],
        "models_used": list(set(r.get("model", "unknown") for r in session_rows)),
    }
    episode_results.append(out)

with open(os.path.join(OUT_DIR, "episode_aggregation.jsonl"), "w") as f:
    for out in episode_results:
        f.write(json.dumps(out) + "\n")

print(f"[聚合器] 第3层完成 → episode_aggregation.jsonl ({len(episode_results)} 个会话)")

# ── 快速摘要 ───────────────────────────────────────────
print("\n═══ 聚合摘要 ═══")
print(f"  原始行数: {len(rows)}")
print(f"  会话数:   {len(episode_results)}")
print(f"  滑动窗口: {len(window_results)} 个 (窗口大小={WINDOW_SIZE})")
print(f"  工具总数: {len(set(r['tool'] for r in rows))} 种")
print(f"  总错误:   {sum(1 for r in rows if r['status'] == 'error')}")
print(f"  总 tokens: {sum(r.get('tokens', 0) for r in rows)}")
