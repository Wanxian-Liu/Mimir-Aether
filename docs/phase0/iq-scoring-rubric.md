# EV-Q04 — 智商评分 rubric（2026-05-26 复评 · IQ-EVO-14）

> 刷新自 [IQ_SCORING_RUBRIC.md](../IQ_SCORING_RUBRIC.md)；依据 Q01–Q03 phase0 真源。
> **本次复评**：Wave 3 完成后诚实复评（hybrid 生产默认 + Chroma 增量 + search-first + AUTO_ANALYSIS 生产门闩）。

## 摘要

- **加权总分 4.3/10**（精算 **4.30**；2026-05-26 **4.1** → 2026-05-25 **3.9** → 2026-05-24 **3.8**）。
- 上调：**反馈收集**（AUTO_ANALYSIS staging→生产默认，7d 97 artifacts）、**上下文管理**（hybrid 生产默认 + Chroma 增量）、**数据闭环**（生产 artifacts 更强证据）。
- 下调：无。
- 距 5.5 目标差 **1.2**。
- **诚实声明**：4.3 反映基础设施从「staging 实验」→「生产默认」的实质升级，不代表「变聪明了」。真正的智商突破仍卡在 #1 学习能力（2.0→7.0）和 #8 意图理解（3.0→7.5）——两维占 25% 权重，Wave 3 未触达。

## 10 维评分

| # | 子维度 | 权 | 现评 | 目标 | 依据（2026-05-26 Wave 3 后） |
|---|--------|:--:|:--:|:--:|------|
| 1 | 学习能力 | 15% | 2.0 | 7.0 | DecisionRing/Degeneration/Compressor 规则为主；AUTO_ANALYSIS 是事后分析不是学习；AUTO_EVOLVE 仍关 |
| 2 | 自适应阈值 | 10% | 3.0 | 7.5 | [Q01](./hardcoded-thresholds.md) **23** 项硬编码，Wave 3 未改任何阈值 |
| 3 | 反馈收集 | 10% | **4.0**↑ | 6.0 | AUTO_ANALYSIS **生产默认**（非 staging）+ 7d **97 artifacts**（bridge §4 IQ-EVO-13 ops 证据）；nudge 注入可见；仍无结构化 FeedbackCollector |
| 4 | 工具选择智能 | 10% | 5.5 | 8.0 | [Q02](./tool-quality-baseline.md) 有排名/降级，无变化 |
| 5 | Prompt 优化 | 10% | 5.0 | 8.0 | skills 注入；search-first prompt 指令已加但不等于优化；无 ToolPromptOptimizer |
| 6 | 错误恢复 | 10% | 6.0 | 8.0 | RecoveryMixin + DecisionRing，无变化 |
| 7 | 上下文管理 | 10% | **8.0**↑ | 8.0 | 🟢 **触顶**。hybrid 生产默认 + Chroma 增量 upsert + compressor 在线/离线 + SEM 全栈 + memory 扩容 55000 chars |
| 8 | 意图理解 | 10% | 3.0 | 7.5 | [Q03](./intent-predictor-audit.md) 无 Predictor；search-first 是 prompt 指令（行为 nudging），不是意图理解能力提升 |
| 9 | 模型路由 | 5% | 4.0 | 7.0 | 仍以默认模型为主，无变化 |
| 10 | 数据闭环 | 10% | **3.5**↑ | 6.0 | AUTO_ANALYSIS 生产默认 + 97 artifacts 产生更强证据；artifact→阈值反哺**仍未接线** |

## 加权

`2.0×0.15 + 3.0×0.10 + 4.0×0.10 + 5.5×0.10 + 5.0×0.10 + 6.0×0.10 + 8.0×0.10 + 3.0×0.10 + 4.0×0.05 + 3.5×0.10` = **4.30 → 4.3/10**

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
| 2 | 自适应阈值 | 3.0 | 7.5 | **4.5** | 23 项硬编码。需 tool_quality→阈值自动调整回路 |
| 3 | 反馈收集 | 4.0 | 6.0 | **2.0** | AUTO_ANALYSIS 生产默认了。需 FeedbackCollector 结构化收集 |
| 10 | 数据闭环 | 3.5 | 6.0 | **2.5** | 97 artifacts 已产生。需 artifact→阈值/prompt 反哺接线 |

**关键瓶颈**：#1 学习能力（差距 5.0，权重 15%）。#7 上下文管理已触顶（8.0），可以不再关注。Wave 3 证明了基础设施可以从 staging→生产，但智商核心（学习、意图）仍待突破。

## 证据链

各维链到 phase0 Q01–Q03 + A01 compressor 边界 + IQ-EVO-01/04 JSON + Wave 2 验收 artifacts + Wave 3 bridge §4 IQ-EVO-11/12/13 签收。

**下一复评**：IQ-EVO-19（Wave 4 完成后）；目标 ≥5.5 或 documented exception 续期。
