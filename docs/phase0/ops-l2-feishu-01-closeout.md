# OPS-L2-FEISHU-01 closeout — Feishu `/new` L2 prefetch session_key alignment

> **Grain:** OPS-L2-FEISHU-01 · §20.2  
> **Baseline:** `905bfd3`  
> **Date:** 2026-05-27

## Symptom

After Feishu `/new`, system prompt lacked `<retrieved-sessions>` despite `session_prefetch_pending.json` being written (MI-AWAY-08 follow-up).

## Root cause

1. **`build_retrieved_sessions_context()`** resolved session via `_session_key_from_env()` reading only **`HERMES_SESSION_KEY`** from `os.environ`, not **`MIMIR_SESSION_KEY`** / gateway **`get_session_env`** / executor **`get_current_session_key`**.
2. **`run_sync`** set `HERMES_SESSION_KEY` early, then **`load_dotenv(..., override=True)`** could clobber it before **agent init** built the system prompt (prefetch consume runs at init for non-prefix-cache agents).

Evidence note: stale pending keys like `feishu:1` vs runtime `agent:main:feishu:dm:oc_...` were from mismatched manual probes; gateway `/new` queues the full `build_session_key` output.

## Fix

| Piece | Change |
|--------|--------|
| `agent/cross_session_retrieval.py` | `_session_key_from_env()` → `MIMIR_SESSION_KEY` via `get_session_env`, then approval contextvar, then env fallbacks |
| `gateway/agent_mixin.py` | Re-bind `HERMES_SESSION_KEY` + `MIMIR_SESSION_KEY` + `set_current_session_key` **after** dotenv reload, **before** agent cache/init |

## Tests

- `tests/agent/test_cross_session_retrieval_feishu.py` — Feishu-equivalent key + `/new` pending → `<retrieved-sessions>`
- `tests/contract/test_horizon_ops_l2_feishu_01.py`

## Verify

```bash
./run_ralph_tier0.sh
pytest -q tests/agent/test_cross_session_retrieval_feishu.py tests/contract/test_horizon_ops_l2_feishu_01.py
```

## Ops

- **Gateway restart required** (touches `gateway/agent_mixin.py`).
- Feishu repro: `/new` in DM → next user message → logs/context should include `<retrieved-sessions>` when objective/query exists and search returns hits.

## Out of scope

- `SESSION_SEARCH_BACKEND` / `MIMIR_CROSS_SESSION_RAG` production defaults unchanged.
- WM Phase0 / `persistent.json` commit.
