# P3-XSR-01 closeout — cross-session retrieval proposal

**Grain:** `P3-XSR-01` · Wave 14 Task 11  
**Backlog:** `docs/MIMIR_EXEC_BACKLOG.md` §18.2 / §19.1  
**Base:** `6112f38` (post OS-TOOL-SRCH-01)

## Delivered

- **Proposal:** [`docs/proposals/p3-cross-session-retrieval.md`](../proposals/p3-cross-session-retrieval.md)
  - Three-layer injection: L1 core slice / L2 Top-N retrieval / L3 semantic RAG
  - Hermes comparison (`hermes-comparison-detailed.md`)
  - ADR-002 relationship + **G-ADR-002** decision points for 刘哥
- **Contract:** `tests/contract/test_horizon_p3_xsr_01.py`
- **No code** changes to `SESSION_SEARCH_BACKEND` or production defaults

## Verify

```bash
python3 -m pytest tests/contract/test_horizon_p3_xsr_01.py -q
./run_ralph_tier0.sh
```

## Gateway

**No restart required** — documentation only.

## Next

- **刘哥 Gate G-ADR-002** — approve L2/L3 injection scope before implementation
- **ENGINE-GW-01** / icebox or candidate **P3-XSR-02** (L2 pre-fetch) after Gate
