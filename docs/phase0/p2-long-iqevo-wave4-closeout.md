# P2-LONG-IQEVO — Wave 4 结案（IQ-EVO-19）

> **日期**：2026-05-26  
> **母任务**：backlog **§15 Wave 4** · 真源 [`p2-long-iqevo-wave4.md`](p2-long-iqevo-wave4.md)  
> **验证**：`./run_ralph_tier0.sh` **433+2**（commit `42da9c0`）；**刘哥验收签收**（飞书/冒烟）

## Wave 4 交付（IQ-EVO-15～19）

| # | 要求 | 证据 |
|---|------|------|
| 1 | 立案 + env 契约 | `p2-long-iqevo-wave4.md` · `.env.example` · `MIMIR_OPS_PANEL.md` §9 |
| 2 | FeedbackCollector | `agent/feedback_collector.py` · `MIMIR_FEEDBACK_COLLECTOR=1` → `data/feedback_events.jsonl` |
| 3 | 只读 tool_quality prompt | `build_tool_quality_guidance()` in `prompt_builder.py` |
| 4 | Pipeline / analysis 接线 | `monitor` · `execution_pipeline` · `post_close_analysis` |
| 5 | rubric 复评 #3 | [`iq-scoring-rubric.md`](iq-scoring-rubric.md) **4.5/10**（IQ-EVO-19） |
| 6 | §17 自治（并行验收） | bridge §4：/new · `mimir_ops` health_check · context_usage |

## 子项对照

| ID | 摘要 | Owner | 状态 |
|----|------|-------|------|
| IQ-EVO-15 | 立案 + backlog + bridge | Cursor | [x] 2026-05-26 |
| IQ-EVO-16 | FeedbackCollector JSONL | Cursor | [x] 2026-05-26 |
| IQ-EVO-17 | tool_quality 只读 prompt | Cursor | [x] 2026-05-26 |
| IQ-EVO-18 | analysis artifact → feedback | Cursor | [x] 2026-05-26 |
| IQ-EVO-19 | rubric 复评 + 本结案 | Mimir+刘哥 | [x] 2026-05-26 · **验收签收** |

## IQ ≥5.5 裁定（documented exception）

| 项 | 值 |
|----|-----|
| **Wave 4 实测** | **4.5/10**（[`iq-scoring-rubric.md`](iq-scoring-rubric.md) · IQ-EVO-19） |
| **较 Wave 3** | 4.3 → **4.5**（+#3 反馈收集、+#10 数据闭环；仍无阈值自改 / AUTO_EVOLVE） |
| **§15 成功标准** | IQ≥5.5 **或** documented 例外 |
| **裁定** | **例外成立** — Wave 4 目标是 **结构化反馈只记录 + 只读质量信号**（Unified Plan **1a**），不是单波拉到 5.5 |
| **下一档 5.5** | **1b** 阈值反哺 / IntentPredictor / AUTO_EVOLVE — **须刘哥另拍板** |

## 生产开关（Cursor 运维 · 2026-05-26）

- `$MIMIR_AETHER_HOME/.env`：**`MIMIR_FEEDBACK_COLLECTOR=1`**（已写入）
- Gateway 硬重启：**PID 356976** · `/health` ok
- **仍关**：`MIMIR_AUTO_EVOLVE=1`

## 刻意未做

- AutoTuner / 硬编码阈值自改（Wave 5 / Unified Plan **1b**）
- ADR-002 大注入

## tier0 契约

- `tests/agent/test_feedback_collector.py`
- `tests/contract/test_horizon_iqevo_wave4.py`
