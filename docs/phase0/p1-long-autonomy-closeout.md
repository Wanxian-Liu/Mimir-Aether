# P1-LONG-AUTONOMY closeout (§17)

**Date:** 2026-05-26  
**Horizon:** `P1-LONG-AUTONOMY` · backlog §17 AUTO-01～06

## Goal

Make Mimir able to **self-check and recover** within an allowlist (health, eval, optional gateway restart) and **reset polluted Feishu sessions** without treating “empty engineering backlog” as full operational independence.

## Delivered

| ID | What |
|----|------|
| AUTO-01 | `mimir_ops` tool — `health_check`, `evolution_eval`, `gateway_restart` (env `MIMIR_OPS_ALLOW_GATEWAY_RESTART=1` + `confirm=true`) |
| AUTO-02 | `/new`/`/reset` documented in prompt; `mimir_ops(session_reset)` queues pending reset consumed at start of `_run_agent` |
| AUTO-03 | `SESSION_AUTONOMY_GUIDANCE` in `prompt_builder`; history trim via `max_history_length` + compressor (existing) |
| AUTO-04 | `data/ops/last_context_usage.json` written after each model call; `mimir_ops(context_usage)` |
| AUTO-05 | This doc + [`MIMIR_OPS_PANEL.md`](../ops/MIMIR_OPS_PANEL.md) §8 |
| AUTO-06 | `tests/contract/test_horizon_aut_autonomy.py` in tier0 |

## Not in scope (刘哥未授权)

- `MIMIR_AUTO_EVOLVE=1`
- Production default `SESSION_SEARCH_BACKEND=semantic_hybrid`
- Full ADR-002 cross-session inject expansion

## Mimir smoke (human)

1. Feishu: send `/new` → “Session reset!” style reply.
2. Agent: `mimir_ops` `health_check` with `quick=true` → JSON `ok: true` when gateway healthy.
3. After one reply: `mimir_ops` `context_usage` → non-empty `prompt_tokens` when API returns usage.
