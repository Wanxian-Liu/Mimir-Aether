# EV-Q04 — 智商评分 rubric（2026-05-24）

> 刷新自 [IQ_SCORING_RUBRIC.md](../IQ_SCORING_RUBRIC.md)；依据 Q01–Q03 phase0 真源。

## 摘要

- **加权总分 3.8/10**（精算 **3.75**；2026-05-21 **3.8**；方案自评 7.2 仍高估）。
- 上调：**工具选择**（ToolQuality 有 DB）、**数据闭环**（pipeline+DB，无 ExperienceBuffer）。
- 下调：**意图理解**（仅 guard，无 Predictor；修正旧稿 #8 笔误）。

## 10 维评分

| # | 子维度 | 权 | 现评 | 目标 | 依据（2026-05-24） |
|---|--------|:--:|:--:|:--:|------|
| 1 | 学习能力 | 15% | 2.0 | 7.0 | DecisionRing/Degeneration/Compressor 规则为主 |
| 2 | 自适应阈值 | 10% | 3.0 | 7.5 | [Q01](./hardcoded-thresholds.md) **23** 项硬编码 |
| 3 | 反馈收集 | 10% | 2.0 | 6.0 | execution_pipeline 记录；无 FeedbackCollector |
| 4 | 工具选择智能 | 10% | 5.5 | 8.0 | [Q02](./tool-quality-baseline.md) 有排名/降级 |
| 5 | Prompt 优化 | 10% | 5.0 | 8.0 | skills 注入；无 ToolPromptOptimizer |
| 6 | 错误恢复 | 10% | 6.0 | 8.0 | RecoveryMixin + DecisionRing |
| 7 | 上下文管理 | 10% | 6.5 | 8.0 | [compressor-overlap](./compressor-overlap-audit.md) 在线+离线 |
| 8 | 意图理解 | 10% | **3.0** | 7.5 | [Q03](./intent-predictor-audit.md) 无 Predictor |
| 9 | 模型路由 | 5% | 4.0 | 7.0 | 仍以默认模型为主 |
| 10 | 数据闭环 | 10% | 1.5 | 6.0 | tool_quality.db + 进化钩子；未回馈阈值 |

## 加权

`2.0×0.15 + 3.0×0.10 + … + 1.5×0.10` = **3.75 → 3.8/10**

## vs 2026-05-21

| 变化 | 说明 |
|------|------|
| 总分 | **持平 ~3.8**（意图维降分 ≈ 工具/闭环/上下文升分抵消） |
| #8 笔误 | 旧稿写「Predictor 存在」→ 纠正为 **guard only** |
| 证据链 | 各维链到 phase0 Q01–Q03 + A01 compressor 边界 |

**Phase 0 后**：IQ 子项可复用本表；AutoTuner/evolve 落地后再抬 #2/#10。
