# ADR-006: Semantic session search (ChromaDB)

> **Status:** Proposed (2026-05-25)  
> **Scope:** Horizon **A** · `P2-LONG-SEM` · GH **#32**  
> **Owner:** Cursor（工程）· 刘哥拍板 Horizon A 2026-05-25  
> **Related:** [memory-retrieval-baseline.md](../phase0/memory-retrieval-baseline.md) · [ADR-003](./003-runtime-env-aliases.md) · Unified Plan §4 冲突 2（AC3 + AC6 合并）

---

## Context

Phase 1 **P1-LONG-MEM** delivered LIKE / FTS5 / **hybrid** on `sessions_search.db` (LIKE **60%** / FTS **50%** on 20-query benchmark). Queries #6–#13 are **semantic-heavy** (paraphrase, Chinese fuzzy intent) — poor fit for substring/FTS5 alone.

**P2-LONG-SEM** adds an **embedding index** for transcript retrieval without replacing cross-session `persistent.json` injection (ADR-002 remains separate).

---

## Decision

### 1. Storage engine (AC3)

- **Engine:** [ChromaDB](https://docs.trychroma.com/) **PersistentClient** (local, no server required for tier0/dev).
- **Path:** `{get_mimir_data_dir()}/chroma_sessions/` — never under git repo root.
- **Collection:** one logical collection `session_messages` (metadata: `session_id`, `message_id`, `role`, `source`, `timestamp`).
- **Optional dependency:** `chromadb` (+ embedding backend) — import fail-open like other optional tools; absence → semantic backend unavailable, hybrid falls back to existing LIKE/FTS.

### 2. Index source

- **Primary feed:** rows in **`sessions_search.db`** (`messages` + `sessions`), same as P1 indexer — avoids dual SoT.
- **Incremental:** gateway / indexer hooks that already append to `sessions_search.db` (P1-M03) trigger **async or batch** chroma upsert (SEM-02); no second transcript SoT.

### 3. Retrieval API (AC6)

Extend `SESSION_SEARCH_BACKEND` in `tools/session_search_tool.py`:

| Value | Behavior |
|-------|----------|
| `like` | unchanged (default) |
| `fts5` | unchanged |
| `hybrid` | unchanged (FTS5 → LIKE) |
| **`semantic`** | Chroma query → if empty, **no** silent LIKE (explicit semantic-only mode) |
| **`semantic_hybrid`** | Chroma query → if empty, existing **hybrid** (FTS5 → LIKE) |

**Env (proposed):**

| Variable | Purpose |
|----------|---------|
| `MIMIR_CHROMA_DIR` | Override chroma persist root (default under `data/chroma_sessions/`) |
| `MIMIR_EMBED_MODEL` | Local embedding model id (default TBD in SEM-02; must work offline for tier0 smoke) |

### 4. Benchmark & evolution

- Extend `run_memory_retrieval_benchmark.py` with optional **`semantic_hit_rate`** when chroma index exists (SEM-04).
- **`run_evolution_eval.sh`** compare: semantic leg **must not regress** vs baseline − 5pp once SEM-04 lands; until then LIKE/FTS gates unchanged (IEVO-04).

### 5. Non-goals (SEM wave)

- **Not** replacing `persistent.json` / CrossSessionMemory (→ ADR-002).
- **Not** ObservabilityBus / insights refactor.
- **Not** cloud-only embedding APIs as tier0 hard dependency.

---

## Consequences

### Positive

- Unified Phase 2 memory semantic project (AC3 storage + AC6 strategy) per Unified Plan §4.
- Clear path under `MIMIR_AETHER_HOME` aligned with path-contract.

### Negative / follow-ups

- Disk size + backfill time for large `sessions_search.db`.
- Embedding model choice affects tier0 portability (prefer small local model + mocked unit tests).
- CJK semantic quality must be validated on queries #6–#13 subset.

---

## Verification (SEM wave)

```bash
./run_ralph_tier0.sh                    # each SEM PR
./scripts/run_memory_retrieval_benchmark.py   # after SEM-04
./scripts/run_evolution_eval.sh         # after semantic compare lands
```

Contract tests: `tests/contract/test_horizon_sem_*.py` (manifest per SEM milestone).

---

## Rollout sub-items

| ID | Deliverable | Status |
|----|-------------|--------|
| SEM-01 | This ADR + path-contract + backlog §14 | [x] 2026-05-25 |
| SEM-02 | Indexer / backfill → chroma | [ ] |
| SEM-03 | `semantic` / `semantic_hybrid` backend | [ ] |
| SEM-04 | Benchmark + eval compare semantic leg | [ ] |
| SEM-05 | tier0 regression ≥3 | [ ] |
| SEM-06 | Closeout + GH #32 + MAINLINE | [ ] |
