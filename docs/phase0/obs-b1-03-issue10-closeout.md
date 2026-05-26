# OBS-B1-03 — ISSUES #10 TRUNCATE monitoring closeout

**Date:** 2026-05-26  
**Backlog:** `OBS-B1-03` · Horizon B1 · `P1-LONG-OBS`  
**Issue:** `MIMIR_ISSUES.md` **#10** (Agent TRUNCATE / since-start KPI)

## Decision

**Close #10 as a documented exception** — not a code defect queue item.

| Before | After |
|--------|-------|
| Active **monitoring** | **Archived** — ops KPI only |
| Blocker for “清空” narrative | **Non-blocking** (same as P0 clearance 2026-05-25) |

Root crash path was fixed under **STAB-04** (dual TRUNCATE guard, code-error recovery). Remaining work is **operational measurement**, wired in OBS-B1-02.

## Evidence (2026-05-26)

| Check | Result |
|-------|--------|
| `./scripts/mimir_health_check.sh --quick` | **READY** — R4 since-start **0** (max 10) |
| R3b monitor | `agent=ok` · `rate=0.0` |
| Gateway | PID **326974** · `/health` ok |
| Full-log TRUNCATE count | **63** historical (pre-STAB-04 noise) — **informational only** |

## Ongoing ops (no Active issue row)

| KPI | Mechanism |
|-----|-----------|
| TRUNCATE since gateway start | `mimir_health_check.sh` **R4** · env `MIMIR_TRUNCATE_SINCE_START_MAX` (default **10**) |
| Tool error rate | **R3b** · `MIMIR_MONITOR_ERROR_RATE_THRESHOLD` |
| Runbook | [`docs/ops/MIMIR_OPS_PANEL.md`](../ops/MIMIR_OPS_PANEL.md) §4 |

**Do not** reopen #10 for full-log total increases; triage **since-start** only.

## Active ISSUES after closeout

| # | Status |
|---|--------|
| **3** | `deferred` (ADR-002 memory write paths) |
| ~~10~~ | → archived (this doc) |
| ~~12~~ | → archived (IQ-EVO Wave 1 resolved) |

**Active count:** **1** (≤3 ✅)

## Sign-off

| Role | Action |
|------|--------|
| **Cursor** | Closeout doc + contract `test_horizon_obs_b1_03` + tier0 |
| **Mimir** | Optional: confirm R4 on production host after gateway restart |
