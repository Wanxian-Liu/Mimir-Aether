# OS-TQM-02 closeout — ToolQualityManager default wiring

**Grain:** `OS-TQM-02` · Wave 11 Task 4  
**Backlog:** `docs/MIMIR_EXEC_BACKLOG.md` §18.2 / §19.1

## Three call sites

| Phase | Location | Behavior |
|-------|----------|----------|
| **After tool result** | `execution_pipeline.record_tool_call` → session `ToolQualityManager.record` | Gated by `MIMIR_TOOL_QUALITY` (default **on**) via `start_execution_pipeline` |
| **Before tool selection** | `tools/registry.get_definitions` | `order_tool_names_by_quality` — higher `quality_score` first |
| **Prompt summary** | `build_tool_quality_guidance()` → volatile tier | Degraded tools read-only block when env on |

## Env

- **`MIMIR_TOOL_QUALITY=1`** (default): tracking + prompt + registry ordering
- **`MIMIR_TOOL_QUALITY=0`**: disable all three (contract-tested)

## Verify

```bash
python3 -m pytest tests/agent/test_tool_quality_wiring.py tests/contract/test_horizon_os_tqm_02.py -q
./run_ralph_tier0.sh
```

## Next

- **OS-SCH-02** — session_search BM25 + semantic fusion
