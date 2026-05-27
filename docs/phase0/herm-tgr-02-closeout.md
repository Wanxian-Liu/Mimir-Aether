# HERM-TGR-02 closeout — tool cache metrics

**Grain:** `HERM-TGR-02` · Wave 10 Task 2  
**Backlog:** `docs/MIMIR_EXEC_BACKLOG.md` §18.2 / §19.1

## Delivered

- `agent/tool_call_cache.py`: `get_stats()` → `{hits, misses, size}`; `reset_stats()` / `clear_cache()` for tests
- Hit/miss counters on `get_cached()` (cacheable tools only); expired entries count as miss
- `MIMIR_TOOL_CACHE_LOG=1` → single `INFO` line per hit/miss with hit_rate
- Tests: `tests/agent/test_tool_call_cache_metrics.py`, `tests/contract/test_horizon_herm_tgr_02.py`

## Verify

```bash
python3 -m pytest tests/agent/test_tool_call_cache_metrics.py tests/contract/test_horizon_herm_tgr_02.py -q
./run_ralph_tier0.sh
```

## Ops

- Default: metrics in-process only (no log spam)
- Debug: `MIMIR_TOOL_CACHE_LOG=1` on gateway/agent process

## Next

- **HERM-SDH-02** — subdirectory hints in system prompt (`prompt_builder.py`)
