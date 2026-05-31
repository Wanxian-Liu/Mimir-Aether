# Wave A · IQ 5.5 closeout（2026-06-01）

> **拍板**：IQ-RUBRIC-55 ✅ · **出口**：rubric ≥5.5 **或** documented exception  
> **结论**：**维持 4.9** + **exception 续期**（行为未过线，工程链已闭合）

## 工程粒完成度

| ID | 状态 | 要点 |
|----|:----:|------|
| WA-A00～A06 | [x] | 基线 · eval · tool_quality · search 基线/审计 · prompt+audit 加固 |
| WA-A06.1 | [x] | 跨会话 **search-first 工具守卫**（`search_first_guard.py` · tier0 +9 tests） |
| WA-A07 | [x] | intent 接线证据 → [`wave-a-intent-nudge-evidence.md`](./wave-a-intent-nudge-evidence.md) |
| WA-A08 | [x] | memory nudge 已在 MimirAgentLoop；`.env` interval=10；生产 log 行 |
| WA-A09 | [x] | 飞书 3 场景 **0P/1部分** → [`iqevo-30`](./iqevo-30-feishu-smoke-evidence.md) |
| WA-A10 | [x] | `post_analysis evolution` log：**46** 行 applied=1 · ok=1 **24** · ok=0 **22**（~52%） |
| WA-A11 | [x] | rubric **4.9** 复评 → 本 closeout |
| WA-A12 | [x] | 本文档 |

## §1.5 终态

| # | 状态 |
|---|------|
| Q1 | **4.9** + exception（未达 5.5） |
| Q2 | **部分** — 离线 eval 优 · 生产 search-first **未过**（A09 FAIL×2） |
| Q3 | **PASS** — evolution_eval 周常 155907Z |
| Q4 | **PASS** — tool_quality_weekly 已跑 |
| Q5 | **待验证** — feedback JSONL 仍缺 |
| Q6–Q7 | **PASS** |

## 未达 5.5 的原因（诚实）

1. **#1 学习能力**：进化链 log ~52% ok；飞书不先 `session_search`（肌肉记忆）。  
2. **#8 意图**：规则 MVP 已接线，**非** ML 全量；A09 未改善检索行为。  
3. **A06 prompt** 需 gateway 重启后仍待 **飞书复测 ①**；filtered 义务句仍 100% 违例（历史 JSONL）。

## 建议后续（非 Wave A 范围）

- **Wave B**：WM Phase0 spike（`world-model-evolution-plan.md`）· **禁止** 与 Horizon C 混 PR  
- **Q5**：对齐 `MIMIR_FEEDBACK_COLLECTOR` 与 gateway `.env`

## 证据索引

- [`wave-a-behavior-report-20260531.md`](./wave-a-behavior-report-20260531.md)
- [`wave-a-execution-plan.md`](./wave-a-execution-plan.md)
- [`iq-scoring-rubric.md`](./iq-scoring-rubric.md)
- [`iqevo-31-search-first-audit.md`](./iqevo-31-search-first-audit.md)
