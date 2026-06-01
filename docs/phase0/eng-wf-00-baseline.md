# ENG-WF-00 Baseline Snapshot

**Date**: 2026-06-01
**Git**: `b8c4a12` (TASK_QUEUE §11 [x] · also `a0dc323` for IQ-31/32/33/34)

## Health
- **Status**: `degraded`
- **Gateway**: `ok`
- **Agent**: `degraded`
- **Agent error rate**: 12.5% (above 10% threshold)
- **Tool p50**: 441.9ms / **p95**: 4284.7ms / **p99**: 4284.7ms

## Tier0 (`./run_ralph_tier0.sh`)
- **684 passed**, **4 failed**, 10 warnings, 80.45s
- Known pre-existing failures (cross_session L2/L3):
  - `test_prefetch_uses_objective_query`
  - `test_query_falls_back_to_next_session`
  - `test_build_with_rag_off_matches_l2_search_fn`
  - `test_build_with_rag_on_merged_injection`

## Notes
- Health `degraded` + 12.5% error rate is notable — not yet critical but should be monitored.
- 4 tier0 failures are the same known cross_session L2/L3 set, unchanged.
