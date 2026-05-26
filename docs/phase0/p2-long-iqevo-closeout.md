# P2-LONG-IQEVO — Wave 1 结案（IQ-EVO-06）

> **日期**：2026-05-19  
> **母任务**：backlog **§15 `P2-LONG-IQEVO`** · 真源 [`MIMIR_IQ_EVOLUTION_DIRECTION.md`](../MIMIR_IQ_EVOLUTION_DIRECTION.md)  
> **验证**：`./run_ralph_tier0.sh` PASS（**372+2**）；Mimir 证据见 [`MIMIR_LIU_CURSOR_BRIDGE.md`](../MIMIR_LIU_CURSOR_BRIDGE.md) §4（IQ-EVO-00～05）

## Wave 1 交付（IQ-EVO-00～05）

| # | 要求 | 证据 |
|---|------|------|
| 1 | 方向签收 + 协作规约 | `MIMIR_IQ_EVOLUTION_DIRECTION.md` §0～§3；bridge §4 IQ-EVO-00 |
| 2 | 回忆可测 | 20-query 基准 JSON（IQ-EVO-01）；LIKE/FTS/Semantic hit rate 三行 |
| 3 | 行为 smoke | 飞书「查历史」→ `session_search` 调用（IQ-EVO-02） |
| 4 | 进化提案轨 | [`docs/proposals/iq-evo-auto-analysis.md`](../proposals/iq-evo-auto-analysis.md)（IQ-EVO-03） |
| 5 | eval 可跑 | `./scripts/run_evolution_eval.sh` exit 0（IQ-EVO-04） |
| 6 | rubric 复评 | [`iq-scoring-rubric.md`](iq-scoring-rubric.md) **3.9/10**（IQ-EVO-05） |

## 子项对照

| ID | 摘要 | Owner | 状态 |
|----|------|-------|------|
| IQ-EVO-00 | Read 方向真源 + bridge 签收 | Mimir | [x] 2026-05-25 |
| IQ-EVO-01 | 20-query 基准 + JSON | Mimir | [x] 2026-05-25 |
| IQ-EVO-02 | 飞书 session_search smoke | Mimir+刘哥 | [x] 2026-05-25 |
| IQ-EVO-03 | AUTO_ANALYSIS 提案 | Mimir | [x] 2026-05-25 |
| IQ-EVO-04 | `run_evolution_eval.sh` | Mimir | [x] 2026-05-25 |
| IQ-EVO-05 | iq-scoring 复填 | Mimir | [x] 2026-05-25 |
| IQ-EVO-06 | 本结案 + MAINLINE + 周常约定 | Cursor | [x] 2026-05-19 |

## IQ ≥5.5 裁定（documented exception）

| 项 | 值 |
|----|-----|
| **Wave 1 实测** | **3.9/10**（[`iq-scoring-rubric.md`](iq-scoring-rubric.md) · 2026-05-25） |
| **§15 成功标准** | IQ≥5.5 **或** documented 例外 |
| **裁定** | **例外成立** — Wave 1 目标是 **建立可测基线 + Mimir 证据链**（§3.2），不是单波拉到 5.5 |
| **下一档 5.5** | AUTO_ANALYSIS 接入 agent_loop · memory/skill **nudge** · ADR-002 注入 — **Horizon 待刘哥拍板**（非 IQ-EVO-06 阻塞） |

## 进化 eval 周常约定（非 tier0 门禁）

**谁**：Mimir 运维轨（或刘哥本机 cron）  
**频率**：建议 **每周 ≥1 次**（或大版本合入 `agent/`/`gateway/`/`tools` 后）

```bash
cd ~/src/MimirAether
MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh
```

**通过**：exit 0；输出 `$MIMIR_AETHER_HOME/data/evolution_eval/memory-retrieval-latest.json`  
**失败**：记 `MIMIR_ISSUES.md` Active（≤3）+ bridge §4 一行；**停手**等刘哥（勿 silent 改基线）

**Semantic 腿**：需本机 Chroma backfill（`python3 scripts/backfill_chroma_sessions.py`）；CI/tier0 不依赖。

## tier0 契约束

- `tests/contract/test_evolution_eval_ievo04.py`（eval 脚本契约）
- `tests/contract/test_iqevo06_closeout.py`（本波结案）

## Wave 2 工程（IQ-EVO-07～09 · 2026-05-19）

| ID | 交付 |
|----|------|
| IQ-EVO-07 | `agent/post_close_analysis.py` — `MIMIR_AUTO_ANALYSIS=1` → LLM 分析 + `data/analysis_artifacts/` |
| IQ-EVO-08 | `agent/conversation_nudges.py` — `MIMIR_MEMORY_NUDGE_INTERVAL` / `MIMIR_SKILL_NUDGE_INTERVAL`（默认 10） |
| IQ-EVO-09 | `prompt_builder` 跨会话 **核心字段 + cap**（`MIMIR_CROSS_SESSION_MAX_CHARS` 默认 2000） |

**Staging 开分析（刘哥本机）**：在 `$MIMIR_AETHER_HOME/.env` 加 `MIMIR_AUTO_ANALYSIS=1`，重启 Gateway；**不要**默认开 `MIMIR_AUTO_EVOLVE=1`。

## Wave 2 验收（Mimir · 2026-05-26）

| 冒烟 | 结果 | 证据 |
|------|------|------|
| **A — AUTO_ANALYSIS** | ✅ | `~/.mimiraether/data/analysis_artifacts/20260526T135803_训练模型我们用不上么？.json`（`type=post_task_analysis`） |
| **B — nudge** | ✅（会话内） | MEMORY/SKILL nudge 文案注入可见；log 未单独计数 `[MIMIR_*_NUDGE]` |
| **周常 eval** | ✅ | `memory-retrieval-compare-20260526T061634Z.json` — LIKE **1.0** / FTS **0.5** / Semantic **1.0** vs 基线 pass |

Bridge §4 签收 · 回报 §3.3 见 Mimir 飞书会话 2026-05-26。

## 下一粒（刘哥 2026-05-26）

- **先 §15 Wave 3**（IQ-EVO-10～14）— backlog + bridge §1「刘哥拍板」。
- **再 Horizon B1**（`P1-LONG-OBS` · d6 可观测）— backlog **§16**；不与 Wave 3 并行工程。
- **Mimir**：维持周常 `run_evolution_eval.sh`；**勿** `MIMIR_AUTO_EVOLVE=1`。
- **ISSUES #12**：IQ-EVO-14 达标后再 **resolved**。
