# Mimir 运维面板（Horizon B1 · OBS-B1-02）

Single-page ops reference: **Gateway health**, **monitor thresholds**, **TRUNCATE KPI**, and weekly commands. No new UI — run from clone root with `$MIMIR_AETHER_HOME` set.

**Related:** [`OPERATIONS_GATEWAY.md`](../OPERATIONS_GATEWAY.md) · [`MIMIR_EV_L_INDUSTRIAL_LEARNING.md`](../MIMIR_EV_L_INDUSTRIAL_LEARNING.md) §10 · ADR-005/007 observability SoT

---

## 1. Weekly one-liner（刘哥 / Mimir 周常）

```bash
export MIMIR_AETHER_HOME="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
cd ~/src/MimirAether

./scripts/mimir_health_check.sh --quick
./scripts/list_analysis_artifacts.sh --days 7
MIMIR_AETHER_HOME="$MIMIR_AETHER_HOME" ./scripts/run_evolution_eval.sh
```

**Pass:** `--quick` → **READY** (R2–R4 PASS, R3b monitor PASS); eval script exit 0.

---

## 2. Health probe matrix (`mimir_health_check.sh`)

| ID | What | Pass | Env override |
|----|------|------|----------------|
| **R1** | `./run_ralph_tier0.sh` | exit 0 | — (skipped in `--quick`) |
| **R2** | `gateway/run.py` process | pgrep finds PID | — |
| **R3** | `GET /health` | JSON has `"status":"ok"` | **`MIMIR_PORT`** (default **18999**) |
| **R3b** | Monitor snapshot on `/health` | `agent` ≠ degraded; `agent_error_rate` ≤ threshold | **`MIMIR_MONITOR_ERROR_RATE_THRESHOLD`** |
| **R4** | Level-3 **TRUNCATE since gateway start** | count ≤ max | **`MIMIR_TRUNCATE_SINCE_START_MAX`** (default **10**) |
| **R5** | Feishu tool round-trip | **MANUAL** | — |
| **R6–R10** | mixin / recovery / persistent / log heuristics | see script | full mode only |

**Commands:**

```bash
# Daily / pre-merge (full)
./scripts/mimir_health_check.sh

# Ops quick (no tier0 — ~30s)
./scripts/mimir_health_check.sh --quick

# CI / automation
./scripts/mimir_health_check.sh --json --quick
```

---

## 3. Monitor thresholds (`agent/monitor.py`)

| Constant / env | Default | Meaning |
|----------------|---------|---------|
| **`MIMIR_MONITOR_ERROR_RATE_THRESHOLD`** | `0.10` | Sliding-window tool **failure rate** above this → `/health` **`agent":"degraded"`** and append **`data/monitor_alerts.json`** |
| **`MIMIR_MONITOR_WINDOW_SECONDS`** | `300` | Window for error rate and **P50/P95/P99** tool latency on `/health` |
| (code) `CHECK_EVERY_N_CALLS` | `10` | Evaluate alert file every N tool outcomes |

**`/health` fields** (from `snapshot_for_health()`):

| Field | Example | Notes |
|-------|---------|-------|
| `agent` | `ok` / `degraded` | Derived from error rate vs threshold |
| `agent_error_rate` | `0.042` | Last **window** (default 5 min) |
| `agent_tool_p50_ms` | `140.0` | Tool latency percentiles |
| `agent_tool_p95_ms` | `890.0` | |
| `agent_tool_p99_ms` | `1200.0` | |

**Inspect alerts file:**

```bash
tail -20 "$MIMIR_AETHER_HOME/data/monitor_alerts.json"
```

---

## 4. TRUNCATE KPI（ISSUES #10 — documented exception · OBS-B1-03）

> **#10 closed 2026-05-26** — no Active row; KPI via R4 only. See [`obs-b1-03-issue10-closeout.md`](../phase0/obs-b1-03-issue10-closeout.md).

