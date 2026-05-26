# P2-LONG-IQEVO · Wave 5（有界自调参 · Unified Plan 1b）

**Date:** 2026-05-26  
**Baseline:** Wave 4 结案 · rubric **4.5/10**（documented exception；距 5.5 差 1.0）  
**真源：** [`MIMIR_UNIFIED_PLAN.md`](../MIMIR_UNIFIED_PLAN.md) 冲突 3 · 子阶段 **1b**  
**拍板：** 刘哥「开 Wave 5」

## Goal

Turn Wave 4 **feedback JSONL** into **bounded, auditable threshold overrides** for the Top-3 🔴 knobs — without `MIMIR_AUTO_EVOLVE=1`, DecisionRing learning, or ADR-002 inject.

## Scope (in)

| ID | Deliverable |
|----|-------------|
| IQ-EVO-20 | This plan + backlog §15 Wave 5 + bridge 拍板 |
| IQ-EVO-21 | `ExperienceBuffer` — summarize `feedback_events.jsonl` |
| IQ-EVO-22 | `tuned_thresholds` registry + `data/tuned_thresholds.json` |
| IQ-EVO-23 | `AutoTuner` — bounded tune cycle (`MIMIR_AUTO_TUNER=1`) + `tune_audit.jsonl` |
| IQ-EVO-24 | Wire Top-3: `threshold_percent` · `loop_detection.threshold` · `tool_quality.degraded_threshold` |
| IQ-EVO-25 | tier0 + contract `test_horizon_iqevo_wave5.py` |
| IQ-EVO-26 | Rubric 复评 #4（Mimir）+ closeout · target ≥5.5 or documented exception |

## Out of scope (仍关)

- `MIMIR_AUTO_EVOLVE=1` / skill 自动写入  
- Unified Plan **1c**（DecisionRing / Compressor 全量自适应）  
- IntentPredictor 全量  
- 无界自改参 / 运行时改 `degeneration_guard.json` 源文件

## Env

| Var | Default | Meaning |
|-----|---------|---------|
| `MIMIR_FEEDBACK_COLLECTOR` | `1`（生产已开） | 反馈事件输入 |
| `MIMIR_AUTO_TUNER` | `0` | `1` → pipeline close 后可有界调参 |

## Top-3 可调键（有界）

| Key | Default | Bounds | 消费方 |
|-----|---------|--------|--------|
| `compressor.threshold_percent` | 0.50 | 0.35–0.70 | `core_loop` → `MimirContextCompressor` |
| `degeneration.loop_detection.threshold` | 3 | 2–5 | `degeneration_guard` |
| `tool_quality.degraded_threshold` | 0.50 | 0.30–0.70 | `get_degraded_tools` / prompt |

## Mimir smoke（IQ-EVO-23～24 部署后）

1. Staging: `MIMIR_AUTO_TUNER=1` + Gateway 重启。  
2. 触发多次 tool 失败或 degraded close → `data/tuned_thresholds.json` 有变更 + `tune_audit.jsonl` 一行。  
3. 确认 `mimir_ops` / health 仍绿；**勿开** AUTO_EVOLVE。

## Success

- tier0 green + wave5 contract  
- IQ-EVO-26 rubric；#2 自适应、#10 闭环应各 +≥0.5（若调参生效）

## Closeout

**[x] 2026-05-26** — [`p2-long-iqevo-wave5-closeout.md`](p2-long-iqevo-wave5-closeout.md) · rubric **4.7/10** documented exception
