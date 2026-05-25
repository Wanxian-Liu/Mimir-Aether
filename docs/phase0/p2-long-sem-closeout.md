# P2-LONG-SEM — Horizon A 结案（SEM-06）

> **日期**：2026-05-19  
> **母任务**：§14 **`P2-LONG-SEM`**（Horizon A · 刘哥 2026-05-25）  
> **验证**：`./run_ralph_tier0.sh` → **368+2** PASS；可选 `./scripts/run_evolution_eval.sh`（本机 DB + Chroma）

## 交付对照（ADR-006 / Unified Plan §4）

| # | 要求 | 证据 |
|---|------|------|
| 1 | Chroma 持久化 + backfill（AC3） | `tools/chroma_session_indexer.py` · `scripts/backfill_chroma_sessions.py` · `get_mimir_chroma_dir()` |
| 2 | 检索 backend（AC6） | `SESSION_SEARCH_BACKEND=semantic\|semantic_hybrid` · `tools/session_search_tool.py` |
| 3 | Benchmark + eval semantic 腿 | `run_memory_retrieval_benchmark.py` · `compare_memory_retrieval_baseline.py` · `semantic_hit_rate` |
| 4 | tier0 回归 ≥3 | `tests/contract/test_horizon_sem_sem05.py` manifest（9+ 文件）· `tests/tools/test_sem05_smoke.py` |
| 5 | 路径契约 | `docs/path-contract.md` · ADR-006 |

## 子项对照

| ID | 摘要 | 状态 |
|----|------|------|
| SEM-01 | ADR-006 + path-contract | [x] |
| SEM-02 | Chroma indexer + backfill | [x] |
| SEM-03 | semantic / semantic_hybrid backend | [x] |
| SEM-04 | benchmark + compare semantic | [x] |
| SEM-05 | tier0 manifest + smoke | [x] |
| SEM-06 | 本结案 + MAINLINE + GH #32 | [x] |

## 语义 query 子集（#6–#13）

[`memory-retrieval-baseline.md`](memory-retrieval-baseline.md) §3 中 **8 条语义偏重** query（paraphrase / 中文模糊意图）。  
Benchmark 输出字段：`like_semantic_heavy_hit_rate` · `semantic_semantic_heavy_hit_rate`（Chroma 可用时）。

### 结案裁定（documented exception）

| 环境 | 子集 vs LIKE | 说明 |
|------|-------------|------|
| **tier0 / CI** | 不要求 semantic ≥ LIKE | 默认 **hash embedding**（离线可复现）；CJK 语义 paraphrase 非其设计目标 |
| **本机 eval**（Chroma 已 backfill） | 建议 `semantic_semantic_heavy_hit_rate` ≥ `like_semantic_heavy_hit_rate` | 设置 **`MIMIR_EMBED_MODEL`**（sentence-transformers）后重跑 benchmark；将实测 `semantic_hit_rate` 写入新基线后 compare 启用 semantic 回归门 |
| **当前冻结基线** | `semantic_hit_rate: null` | IEVO-04 LIKE/FTS 门不变；semantic 门跳过直至本机冻结 |

## GitHub #32（phase-2 semantic memory）

| 已交付 | 余量（可续 icebox / follow-up） |
|--------|----------------------------------|
| Chroma persist + backfill · semantic / semantic_hybrid · 20-query benchmark 第三腿 · tier0 契约 | Gateway **增量** Chroma upsert（batch/async，非 SEM 阻塞项）· 生产 embed 模型选型与 CJK 质量验收 · ADR-002 跨会话注入（**非**本波） |

**建议**：刘哥确认后 **comment/close #32** 并链到本文件；余量开新 issue 或 icebox。

## tier0 契约束（Gate2 须保持）

见 [`test_horizon_sem_sem05.py`](../tests/contract/test_horizon_sem_sem05.py) `SEM_TIER0_PATHS` + [`test_horizon_sem_sem06.py`](../tests/contract/test_horizon_sem_sem06.py)。

## 下一粒

- **工程**：Horizon A **SEM 波 [x]** — 下一条 Horizon 待刘哥拍板（ADR-002 / Phase 3 等，**勿**默认开）。
- **Mimir 并行轨**：backlog **§15 `P2-LONG-IQEVO`**（与 SEM 工程分离）。
