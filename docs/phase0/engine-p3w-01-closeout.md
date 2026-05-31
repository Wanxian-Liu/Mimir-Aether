# ENGINE-P3W-01 closeout — ADR-002 MemoryWriteFacade

> **Grain:** ENGINE-P3W-01 · §20.1 #2  
> **Gate:** **ADR-002-impl** ✅ 2026-05-28（刘哥授权 · `adr-002-impl-gate-brief.md`）  
> **Baseline:** `83f006b` · **Date:** 2026-05-28

## Delivered

| Item | Location |
|------|----------|
| **MemoryWriteFacade** | `agent/memory_write_facade.py` |
| Path A · capsules | `write_capsule_html` · `get_capsules_dir` |
| Path B · persistent | `load_persistent` · `write_persistent_mutator` · `save_persistent_merged` → `persistent_store` |

## Write-path migration

| Call site | Before | After |
|-----------|--------|-------|
| `agent/cross_session_memory.py` `save()` | `persistent_store.save_merged` | `save_persistent_merged` |
| `agent/skill_curator.py` skill_usage / dormant | `persistent_store.load` / `read_modify_write` | `mwf.load_persistent` / `write_persistent_mutator` |
| `tools/mimircore_tool.py` publish | `filepath.write_text` | `write_capsule_html` |

**Allowlist（仍直连 store）：** `agent/persistent_store.py` only · tests may patch store.

**Read-only（未改）：** `prompt_builder` · `cross_session_retrieval` L2/L3 prefetch.

## Tests (tier0)

| Test | Asserts |
|------|---------|
| `tests/agent/test_memory_write_facade_p3w.py` | Capsule write · persistent mutator |
| `tests/contract/test_horizon_engine_p3w_01.py` | Wiring + tier0 registration |

## Gateway ops

**No Gateway restart required** (agent/tools write routing only).

## References

- `docs/phase0/adr-002-impl-gate-brief.md`  
- `docs/phase0/adr-002-write-spike.md` · `docs/adr/002-memory-write-paths.md`  
- `docs/proposals/p3-cross-session-retrieval.md` §6 G3

## Verify

```bash
./run_ralph_tier0.sh
pytest -q tests/agent/test_memory_write_facade_p3w.py tests/contract/test_horizon_engine_p3w_01.py
```
