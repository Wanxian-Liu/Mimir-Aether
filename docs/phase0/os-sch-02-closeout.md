# OS-SCH-02 closeout — session_search BM25 + semantic fusion

**Grain:** `OS-SCH-02` · Wave 11 Task 5  
**Base:** `1dfcf57` (post OS-TQM-02)

## What shipped

| Leg | Source | Rank signal |
|-----|--------|-------------|
| **Lexical** | FTS5 `bm25(messages_fts)` when `fts5_search.db` exists; else LIKE session order | BM25 / term match |
| **Semantic** | Chroma `query_session_messages` | distance (lower = better rank) |
| **Merge** | `rank_fusion_rrf` | RRF with **k=60** (reciprocal rank fusion) |

## When fusion runs

- Backend **`semantic_hybrid`** only.
- **`MIMIR_SESSION_SEARCH_FUSION=1`** (default): call `_session_search_via_fusion` before legacy waterfall.
- **`MIMIR_SESSION_SEARCH_FUSION=0`**: restore pre-SCH-02 semantic→FTS→LIKE cascade (contract-tested).

## Design choice

**RRF** over weighted score sum: lexical BM25 and Chroma distance are not comparable scales; RRF only needs ranks. Sessions appearing in both lists rise (e.g. `b` when lexical=`[a,b,c]` and semantic=`[b,d]`).

## Tests

- `tests/tools/test_session_search_fusion_rank.py` — RRF unit + fusion integration (mock Chroma)
- `tests/contract/test_horizon_os_sch_02.py` — exports + tier0 registration

## Not in scope

- New `SESSION_SEARCH_BACKEND=fusion` alias (use `semantic_hybrid` + fusion flag)
- Mandatory benchmark JSON delta (optional follow-up on `run_memory_retrieval_benchmark.py`)

## Next

- **OS-REV-01** / **OS-TOOL-SRCH-01** (Wave 12–13) unlocked per master plan
