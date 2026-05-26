# EV-Q04 — 智商评分 rubric（2026-05-25 复评）

> 刷新自 [IQ_SCORING_RUBRIC.md](../IQ_SCORING_RUBRIC.md)；依据 Q01–Q03 phase0 真源。
> **本次复评**：SEM 完成 + CLEARANCE 8/8 后复填（IQ-EVO-05）。

## 摘要

- **加权总分 3.9/10**（精算 **3.90**；2026-05-24 **3.8**；2026-05-21 **3.8**）。
- 上调：**上下文管理**（semantic session_search 100% hit rate + hybrid 上线）、**数据闭环**（evolution eval 可跑 + AUTO_ANALYSIS 提案就绪）。
- 其余 8 维持平。

## 10 维评分

| # | 子维度 | 权 | 现评 | 目标 | 依据（2026-05-25） |
|---|--------|:--:|:--:|:--:|------|
| 1 | 学习能力 | 15% | 2.0 | 7.0 | DecisionRing/Degeneration/Compressor 规则为主 |
| 2 | 自适应阈值 | 10% | 3.0 | 7.5 | [Q01](./hardcoded-thresholds.md) **23** 项硬编码 |
| 3 | 反馈收集 | 10% | 2.0 | 6.0 | execution_pipeline 记录；无 FeedbackCollector |
| 4 | 工具选择智能 | 10% | 5.5 | 8.0 | [Q02](./tool-quality-baseline.md) 有排名/降级 |
| 5 | Prompt 优化 | 10% | 5.0 | 8.0 | skills 注入；无 ToolPromptOptimizer |
| 6 | 错误恢复 | 10% | 6.0 | 8.0 | RecoveryMixin + DecisionRing |
| 7 | 上下文管理 | 10% | **7.5** | 8.0 | [compressor-overlap](./compressor-overlap-audit.md) 在线+离线；**SEM 完成** hybrid/semantic 上线；20-query semantic **100%** hit rate |
| 8 | 意图理解 | 10% | 3.0 | 7.5 | [Q03](./intent-predictor-audit.md) 无 Predictor |
| 9 | 模型路由 | 5% | 4.0 | 7.0 | 仍以默认模型为主 |
| 10 | 数据闭环 | 10% | **2.0** | 6.0 | tool_quality.db + 进化钩子；**evolution eval 可跑**（IEVO-04）；AUTO_ANALYSIS 提案就绪（IQ-EVO-03）；仍未回馈阈值 |

## 加权

`2.0×0.15 + 3.0×0.10 + 2.0×0.10 + 5.5×0.10 + 5.0×0.10 + 6.0×0.10 + 7.5×0.10 + 3.0×0.10 + 4.0×0.05 + 2.0×0.10` = **3.90 → 3.9/10**

## vs 2026-05-24

| 变化 | 说明 |
|------|------|
| 总分 | **3.8 → 3.9**（+0.1） |
| #7 上下文管理 | 6.5 → **7.5**：SEM 完成，semantic 检索 100% hit rate（IQ-EVO-01 JSON） |
| #10 数据闭环 | 1.5 → **2.0**：evolution eval 基础设施验证（IQ-EVO-04 JSON）；AUTO_ANALYSIS 提案已写 |
| 其余 8 维 | 持平，无新能力上线 |

**证据链**：各维链到 phase0 Q01–Q03 + A01 compressor 边界 + IQ-EVO-01/04 JSON。

**下一复评**：AUTO_ANALYSIS 开启 + nudge 移植后（阶段 2 完成）；目标 ≥5.5（阶段 3）。