| Metric | Command | Pass (ops) |
|--------|---------|------------|
| Since last gateway start | R4 inside `mimir_health_check.sh --quick` | ≤ **`MIMIR_TRUNCATE_SINCE_START_MAX`** (default **10**) |
| Legacy full-log count | `grep -c 'Level 3 TRUNCATE' "$MIMIR_AETHER_HOME/logs/agent.log"` | Informational only (historical **63** noise pre-STAB-04) |
| Recovery guard | `grep 'Skipping TRUNCATE/COMPRESS for code error' … \| tail -5` | Code errors must **not** reach TRUNCATE |

**Do not** treat full-log TRUNCATE total as P0; use **since-start** (R4).

---

## 5. Gateway restart + verify

```bash
cd ~/src/MimirAether
MIMIR_AETHER_HOME=~/.mimiraether ./scripts/restart_gateway_hard.sh
./scripts/mimir_health_check.sh --quick
```

---

## 6. Log triage (5 min)

```bash
H="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
tail -30 "$H/logs/agent.log"
grep -E 'Agent error|Level 3 TRUNCATE|ERROR' "$H/logs/agent.log" | tail -15
grep -i timeout "$H/logs/watchdog.log" 2>/dev/null | tail -5 || true
```

---

## 7. Semantic session search（Horizon A · P2-LONG-SEM）

| Step | Command |
|------|---------|
| Backfill Chroma（一次性或修复） | `MIMIR_AETHER_HOME=~/.mimiraether python3 scripts/backfill_chroma_sessions.py` |
| 20-query 基准 | `MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_memory_retrieval_benchmark.py` |
| 周常 eval + 回归门 | `MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh` |

| Env | Default | Notes |
|-----|---------|-------|
| **`SESSION_SEARCH_BACKEND`** | **`hybrid`** | Production: FTS5→LIKE. Optional upgrade: **`semantic_hybrid`** (Chroma→hybrid). |
| **`MIMIR_CHROMA_INCREMENTAL`** | **`1`** | Upsert on `sessions_search` write (IQ-EVO-11). Set `0` to disable. |
| **`MIMIR_EMBED_MODEL`** | (unset → hash) | e.g. `paraphrase-multilingual-MiniLM-L12-v2` for CJK paraphrase; requires `sentence-transformers`. |

Smoke:

```bash
MIMIR_AETHER_HOME=~/.mimiraether SESSION_SEARCH_BACKEND=semantic_hybrid \
  python3 -c "from tools.session_search_tool import session_search; print(session_search('跨会话记忆', limit=3))"
```

Closeout: [`docs/phase0/p2-long-sem-closeout.md`](../phase0/p2-long-sem-closeout.md) · ADR-006.

---

## 8. Agent autonomy (`mimir_ops` · §17)

**Tool:** `mimir_ops` (allowlisted only — no arbitrary shell).

| Action | Purpose | Guards |
|--------|---------|--------|
| `health_check` | Runs `scripts/mimir_health_check.sh --json [--quick]` | — |
| `evolution_eval` | Runs `scripts/run_evolution_eval.sh` | — |
| `gateway_restart` | Runs `scripts/restart_gateway_hard.sh` | `confirm=true` **and** `MIMIR_OPS_ALLOW_GATEWAY_RESTART=1` in `$MIMIR_AETHER_HOME/.env` |
| `context_usage` | Reads `data/ops/last_context_usage.json` + monitor snapshot | Written after each model call |
| `session_reset` | Queues reset for next agent turn | User can also send **`/new`** or **`/reset`** in Feishu |

**Session reset (Feishu):** same chat window keeps one `session_key`; `/new` rotates `session_id` and evicts the cached agent (see `gateway/router/session_commands_mixin.py`).

**Context governance:** in-process history capped at `max_history_length` (default 200 messages); compressor may TRUNCATE when prompt tokens exceed threshold — see `agent/context_compressor.py`.

**Closeout:** [`docs/phase0/p1-long-autonomy-closeout.md`](../phase0/p1-long-autonomy-closeout.md)

---

## 9. Revision log

| Date | Note |
|------|------|
| 2026-05-26 | §17: `mimir_ops` + context_usage snapshot + `/new` docs |
| 2026-05-26 | SEM-07: semantic baseline + eval gate + §7 |
| 2026-05-26 | OBS-B1-02: ops panel + R3b + monitor env overrides |
