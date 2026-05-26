# EV-Q04 — 智商评分 rubric（2026-05-26 复评 · IQ-EVO-10）

> 刷新自 [IQ_SCORING_RUBRIC.md](../IQ_SCORING_RUBRIC.md)；依据 Q01–Q03 phase0 真源。
> **本次复评**：Wave 2 验收后诚实复评（AUTO_ANALYSIS staging + nudge + cross-session cap）。

## 摘要

- **加权总分 4.1/10**（精算 **4.10**；2026-05-25 **3.9**；2026-05-24 **3.8**）。
- 上调：**反馈收集**（AUTO_ANALYSIS staging 在生产 artifacts + nudge 注入可见）、**数据闭环**（artifacts 产生 + tool_quality 有数据，但 artifact→阈值反哺未接线）。
- 下调：无。
- 距 5.5 目标差 **1.4**。
- **诚实声明**：4.1 不代表"变聪明了"，只说明反馈采集和闭环的基础设施从「不存在」→「staging 在用」。真正的智商提升需要 #1 学习能力（2.0→7.0）和 #8 意图理解（3.0→7.5）突破——这两维 Wave 2 没碰。

## 10 维评分

| # | 子维度 | 权 | 现评 | 目标 | 依据（2026-05-26） |
|---|--------|:--:|:--:|:--:|------|
| 1 | 学习能力 | 15% | 2.0 | 7.0 | DecisionRing/Degeneration/Compressor 规则为主；AUTO_ANALYSIS 是事后分析不是学习；nudge 是提醒存记忆不是我"学会"了 |
| 2 | 自适应阈值 | 10% | 3.0 | 7.5 | [Q01](./hardcoded-thresholds.md) **23** 项硬编码，Wave 2 未改任何阈值 |
| 3 | 反馈收集 | 10% | **3.0**↑ | 6.0 | AUTO_ANALYSIS staging 在生产 artifacts（`20260526T135803_训练模型…json` 有证据）；nudge 注入可见；仍无 FeedbackCollector |
| 4 | 工具选择智能 | 10% | 5.5 | 8.0 | [Q02](./tool-quality-baseline.md) 有排名/降级，无变化 |
| 5 | Prompt 优化 | 10% | 5.0 | 8.0 | skills 注入；无 ToolPromptOptimizer，无变化 |
| 6 | 错误恢复 | 10% | 6.0 | 8.0 | RecoveryMixin + DecisionRing，无变化 |
| 7 | 上下文管理 | 10% | 7.5 | 8.0 | [compressor-overlap](./compressor-overlap-audit.md) 在线+离线；SEM 完成 hybrid/semantic 上线；memory 扩容 55000 chars（配置改动非能力提升） |
| 8 | 意图理解 | 10% | 3.0 | 7.5 | [Q03](./intent-predictor-audit.md) 无 Predictor，无变化 |
| 9 | 模型路由 | 5% | 4.0 | 7.0 | 仍以默认模型为主，无变化 |
| 10 | 数据闭环 | 10% | **3.0**↑ | 6.0 | AUTO_ANALYSIS staging 产生 artifacts + tool_quality.db 有数据 + nudge 运行；artifact→阈值反哺**仍未接线** |

## 加权

`2.0×0.15 + 3.0×0.10 + 3.0×0.10 + 5.5×0.10 + 5.0×0.10 + 6.0×0.10 + 7.5×0.10 + 3.0×0.10 + 4.0×0.05 + 3.0×0.10` = **4.10 → 4.1/10**

## vs 2026-05-25

| 变化 | 说明 |
|------|------|
| 总分 | **3.9 → 4.1**（+0.2） |
| #3 反馈收集 | 2.0 → **3.0**：AUTO_ANALYSIS staging 在生产 artifacts（Wave 2 验收证据）；nudge 注入可见 |
| #10 数据闭环 | 2.0 → **3.0**：tool_quality.db 有数据 + artifacts 产生；但 artifact→阈值反哺仍未接线 |
| 其余 8 维 | 持平，无新能力上线 |

## 距 5.5 差距（诚实）

| # | 维度 | 现评 | 目标 | 差距 | 需什么 |
|---|------|:--:|:--:|:--:|------|
| 1 | 学习能力 | 2.0 | 7.0 | **5.0** | 最大的缺口。需要从「规则驱动」→「从错误中自动调整」。AUTO_EVOLVE 管线存在但默认关，即使开了也是事后分析不是实时学习。 |
| 8 | 意图理解 | 3.0 | 7.5 | **4.5** | 无 IntentPredictor。当前靠 prompt 和 tool-triggers 技能硬编码匹配。 |
| 2 | 自适应阈值 | 3.0 | 7.5 | **4.5** | 23 项硬编码。需 tool_quality→阈值自动调整回路。 |
| 3 | 反馈收集 | 3.0 | 6.0 | **3.0** | AUTO_ANALYSIS 已在 staging。需 FeedbackCollector 结构化收集 + 接入决策。 |
| 10 | 数据闭环 | 3.0 | 6.0 | **3.0** | artifacts 有了。需 artifact→阈值/prompt 反哺接线。 |

**关键瓶颈**：#1 学习能力占权重 15%，差距最大且最难突破。AUTO_EVOLVE 是答案的一部分但它默认关——即使开了也只是事后管线。

## 证据链

各维链到 phase0 Q01–Q03 + A01 compressor 边界 + IQ-EVO-01/04 JSON + Wave 2 验收证据（`analysis_artifacts/20260526T135803_训练模型…json`）。

**下一复评**：IQ-EVO-14（Wave 3 完成后）；目标 ≥5.5 或 documented exception 续期。
