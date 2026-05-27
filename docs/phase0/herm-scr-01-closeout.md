# HERM-SCR-01 closeout — streaming think scrubber

**Grain:** `HERM-SCR-01` · Wave 12 Task 6  
**Backlog:** `docs/MIMIR_EXEC_BACKLOG.md` §18.2 / §19.1

## Problem

Per-chunk regex on stream deltas leaks or drops thinking when tags split across chunks (see Hermes §2.17).

## Delivered

- **`agent/think_scrubber.py`**: `StreamingThinkScrubber` (`feed` / `flush` / `reset`) + `strip_think_blocks()` for final content
- **`agent/callers_mixin.py`**: OpenAI-compatible stream path scrubs before `_fire_stream_delta`; EOF `flush()`; `_strip_think_blocks` delegates to scrubber
- Tags: `<think>`, `<thinking>`, `<reasoning>`, `<thought>`, `<REASONING_SCRATCHPAD>`, partial open/close holdback
- Tests: `tests/agent/test_think_scrubber.py`, `tests/contract/test_horizon_herm_scr_01.py`

## Three call sites

| Phase | Location |
|-------|----------|
| Stream | `_stream_openai_compatible` → scrubber.feed → `_fire_stream_delta` |
| EOF | `think_scrubber.flush()` after stream |
| Final | `core_loop` → `_strip_think_blocks` → `strip_think_blocks()` |

## Verify

```bash
python3 -m pytest tests/agent/test_think_scrubber.py tests/contract/test_horizon_herm_scr_01.py -q
./run_ralph_tier0.sh
```

## Gateway

**Hard restart recommended** — touches `callers_mixin` streaming consumed by gateway agent loop.

## Next

- **HERM-RED-02** — redact rules ops
