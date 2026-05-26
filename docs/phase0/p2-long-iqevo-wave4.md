# P2-LONG-IQEVO · Wave 4（学习闭环 · 只记录不改阈值）

**Date:** 2026-05-26  
**Baseline:** Wave 3 结案 · rubric **4.3/10**（documented exception；距 5.5 差 1.2）  
**真源：** [`MIMIR_UNIFIED_PLAN.md`](../MIMIR_UNIFIED_PLAN.md) 冲突 3 · 子阶段 **1a**

## Goal

Close the gap on **#3 反馈收集** and **#10 数据闭环** without opening `MIMIR_AUTO_EVOLVE=1` or mutating hardcoded thresholds. Wave 4 is **observe → structure → inject read-only signals**.

## Scope (in)

| ID | Deliverable |
|----|-------------|
| IQ-EVO-15 | This plan + backlog §15 Wave 4 + bridge 拍板 |
| IQ-EVO-16 | `FeedbackCollector` → `data/feedback_events.jsonl` (`MIMIR_FEEDBACK_COLLECTOR=1`) |
| IQ-EVO-17 | `tool_quality` degraded summary in prompt (read-only) |
| IQ-EVO-18 | Pipeline close + analysis artifact → feedback events |
| IQ-EVO-19 | Rubric 复评 #3（Mimir）+ closeout · target ≥5.5 or documented exception |

## Out of scope (刘哥未授权)

- `MIMIR_AUTO_EVOLVE=1` / skill auto-apply  
- AutoTuner / DegenerationGuard 自改参（Unified Plan **1b**）  
- IntentPredictor 全量（仅 Wave 4 后候选 **Wave 5**）  
- ADR-002 大注入

## Env

| Var | Default | Meaning |
|-----|---------|---------|
| `MIMIR_FEEDBACK_COLLECTOR` | `0` | `1` → append JSONL feedback events |

## Mimir smoke (after IQ-EVO-16～18 deploy)

1. Staging: `MIMIR_FEEDBACK_COLLECTOR=1` + restart Gateway.  
2. Trigger one tool failure (bad `read_file` path) → `tail` `feedback_events.jsonl` has `tool_failure`.  
3. Long task with AUTO_ANALYSIS → `analysis_artifact` event with path.  
4. If `tool_quality.db` has degraded tools → prompt contains read-only quality block.

## Success

- tier0 green + contract `test_horizon_iqevo_wave4.py`  
- IQ-EVO-19 rubric honest re-score; #3 and #10 should move ≥0.5 each if events flow
