# ENGINE-WS-01 closeout — WebSocket inference activity heartbeat

> **Grain:** ENGINE-WS-01 · Wave 15+  
> **Baseline:** `6aba91f` (P3-XSR-03 + §19.6)  
> **Date:** 2026-05-27  
> **Verdict:** **No new runtime code** — STAB-01 + STAB-06 (2026-05-25, `98a6f6d`) already satisfy this grain.

## Problem (GH #25 / #27 · GATEWAY_STABILITY #1)

Long LLM/tool turns blocked the Feishu Lark **WebSocket worker thread** or left the Gateway **inactivity watchdog** with no `activity` signal → false timeout / WS ping starvation.

## Evidence chain (production paths)

| Layer | Mechanism | Location |
|-------|-----------|----------|
| **WS inbound** | P2 IM dispatch via `asyncio.run_coroutine_threadsafe` — worker returns immediately | `gateway/platforms/feishu_adapter.py` `_sync_p2_im_message_receive_v1` (STAB-01 comment) |
| **Agent turn** | Daemon thread `_activity_heartbeat` every `_ACTIVITY_HEARTBEAT_INTERVAL` (30s) touches activity during blocking `run_async` | `run_agent.py` `AIAgent.run_conversation` |
| **Callbacks** | `_wrap_step_callback` / `_wrap_tool_progress_callback` → `_touch_activity` on iteration + tools | `run_agent.py` |
| **Watchdog consumer** | Poll loop uses `get_activity_summary().seconds_since_activity` vs `HERMES_AGENT_TIMEOUT` | `gateway/agent_mixin.py` `_run_agent` inactivity poll |
| **STAB-06** | Same PR as STAB-01 — semantic alias for WS inference blocking heartbeat | `docs/GATEWAY_STABILITY_BACKLOG.md` · backlog §15 STAB-06 |

## Tests (tier0)

| Test | Asserts |
|------|---------|
| `tests/test_feishu_ws_dispatch.py` | WS handler returns in &lt;0.5s; dispatch async |
| `tests/test_run_agent_activity.py` | Activity API + heartbeat keeps `seconds_since_activity` fresh during slow turn |
| `tests/contract/test_horizon_engine_ws_01.py` | Grain wiring + tier0 registration |

## Gateway ops

**No config change.** **No Gateway restart required** for this closeout (documentation + contract only).

If deploying unrelated gateway changes: hard restart + `curl -s http://127.0.0.1:<port>/health` per `docs/OPERATIONS_GATEWAY.md`.

## References

- `docs/GATEWAY_STABILITY_BACKLOG.md` — #1 Watchdog · #25 WS · STAB-01/06  
- `docs/plans/2026-05-19_stability_sprint.md` — Phase D  
- `docs/superpowers/plans/2026-05-27-horizon-c-master-iteration.md` — ENGINE-WS-01 row

## Verify

```bash
./run_ralph_tier0.sh
pytest -q tests/test_run_agent_activity.py tests/test_feishu_ws_dispatch.py tests/contract/test_horizon_engine_ws_01.py
```
