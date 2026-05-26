# P2-LONG-IQEVO — Wave 5 结案（IQ-EVO-26）

> **日期**：2026-05-26  
> **母任务**：backlog **§15 Wave 5** · 真源 [`p2-long-iqevo-wave5.md`](p2-long-iqevo-wave5.md)  
> **验证**：`./run_ralph_tier0.sh` **441+2**（commit `e586a03`）

## Wave 5 交付（IQ-EVO-20～26）

| # | 要求 | 证据 |
|---|------|------|
| 1 | ExperienceBuffer | `agent/experience_buffer.py` · 128 events summarized |
| 2 | tuned_thresholds + AutoTuner | `tuned_thresholds.json` · `tune_audit.jsonl` |
| 3 | 三处消费方接线 | `core_loop` · `degeneration_guard` · `tool_quality` / prompt |
| 4 | rubric 复评 #4 | [`iq-scoring-rubric.md`](iq-scoring-rubric.md) **4.7/10** |
| 5 | 生产 env | `MIMIR_FEEDBACK_COLLECTOR=1` · `MIMIR_AUTO_TUNER=1` |

## 运维冒烟（Cursor · 2026-05-26）

```text
experience: tool_failure_count=2, pipeline_close_count=63, event_count=128
tune_changes: compressor.threshold_percent 0.50→0.45; tool_quality.degraded_threshold 0.50→0.45
files: ~/.mimiraether/data/tuned_thresholds.json, tune_audit.jsonl
Gateway PID 367984 · /health ok
```

飞书真人对话冒烟仍可由 Mimir 补一行 bridge §4；**工程路径已验证**。

## IQ ≥5.5 裁定（documented exception）

| 项 | 值 |
|----|-----|
| **Wave 5 实测** | **4.7/10**（IQ-EVO-26） |
| **较 Wave 4** | 4.5 → **4.7**（+#2 自适应、+#10 闭环） |
| **裁定** | **例外成立** — 1b 有界调参已上线；#1 学习能力、#8 意图理解仍未突破 |
| **下一档** | Wave 6 合格智能体（行为+rubric≥5.5）或 Unified Plan **1c**（须另拍板） |

## 仍关

- `MIMIR_AUTO_EVOLVE=1`
- DecisionRing/Compressor 全量自适应（1c）
