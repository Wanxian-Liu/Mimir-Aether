"""
格式适配器：aggregator jsonl → orchestrator json

读取 data/*.jsonl (aggregator 输出)，转换为 orchestrator 期望的 JSON 格式，
写入 mimicore/evolve/feedback/aggregator_outputs/。

Orchestrator 期望格式 (feedback_orchestrator.py):
  decide_token_level(data): data["tokens"] → list of {step_id, token_idx, type, confidence, error, latency_ms, ...}
  decide_step_level(data):  data["rolling_windows"] → list of {window_start, window_end, steps, avg_error_rate, trend, ...}
  decide_episode_level(data): data["episodes"] → list of {episode_id, session_ids, tool_distribution, total_steps, error_rate, ...}

字段映射:
  step_aggregation.jsonl → token_level.json
    timestamp → step_id (构造)
    tool → type (tool_call / tool_result / tool_retry)
    status → error (success→false, error→true)
    duration → latency_ms (s→ms)
    confidence → 从 status 推导: success→0.85, error→0.40

  step_window.jsonl → step_level.json
    每个窗口生成一个 step 条目
    error_rate → avg_error_rate
    连续窗口生成 rolling_windows[] (窗口大小=3)

  episode_aggregation.jsonl → episode_level.json
    session_id → episode_id (前缀 ep_)
    total_calls → total_steps
    error_rate → error_rate (直接映射)
    tool_distribution → tool_distribution (直接映射)
"""

import json
import os
from collections import defaultdict
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "mimicore" / "evolve" / "feedback" / "aggregator_outputs"

STEP_IN = DATA_DIR / "step_aggregation.jsonl"
WINDOW_IN = DATA_DIR / "step_window.jsonl"
EPISODE_IN = DATA_DIR / "episode_aggregation.jsonl"

TOKEN_OUT = OUT_DIR / "token_level.json"
STEP_OUT = OUT_DIR / "step_level.json"
EPISODE_OUT = OUT_DIR / "episode_level.json"


# ── 工具函数 ──────────────────────────────────────────────

def load_jsonl(path):
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def status_to_error(status):
    return status.lower() == "error"


def status_to_confidence(status):
    return 0.40 if status_to_error(status) else 0.85


def status_to_type(status):
    return "tool_retry" if status_to_error(status) else "tool_result"


# ── 第1层: step_aggregation.jsonl → token_level.json ─────

def build_token_level(rows):
    """每条原始记录 → 2-3 条 token (tool_call + result/retry)"""
    by_session = defaultdict(list)
    for r in rows:
        by_session[r["session_id"]].append(r)

    all_tokens = []
    first_sid = list(by_session.keys())[0] if by_session else "unknown"
    session_id = f"session_{first_sid}"

    for sid, session_rows in by_session.items():
        for idx, r in enumerate(session_rows):
            step_id = f"step_{idx + 1:03d}"
            status = r.get("status", "success")
            duration_s = r.get("duration", 1.0)
            latency_ms = int(duration_s * 1000)
            is_error = status_to_error(status)

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
                "type": status_to_type(status),
                "confidence": status_to_confidence(status),
                "error": is_error,
                "latency_ms": latency_ms,
            })

            # error → extra retry token
            if is_error:
                all_tokens.append({
                    "step_id": step_id,
                    "token_idx": 2,
                    "type": "tool_retry",
                    "confidence": status_to_confidence(status),
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

def build_step_level(rows):
    """每个窗口 → step, 连续3窗 → rolling_window"""
    if not rows:
        return {
            "session_id": "session_unknown", "aggregator": "step_level",
            "generated_at": "2026-05-10T00:00:00Z", "window_size": 0,
            "steps": [], "rolling_windows": [],
            "summary": {"total_steps": 0, "total_error_steps": 0,
                        "overall_error_rate": 0.0, "avg_confidence": 0.0, "avg_latency_ms": 0},
        }

    session_id = rows[0].get("session_ids_in_window", ["unknown"])[0]

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

    rolling_windows = []
    for i in range(len(rows) - 2):
        window = rows[i:i + 3]
        step_ids = [f"step_{i + j + 1:03d}" for j in range(3)]
        avg_err = sum(w.get("error_rate", 0.0) for w in window) / 3

        first_err = window[0].get("error_rate", 0.0)
        last_err = window[-1].get("error_rate", 0.0)
        if last_err > first_err + 0.05:
            trend = "up"
        elif last_err < first_err - 0.05:
            trend = "down"
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

def build_episode_level(rows):
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

def run_bridge():
    print("=" * 60)
    print("  format_bridge.py — Aggregator → Orchestrator")
    print("=" * 60)

    step_rows = load_jsonl(STEP_IN)
    window_rows = load_jsonl(WINDOW_IN)
    episode_rows = load_jsonl(EPISODE_IN)

    print(f"\n读取 aggregator 输出:")
    print(f"  step_aggregation.jsonl:    {len(step_rows)} 条")
    print(f"  step_window.jsonl:         {len(window_rows)} 条")
    print(f"  episode_aggregation.jsonl: {len(episode_rows)} 条")

    token_data = build_token_level(step_rows)
    step_data = build_step_level(window_rows)
    episode_data = build_episode_level(episode_rows)

    print(f"\n转换完成:")
    print(f"  token_level.json:    {len(token_data['tokens'])} tokens")
    print(f"  step_level.json:     {len(step_data['steps'])} steps, {len(step_data['rolling_windows'])} windows")
    print(f"  episode_level.json:  {len(episode_data['episodes'])} episodes")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_OUT, "w") as f:
        json.dump(token_data, f, indent=2, ensure_ascii=False)
    with open(STEP_OUT, "w") as f:
        json.dump(step_data, f, indent=2, ensure_ascii=False)
    with open(EPISODE_OUT, "w") as f:
        json.dump(episode_data, f, indent=2, ensure_ascii=False)

    print(f"\n写入 {OUT_DIR}/")
    print(f"  token_level.json")
    print(f"  step_level.json")
    print(f"  episode_level.json")

    return token_data, step_data, episode_data


if __name__ == "__main__":
    run_bridge()
