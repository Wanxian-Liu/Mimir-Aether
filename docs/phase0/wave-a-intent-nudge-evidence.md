# Wave A · WA-A07 / WA-A08 生产接线证据

**Date:** 2026-06-01

## WA-A07 · Intent（规则 MVP，非 ML 全量）

| 项 | 证据 |
|----|------|
| 模块 | `agent/intent_predictor.py` · `IntentPrediction` · `predict_and_format` |
| 默认开 | `MIMIR_INTENT_PREDICTOR` 未设时 **默认 1**（`intent_predictor.py`） |
| 接线 | `core_loop.py` 每 user 轮 `predict_and_format` → `_intent_context_block` |
| 注入 | `callers_mixin.py` `_build_full_messages` 追加 `<intent-context>` |
| 日志 | `[IntentPredictor] intent=… complexity=… search=…` |
| 合约 | `tests/contract/test_horizon_iqevo_wave7_intent.py` · tier0 manifest |

**诚实边界**：规则标签 + 路由提示；**不**宣称 Hermes 级 ML IntentPredictor 全量上线。

## WA-A08 · Memory nudge（Hermes 间隔）

| 项 | 证据 |
|----|------|
| 模块 | `agent/conversation_nudges.py` · `maybe_memory_nudge_message` |
| 间隔 | `MIMIR_MEMORY_NUDGE_INTERVAL=10`（`~/.mimiraether/.env` 已设） |
| 路径 | 飞书/网关 → `core_loop` → **MimirAgentLoop**（`agent_loop.py` L190+） |
| 文案 | `[MIMIR_MEMORY_NUDGE]` · 含 session_search + memory tool 提示 |
| 日志 | `turn N: memory nudge (interval=…)`（WA-A08 追加） |
| 单测 | `tests/agent/test_conversation_nudges.py` |

**与 A09 ② 关系**：nudge 每 10 **agent 轮** 才注入；单轮偏好句 **不保证** 立即写 memory — 需模型跟做或用户重复。
