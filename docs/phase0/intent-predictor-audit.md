# EV-Q03 — IntentPredictor 审计（2026-05-24）

> **IQ-EVO-47（2026-05-27）**：`agent/intent_predictor.py` — 规则 MVP（`IntentPrediction` + `predict()`），env `MIMIR_INTENT_PREDICTOR` 默认开。非 ML 全量分类器。勿与 **`intent_action_guard`** 混淆。

## 摘要

- **方案 §6.2 分类器 v2**：**部分** — 规则 MVP + prompt/便宜路由守卫；无 ML 训练路由。
- **现有**：`intent_action_guard` — 规则 nudge（`MAX_INTENT_NUDGES=2`），接 **`agent_loop`** turn 末，非意图分类。
- **安全向**：`prompt_builder.scan_context_content`、tool_guard — 与预测无关（[agent-core map](./agent-core-responsibility-map.md)）。

## 差距表（方案 vs 现状）

| 能力 | 现状 | 差距 |
|------|------|:--:|
| 意图分类（code/debug/chat/…） | 无 | 🔴 |
| TaskComplexityScorer | 无 | 🔴 |
| 按意图+复杂度选模型 | 配置默认单模型 | 🔴 |
| 下一步行为预测 | 无 | 🔴 |
| **行动守卫**（禁「光说不做」） | `intent_action_guard` + env `MIMIR_INTENT_ACTION_GUARD` | 🟢 局部 |

## 相关符号

| 模块 | 入口 |
|------|------|
| `intent_action_guard` | `guard_enabled`, `should_block_text_only_finish`, `build_nudge_message` |
| `agent_loop` | L31–36 import；turn 内 nudge |

## vs 2026-05-21

结论不变（Predictor 缺失）；**新增记录** E-006 系列 **intent-action guard** 已落地，不填补 Predictor 缺口。

## Phase 1

P2：先 Q01 AutoTuner + Q02 工具闭环，再建轻量 intent 标签（日志/离线），最后模型路由；guard 保持独立策略层。
