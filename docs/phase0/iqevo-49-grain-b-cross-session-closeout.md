# IQ-EVO-49 — 粒 B 跨会话注入结案

> **日期**：2026-05-27  
> **前置**：粒 A `/new` 同步 flush [x] · IQ-EVO-09 ADR-002 cap [x]

## 做了什么

- `agent/prompt_builder._build_cross_session_context` 从 runtime `persistent.json` → `memory.key_decisions`（默认最近 **5**）与 `learned_patterns`（默认最近 **3**）注入 `<cross-session-context>`。
- 支持 dict 行（`decision` / `pattern`）与 legacy 字符串行。
- 仍受 `MIMIR_CROSS_SESSION_MAX_CHARS` 总 cap；条数可用 `MIMIR_CROSS_SESSION_DECISIONS_MAX` / `MIMIR_CROSS_SESSION_PATTERNS_MAX` 覆盖。

## 验证

- `tests/agent/test_cross_session_grain_b.py`
- `tests/contract/test_horizon_iqevo_wave8_grain_b.py`
- `./run_ralph_tier0.sh`

## Mimir 验收（人工）

1. 确保 `~/.mimiraether/data/persistent.json` 的 `memory.key_decisions` 有上一轮决策。
2. 飞书 `/new` → 首条问「上次关键决策是什么」→ 应能引用注入片段（非空盘时）。

## 非范围

- P3 全量跨会话 RAG（§11 调研项）。
- 不改 Chroma / `SESSION_SEARCH_BACKEND` 生产默认。
