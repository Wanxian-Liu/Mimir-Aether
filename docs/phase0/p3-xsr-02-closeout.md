# P3-XSR-02 closeout — L2 cross-session retrieval prefetch

> **Grain:** P3-XSR-02 · Wave 15  
> **Baseline:** `99ac4f1` (G-ADR-002 gate)  
> **Date:** 2026-05-27

## Delivered

| Piece | Path |
|--------|------|
| L2 prefetch module | `agent/cross_session_retrieval.py` |
| Prompt injection | `agent/prompt_builder.py` — `<retrieved-sessions>` after L1 `<cross-session-context>` |
| Queue on `/new` | `gateway/router/session_commands_mixin.py` |
| Queue on ops reset | `gateway/agent_mixin.py` (after `consume_session_reset_pending`) |
| Unit tests | `tests/agent/test_cross_session_retrieval_l2.py` |
| Contract | `tests/contract/test_horizon_p3_xsr_02.py` |

## Behavior

- **Trigger:** One-shot `session_prefetch_pending.json` per `session_key` after `/new` or `session_reset` pending apply.
- **Query:** `progress.current_objective` → else `NEXT_SESSION.md` snippet → else skip L2.
- **Search:** Internal `session_search()` (no tool round-trip); does **not** change `SESSION_SEARCH_BACKEND` default.
- **Caps:** `MIMIR_CROSS_SESSION_RETRIEVAL_MAX_CHARS` (default 2000), session limit 3, messages/session 3.
- **Flag:** `MIMIR_CROSS_SESSION_RETRIEVAL=1` default on; set `0` to disable L2.

## Out of scope (P3-XSR-03+)

- `MIMIR_CROSS_SESSION_RAG` / L3 semantic auto-prefetch
- ADR-002 MemoryFacade write path (`ENGINE-P3W-01`)

## Verify

```bash
./run_ralph_tier0.sh
pytest -q tests/agent/test_cross_session_retrieval_l2.py tests/contract/test_horizon_p3_xsr_02.py
```
