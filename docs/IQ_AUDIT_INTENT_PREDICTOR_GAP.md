# IntentPredictor 现状审计

**日期**：2026-05-21  
**来源**：EV-Q03（琬弦智商方案方向六 — 意图预测 P2）

> **Intent 真源（2026-05-24）** → [`docs/phase0/intent-predictor-audit.md`](./phase0/intent-predictor-audit.md)（Predictor 仍无；`intent_action_guard` 已存在）。下文为历史快照。

## 实际状态

| 维度 | 内容 |
|------|------|
| **`agent/intent_predictor.py`** | ❌ **不存在** |
| **任何 `class.*Intent` in agent/** | ❌ 未发现 |
| **任何 `def.*intent` in agent/** | ❌ 未发现 |
| **意图相关引用** | 仅 `prompt_builder.py` 中的 prompt injection 扫描和 `tool_guard.py` 中的风险标注 |

## 与方案 §6.2 意向分类器 v2 的差距

| 方案要求 | 现状 | 差距 |
|---------|------|:--:|
| 意图分类器（code/debug/chat/search/deploy） | 不存在 | 🔴 全部缺失 |
| 任务复杂度评分（TaskComplexityScorer） | 不存在 | 🔴 |
| 模型路由决策（按意图+复杂度选择模型） | DeepSeek-only | 🔴 |
| 用户行为预测（下一步概率） | 不存在 | 🔴 |

## 当前"意图"相关功能

仅存在于以下安全扫描中（非意图预测）：

| 位置 | 功能 | 与实际意图预测的关系 |
|------|------|:--:|
| `prompt_builder.py:scan_context_content()` | 检测 prompt injection 模式 | ❌ 无关 |
| `tool_guard.py` | 工具风险等级标注 | ❌ 无关 |
| `prompt_builder.py:DEFAULT_AGENT_IDENTITY` | Agent 身份描述 | ❌ 无关 |

## 结论

**IntentPredictor 完全不存在**。这是方向六（P2 优先级）中最重的一块——需要从零构建意图分类器 + 任务复杂度评分 + 模型路由决策。建议在方向一（学习引擎 P0）、方向四（工具智能 P1）完成后才启动此方向。
