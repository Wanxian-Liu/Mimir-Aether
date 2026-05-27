# P3-XSR-03 closeout — L3 semantic RAG prefetch (flag, default off)

> **Grain:** P3-XSR-03  
> **Baseline:** `c3dfdc0` (P3-XSR-02 L2)  
> **Date:** 2026-05-27

## Delivered

| Piece | Path |
|--------|------|
| L3 flag | `MIMIR_CROSS_SESSION_RAG` — default **off** (`cross_session_rag_enabled`) |
| Prefetch API | `tools/session_search_tool.session_search_prefetch(..., use_rag=)` |
| L2+L3 merge | `agent/cross_session_retrieval.run_prefetch_search` → same `<retrieved-sessions>` block |
| Unit tests | `tests/agent/test_cross_session_retrieval_l3.py` |
| Contract | `tests/contract/test_horizon_p3_xsr_03.py` |

## Behavior

- **L2 on, L3 off** (`MIMIR_CROSS_SESSION_RAG=0`): unchanged — `session_search()` hybrid path.
- **L3 on** (`MIMIR_CROSS_SESSION_RAG=1`): tries OS-SCH-02 `_session_search_via_fusion` when Chroma + fusion enabled; falls back to L2 `session_search` on empty/failure.
- **Does not** change `SESSION_SEARCH_BACKEND` production default (`hybrid`).

## Out of scope

- ADR-002 MemoryFacade write path (`ENGINE-P3W-01`)
- Capsule text in Chroma index (proposal Phase 2b)

## Verify

```bash
./run_ralph_tier0.sh
pytest -q tests/agent/test_cross_session_retrieval_l3.py tests/contract/test_horizon_p3_xsr_03.py
```
