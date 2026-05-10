#!/usr/bin/env python3
"""
数据格式适配器 (Bridge) — 连接 Aggregator 与 Orchestrator

问题: 
  - Aggregator (session_aggregator.py) 输出 jsonl → data/*.jsonl
  - Orchestrator (feedback_orchestrator.py) 期望 json → aggregator_outputs/*.json
  - 字段名与结构完全不同

功能:
  1. 读 aggregator 的 jsonl 输出 (data/ 目录)
  2. 转换成 orchestrator 期望的 json 格式 + 字段映射
  3. 写到 orchestrator 的输入目录 (mimicore/evolve/feedback/aggregator_outputs/)

字段映射:
  step_aggregation.jsonl → token_level.json
    timestamp → (构造 step_id)
    tool → type (映射为 tool_call/tool_result)
    status → error (success→false, error→true)
    duration → latency_ms (s→ms)
    tokens → (token_count, 拆成多条)
    model → (丢弃，orchestrator 不关心)
    confidence → (从 status 推导: success→0.85, error→0.40)

  step_window.jsonl → step_level.json
    window_start/end → steps[] + rolling_windows[]
    error_rate → avg_error_rate
    tool_distribution → (丢弃，orchestrator 不用)
    每个窗口生成一个 step 条目

  episode_aggregation.jsonl → episode_level.json
    session_id → episode_id (前缀 ep_)
    total_calls → total_steps
    error_rate → error_rate (直接映射)
    tool_distribution → tool_distribution (直接映射)
    avg_duration → (丢弃)
    tokens → (丢弃)

用法:
  python scripts/aggregator_bridge.py

验证:
  运行后 orchestrator 能正常读取 aggregator_outputs/ 下的文件
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────

BASE = Path(__file__).resolve().parent.parent  # 项目根
DATA_DIR = BASE / "data"
ORCH_INPUT_DIR = BASE / "mimicore" / "evolve" / "feedback" / "aggregator_outputs"

# 输入文件 (aggregator 输出)
STEP_AGGR_FILE = DATA_DIR / "step_aggregation.jsonl"
STEP_WINDOW_FILE = DATA_DIR / "step_window.jsonl"
EPISODE_AGGR_FILE = DATA_DIR / "episode_aggregation.jsonl"

# 输出文件 (orchestrator 输入)
TOKEN_OUT = ORCH_INPUT_DIR / "token_level.json"
STEP_OUT = ORCH_INPUT_DIR / "step_level.json"
EPISODE_OUT = ORCH_INPUT_DIR / "episode_level.json"


# ── 工具函数 ──────────────────────────────────────────────

def read_jsonl(path: Path) -> list:
    """读取 jsonl 文件，返回字典列表"""
    if not path.exists():
        print(f"[WARN] 文件不存在: {path}")
        return []
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _status_to_error(status: str) -> bool:
    """status → error bool"""
    return status.lower() == "error"


def _status_to_confidence(status: str) -> float:
    """status → confidence 推导"""
    return 0.40 if _status_to_error(status) else 0.85


def _status_to_type(status: str) -> str:
    """tool + status → token type"""
    return "tool_retry" if _status_to_error(status) else "tool_result"


# ── 第1层: step_aggregation.jsonl → token_level.json ─────

def build_token_level(rows: list) -> dict:
    """
    将 step_aggregation.jsonl 转为 token_level.json
    
    每条原始记录变成 2-3 条 token:
      - 1条 tool_call (从原始数据推导)
      - 1条 tool_result or tool_retry (根据 status)
    按 session_id 分组，生成 step_id
    """
    # 按 session_id 分组
    by_session = defaultdict(list)
    for r in rows:
        by_session[r["session_id"]].append(r)

    all_tokens = []
    session_id = f"session_{list(by_session.keys())[0] if by_session else 'unknown'}"

    for sid, session_rows in by_session.items():
        for idx, r in enumerate(session_rows):
            step_id = f"step_{idx + 1:03d}"
            status = r.get("status", "success")
            duration_s = r.get("duration", 1.0)
            latency_ms = int(duration_s * 1000)
            is_error = _status_to_error(status)

            # tool_call token
            all_tokens.append({
                "step_id": step_id,
                "token_idx": 0,
                "type": "tool_call",
                "confidence": 0.85,
                "error": False,
                "latency_ms": max(50, latency_ms // 3),
            })

            # result/retry token
            all_tokens.append({
                "step_id": step_id,
                "token_idx": 1,
                "type": _status_to_type(status),
                "confidence": _status_to_confidence(status),
                "error": is_error,
                "latency_ms": latency_ms,
            })

            # 如果是 error，加一条 tool_retry 或 tool_abort
            if is_error:
                all_tokens.append({
                    "step_id": step_id,
                    "token_idx": 2,
                    "type": "tool_retry",
                    "confidence": _status_to_confidence(status),
                    "error": True,
                    "error_type": "tool_error",
                    "latency_ms": latency_ms,
                })

    total = len(all_tokens)
    errors = sum(1 for t in all_tokens if t.get("error"))
    confs = [t["confidence"] for t in all_tokens]
    latencies = [t["latency_ms"] for t in all_tokens]

    return {
        "session_id": session_id,
        "aggregator": "token_level",
        "generated_at": "2026-05-10T00:00:00Z",
        "tokens": all_tokens,
        "summary": {
            "total_tokens": total,
            "error_tokens": errors,
            "error_rate": round(errors / total, 2) if total > 0 else 0.0,
            "avg_confidence": round(sum(confs) / len(confs), 2) if confs else 0.0,
            "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        },
    }


# ── 第2层: step_window.jsonl → step_level.json ───────────

def build_step_level(rows: list) -> dict:
    """
    将 step_window.jsonl 转为 step_level.json

    step_window 每条是滑动窗口聚合结果。
    我们需要：
      - 从窗口数据中提取 steps[]（每个窗口产生一个 step）
      - 生成 rolling_windows[]（连续窗口的 error 趋势）
    """
    if not rows:
        return {
            "session_id": "session_unknown",
            "aggregator": "step_level",
            "generated_at": "2026-05-10T00:00:00Z",
            "window_size": 0,
            "steps": [],
            "rolling_windows": [],
            "summary": {
                "total_steps": 0,
                "total_error_steps": 0,
                "overall_error_rate": 0.0,
                "avg_confidence": 0.0,
                "avg_latency_ms": 0,
            },
        }

    session_id = rows[0].get("session_ids_in_window", ["unknown"])[0]

    # 每个窗口生成一个 step
    steps = []
    for idx, w in enumerate(rows):
        steps.append({
            "step_id": f"step_{idx + 1:03d}",
            "window_idx": idx,
            "token_count": w.get("total_tokens", 0),
            "error_count": w.get("error_count", 0),
            "error_rate": w.get("error_rate", 0.0),
            "avg_confidence": max(0.01, 1.0 - w.get("error_rate", 0.0)),
            "avg_latency_ms": int(w.get("avg_duration", 1.0) * 1000),
            "tool": list(w.get("tool_distribution", {}).keys())[0] if w.get("tool_distribution") else "unknown",
        })

    # 生成 rolling_windows (窗口大小=3)
    rolling_windows = []
    for i in range(len(rows) - 2):
        window = rows[i:i + 3]
        step_ids = [f"step_{i + j + 1:03d}" for j in range(3)]
        avg_err = sum(w.get("error_rate", 0.0) for w in window) / 3

        # trend: 比较前后两半
        if len(window) >= 2:
            first_half = sum(window[0].get("error_rate", 0.0) for _ in [0])
            second_half = sum(window[-1].get("error_rate", 0.0) for _ in [0])
            if second_half > first_half + 0.05:
                trend = "up"
            elif second_half < first_half - 0.05:
                trend = "down"
            else:
                trend = "flat"
        else:
            trend = "flat"

        rolling_windows.append({
            "window_start": i,
            "window_end": i + 2,
            "steps": step_ids,
            "avg_error_rate": round(avg_err, 2),
            "trend": trend,
        })

    total_steps = len(steps)
    total_errors = sum(s["error_count"] for s in steps)
    error_rates = [s["error_rate"] for s in steps]
    latencies = [s["avg_latency_ms"] for s in steps]

    return {
        "session_id": session_id,
        "aggregator": "step_level",
        "generated_at": "2026-05-10T00:00:00Z",
        "window_size": 3,
        "steps": steps,
        "rolling_windows": rolling_windows,
        "summary": {
            "total_steps": total_steps,
            "total_error_steps": total_errors,
            "overall_error_rate": round(sum(error_rates) / len(error_rates), 2) if error_rates else 0.0,
            "avg_confidence": round(sum(s["avg_confidence"] for s in steps) / len(steps), 2) if steps else 0.0,
            "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        },
    }


# ── 第3层: episode_aggregation.jsonl → episode_level.json ─

def build_episode_level(rows: list) -> dict:
    """
    将 episode_aggregation.jsonl 转为 episode_level.json

    字段映射：
      session_id → episode_id (前缀 ep_)
      total_calls → total_steps
      error_rate → error_rate
      tool_distribution → tool_distribution
      avg_duration → (丢弃)
      total_tokens → (丢弃)
    """
    episodes = []
    for idx, r in enumerate(rows):
        episodes.append({
            "episode_id": f"ep_{idx + 1:03d}",
            "session_ids": [r.get("session_id", f"session_{idx + 1:03d}")],
            "start_time": r.get("start_time", "2026-05-10T00:00:00Z"),
            "end_time": r.get("end_time", "2026-05-10T00:00:00Z"),
            "tool_distribution": r.get("tool_distribution", {}),
            "total_steps": r.get("total_calls", 0),
            "error_rate": r.get("error_rate", 0.0),
            "avg_confidence": max(0.01, 1.0 - r.get("error_rate", 0.0)),
        })

    total_episodes = len(episodes)
    total_sessions = len(set(e["session_ids"][0] for e in episodes))
    total_steps = sum(e["total_steps"] for e in episodes)
    error_rates = [e["error_rate"] for e in episodes]
    confidences = [e["avg_confidence"] for e in episodes]

    return {
        "session_id": "session_evolve_001",
        "aggregator": "episode_level",
        "generated_at": "2026-05-10T00:00:00Z",
        "episodes": episodes,
        "summary": {
            "total_episodes": total_episodes,
            "total_sessions": total_sessions,
            "total_steps_across_episodes": total_steps,
            "overall_error_rate": round(sum(error_rates) / len(error_rates), 2) if error_rates else 0.0,
            "overall_avg_confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
        },
    }


# ── 主流程 ────────────────────────────────────────────────

def run_bridge() -> dict:
    """运行 bridge，返回各层结果"""
    print("=" * 60)
    print("  数据格式适配器 (Aggregator → Orchestrator Bridge)")
    print("=" * 60)

    # 读 aggregator 输出
    step_rows = read_jsonl(STEP_AGGR_FILE)
    window_rows = read_jsonl(STEP_WINDOW_FILE)
    episode_rows = read_jsonl(EPISODE_AGGR_FILE)

    print(f"\n📖 读取 aggregator 输出:")
    print(f"   ├─ step_aggregation.jsonl:    {len(step_rows)} 条")
    print(f"   ├─ step_window.jsonl:         {len(window_rows)} 条")
    print(f"   └─ episode_aggregation.jsonl: {len(episode_rows)} 条")

    # 转换
    token_data = build_token_level(step_rows)
    step_data = build_step_level(window_rows)
    episode_data = build_episode_level(episode_rows)

    print(f"\n🔄 转换完成:")
    print(f"   ├─ token_level.json:    {len(token_data['tokens'])} tokens")
    print(f"   ├─ step_level.json:     {len(step_data['steps'])} steps, {len(step_data['rolling_windows'])} windows")
    print(f"   └─ episode_level.json:  {len(episode_data['episodes'])} episodes")

    # 写入 orchestrator 输入目录
    ORCH_INPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(TOKEN_OUT, "w") as f:
        json.dump(token_data, f, indent=2, ensure_ascii=False)
    with open(STEP_OUT, "w") as f:
        json.dump(step_data, f, indent=2, ensure_ascii=False)
    with open(EPISODE_OUT, "w") as f:
        json.dump(episode_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 写入 orchestrator 输入目录: {ORCH_INPUT_DIR}")
    print(f"   ├─ {TOKEN_OUT.name}")
    print(f"   ├─ {STEP_OUT.name}")
    print(f"   └─ {EPISODE_OUT.name}")

    return {
        "token_data": token_data,
        "step_data": step_data,
        "episode_data": episode_data,
    }


# ── 入口 ──────────────────────────────────────────────────

if __name__ == "__main__":
    run_bridge()
