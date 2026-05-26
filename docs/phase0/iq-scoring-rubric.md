# EV-Q04 — 智商评分 rubric（2026-05-26 复评 · IQ-EVO-26）

> 刷新自 [IQ_SCORING_RUBRIC.md](../IQ_SCORING_RUBRIC.md)；依据 Q01–Q03 phase0 真源。
> **本次复评**：Wave 5 完成后（有界 AutoTuner · `tuned_thresholds.json` · 生产 `MIMIR_AUTO_TUNER=1`）。

## 摘要

- **加权总分 4.7/10**（精算 **4.65→4.7**；Wave 4 **4.5** → Wave 3 **4.3**）。
- 上调：**自适应阈值**（Top-3 有界 override + audit）、**数据闭环**（feedback→tune 路径，仍非 AUTO_EVOLVE）。
- 距 5.5 目标差 **0.8**。
- **诚实声明**：4.7 = 基础设施会「微调旋钮」，不是 #1 学习能力或 #8 意图理解突破。

## 10 维评分

| # | 子维度 | 权 | 现评 | 目标 | 依据（2026-05-26 Wave 3 后） |
|---|--------|:--:|:--:|:--:|------|
| 1 | 学习能力 | 15% | 2.0 | 7.0 | DecisionRing/Degeneration/Compressor 规则为主；AUTO_ANALYSIS 是事后分析不是学习；AUTO_EVOLVE 仍关 |
| 2 | 自适应阈值 | 10% | **4.0**↑ | 7.5 | Top-3 有界 `tuned_thresholds.json` + `MIMIR_AUTO_TUNER=1`；非 23 项全量自适应 |
| 3 | 反馈收集 | 10% | **5.0**↑ | 6.0 | AUTO_ANALYSIS 生产默认 + **FeedbackCollector**（`tool_failure` / `pipeline_close` / `analysis_artifact` JSONL）；生产 `MIMIR_FEEDBACK_COLLECTOR=1`（Wave 4 ops） |
| 4 | 工具选择智能 | 10% | 5.5 | 8.0 | [Q02](./tool-quality-baseline.md) 有排名/降级，无变化 |
| 5 | Prompt 优化 | 10% | 5.0 | 8.0 | skills 注入；search-first prompt 指令已加但不等于优化；无 ToolPromptOptimizer |
| 6 | 错误恢复 | 10% | 6.0 | 8.0 | RecoveryMixin + DecisionRing，无变化 |
| 7 | 上下文管理 | 10% | **8.0**↑ | 8.0 | 🟢 **触顶**。hybrid 生产默认 + Chroma 增量 upsert + compressor 在线/离线 + SEM 全栈 + memory 扩容 55000 chars |
| 8 | 意图理解 | 10% | 3.0 | 7.5 | [Q03](./intent-predictor-audit.md) 无 Predictor；search-first 是 prompt 指令（行为 nudging），不是意图理解能力提升 |
| 9 | 模型路由 | 5% | 4.0 | 7.0 | 仍以默认模型为主，无变化 |
| 10 | 数据闭环 | 10% | **5.0**↑ | 6.0 | feedback→`tune_audit.jsonl`→三处消费；仍无 AUTO_EVOLVE / 1c 全量反哺 |

## 加权

`2.0×0.15 + 4.0×0.10 + 5.0×0.10 + 5.5×0.10 + 5.0×0.10 + 6.0×0.10 + 8.0×0.10 + 3.0×0.10 + 4.0×0.05 + 5.0×0.10` = **4.65 → 4.7/10**

## vs 2026-05-26 IQ-EVO-19（4.5）

| 变化 | 说明 |
|------|------|
| 总分 | **4.5 → 4.7**（+0.2） |
| #2 自适应阈值 | 3.0 → **4.0**：有界 AutoTuner + 生产 env |
| #10 数据闭环 | 4.5 → **5.0**：feedback→tune→消费方 |
| 其余 8 维 | 持平 |

## vs 2026-05-26 IQ-EVO-14（4.3）

| 变化 | 说明 |
|------|------|
| 总分 | **4.3 → 4.5**（+0.2） |
| #3 反馈收集 | 4.0 → **5.0**：FeedbackCollector + 生产 `MIMIR_FEEDBACK_COLLECTOR=1` |
| #10 数据闭环 | 3.5 → **4.5**：JSONL 事件链 + 只读 tool_quality 信号；阈值反哺仍关 |
| 其余 8 维 | 持平 |

## vs 2026-05-26 IQ-EVO-10（4.1）

| 变化 | 说明 |
|------|------|
| 总分 | **4.1 → 4.3**（+0.2） |
| #3 反馈收集 | 3.0 → **4.0**：AUTO_ANALYSIS staging→**生产默认**，7d 97 artifacts（IQ-EVO-13 ops 证据） |
| #7 上下文管理 | 7.5 → **8.0**：hybrid 生产默认 + Chroma 增量 upsert（IQ-EVO-11），**触顶** |
| #10 数据闭环 | 3.0 → **3.5**：生产 artifacts 提供更强证据，但 artifact→阈值反哺仍未接线 |
| #8 意图理解 | 维持 3.0：search-first 是 prompt 指令，不是 IntentPredictor 能力 |
| 其余 6 维 | 持平，无新能力上线 |

## 距 5.5 差距（诚实）

| # | 维度 | 现评 | 目标 | 差距 | 需什么 |
|---|------|:--:|:--:|:--:|------|
| 1 | 学习能力 | 2.0 | 7.0 | **5.0** | 最大缺口（15% 权重）。需从「规则驱动」→「从错误中自动调整」。AUTO_EVOLVE 管线存在但默认关 |
| 8 | 意图理解 | 3.0 | 7.5 | **4.5** | 无 IntentPredictor。search-first prompt 是 nudging 不是能力 |
| 2 | 自适应阈值 | 4.0 | 7.5 | **3.5** | Top-3 有界；全量 23 项仍硬编码 |
| 3 | 反馈收集 | 5.0 | 6.0 | **1.0** | 结构化收集已有；距 6.0 差主动策略层 |
| 10 | 数据闭环 | 5.0 | 6.0 | **1.0** | tune 路径已通；AUTO_EVOLVE / 1c 仍关 |

**关键瓶颈**：#1 学习能力（差距 5.0，权重 15%）。#7 上下文管理已触顶（8.0），可以不再关注。Wave 3 证明了基础设施可以从 staging→生产，但智商核心（学习、意图）仍待突破。

## 证据链

各维链到 phase0 Q01–Q03 + A01 compressor 边界 + IQ-EVO-01/04 JSON + Wave 2 验收 artifacts + Wave 3 bridge §4 IQ-EVO-11/12/13 签收。

**下一复评**：Wave 6 合格智能体（IQ-EVO-39）；目标 ≥5.5 或 documented exception 续期。
