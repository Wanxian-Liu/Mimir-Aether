# EV-Q04 — 智商评分 rubric（2026-05-26 复评 · IQ-EVO-38）

> 刷新自 [IQ_SCORING_RUBRIC.md](../IQ_SCORING_RUBRIC.md)；依据 Q01–Q03 phase0 真源。
> **本次复评**：Wave 6 合格智能体结案（行为证据 + artifact prompt + 离线 intent MVP）。

## 摘要

- **加权总分 4.8/10**（精算 **4.75→4.8**；Wave 5 **4.7**）。
- 上调：**Prompt 优化**（artifact 只读段）、**意图理解**（离线标签 MVP，非 Predictor）。
- 距 5.5 目标差 **0.7**。
- **诚实声明**：4.8 = Wave 6 可观测与文档闭环；**不是**学习能力/生产意图突破。

## 10 维评分

| # | 子维度 | 权 | 现评 | 目标 | 依据（2026-05-26 Wave 6 后） |
|---|--------|:--:|:--:|:--:|------|
| 1 | 学习能力 | 15% | 2.0 | 7.0 | 规则为主；AUTO_EVOLVE 仍关 |
| 2 | 自适应阈值 | 10% | 4.0 | 7.5 | Top-3 AutoTuner + `MIMIR_AUTO_TUNER=1` |
| 3 | 反馈收集 | 10% | 5.0 | 6.0 | FeedbackCollector + 生产 JSONL |
| 4 | 工具选择智能 | 10% | 5.5 | 8.0 | Q02 排名/降级 |
| 5 | Prompt 优化 | 10% | **5.5**↑ | 8.0 | search-first + tool_quality + **analysis artifact 只读**（IQ-EVO-35） |
| 6 | 错误恢复 | 10% | 6.0 | 8.0 | RecoveryMixin + DecisionRing |
| 7 | 上下文管理 | 10% | **8.0** | 8.0 | 🟢 触顶 |
| 8 | 意图理解 | 10% | **3.5**↑ | 7.5 | 离线 intent 标签；**无**生产 Predictor |
| 9 | 模型路由 | 5% | 4.0 | 7.0 | 默认模型为主 |
| 10 | 数据闭环 | 10% | 5.0 | 6.0 | feedback→tune→消费；AUTO_EVOLVE 关 |

## 加权

`2.0×0.15 + 4.0×0.10 + 5.0×0.10 + 5.5×0.10 + 5.5×0.10 + 6.0×0.10 + 8.0×0.10 + 3.5×0.10 + 4.0×0.05 + 5.0×0.10` = **4.75 → 4.8/10**

## vs Wave 5（4.7）

| 变化 | 说明 |
|------|------|
| 总分 | **4.7 → 4.8**（+0.1） |
| #5 Prompt | 5.0 → **5.5** |
| #8 意图 | 3.0 → **3.5** |
| 行为 | Wave 6 证据脚本 + ops 周常 |

## 距 5.5 差距（诚实）

| # | 维度 | 现评 | 差距 | 需什么 |
|---|------|:--:|:--:|------|
| 1 | 学习能力 | 2.0 | **5.0** | AUTO_EVOLVE 或 1c（未授权） |
| 8 | 意图理解 | 3.5 | **4.0** | 生产 IntentPredictor |
| 2 | 自适应阈值 | 4.0 | **3.5** | 全量 23 项，非 Top-3 |

**ISSUES #12：** resolved · documented exception 续期至 ≥5.5。

## 证据链

Wave 6 closeout · `iqevo-30`～`34` · `evolution-eval-weekly.md` · IQ-EVO-29/37 JSON 路径 · bridge §4 2026-05-26 Wave 6 行。

**下一复评：** 刘哥飞书 3 场景 hard pass 或新 Horizon 拍板。
