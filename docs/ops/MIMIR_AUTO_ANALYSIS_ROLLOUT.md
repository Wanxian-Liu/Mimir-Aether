# MIMIR_AUTO_ANALYSIS — production rollout (IQ-EVO-13)

Post-close LLM execution analysis is **opt-in** via environment variable. Wave 2 wired the hook (`agent/post_close_analysis.py`); this document is the **production gate** for turning it on outside staging.

**Do not enable `MIMIR_AUTO_EVOLVE=1` on production as part of this rollout** — that path auto-applies skill suggestions and requires separate human authorization (Gate **C**; see [`iqevo-evolution-gates.md`](../phase0/iqevo-evolution-gates.md) · [`OPERATIONS_GATEWAY.md`](../OPERATIONS_GATEWAY.md) STAB-05).

**Staging (2026-05-26):** After Gate **B**, Liu staging `$MIMIR_AETHER_HOME/.env` may set `MIMIR_AUTO_EVOLVE=1` alongside `MIMIR_AUTO_ANALYSIS=1`. Evidence: [`iqevo-gate-b-closeout.md`](../phase0/iqevo-gate-b-closeout.md). Production hosts must keep `MIMIR_AUTO_EVOLVE=0` until Gate C.

---

## 1. What turns on

| Variable | Values | Effect |
|----------|--------|--------|
| **`MIMIR_AUTO_ANALYSIS`** | `1` / `true` / `yes` | After each agent session close, if the execution pipeline reports **errors** or **degraded tools**, a **background thread** runs LLM analysis (fire-and-forget; does not block the user reply). |
| **`MIMIR_AUTO_EVOLVE`** | (leave **unset** or `0`) | Must stay **off** for IQ-EVO-13. When on, `schedule_post_close_evolution` may apply suggestions to SKILL files. |

**Code entry**: `schedule_post_close_analysis()` from `agent/agent_loop.py` `_close_pipeline` (IQ-EVO-07).

**Artifacts** (always written when analysis runs and a prompt is built):

```text
$MIMIR_AETHER_HOME/data/analysis_artifacts/<YYYYMMDDThhmmss>_<task>.json
```

Each file has `"type": "post_task_analysis"` and the analysis prompt payload.

---

## 2. Prerequisites (before production)

1. **Wave 2 smoke passed** on staging — see [`MIMIR_LIU_CURSOR_BRIDGE.md`](../MIMIR_LIU_CURSOR_BRIDGE.md) §4 · `20260526T135803_…json` class evidence.
2. **`./run_ralph_tier0.sh`** green on the commit you deploy.
3. **`MIMIR_AETHER_HOME`** and **`HERMES_HOME`** point at the runtime data root ([`MIMIR_RUNTIME_CONTRACT.md`](../MIMIR_RUNTIME_CONTRACT.md)).
4. LLM credentials in **`$MIMIR_AETHER_HOME/.env`** (analysis uses `call_llm(task="compression", …)`).

---

## 3. Enable on production (刘哥 / ops)

Edit **`$MIMIR_AETHER_HOME/.env`** (not the git clone unless that *is* your home):

```bash
# IQ-EVO-13: post-close analysis (suggestions + artifacts only)
MIMIR_AUTO_ANALYSIS=1

# Explicitly OFF — do not enable without separate approval
# MIMIR_AUTO_EVOLVE=1
```

Restart Gateway so the process reloads env (from repo root):

```bash
./scripts/restart_gateway_hard.sh
```

Verify health:

```bash
curl -sS "http://127.0.0.1:${GATEWAY_PORT:-18999}/health"
```

---

## 4. Seven-day observation (required)

For **7 calendar days** after enabling on production, review artifacts and logs.

### 4.1 List recent artifacts (repo helper)

From clone root:

```bash
./scripts/list_analysis_artifacts.sh
./scripts/list_analysis_artifacts.sh --days 7
```

Manual equivalent:

```bash
ls -lt "$MIMIR_AETHER_HOME/data/analysis_artifacts/" | head -20
find "$MIMIR_AETHER_HOME/data/analysis_artifacts" -name '*.json' -mtime -7 -print
```

### 4.2 What to check

| Check | Pass criteria |
|-------|----------------|
| Volume | Not zero if you had sessions with tool errors; zero is OK if no errors/degraded tools |
| Hallucination | Spot-check 3–5 JSON files: `suggestions[].target` refers to real tools/skills |
| Latency | No user-visible slowdown (analysis is background) |
| Logs | `grep post_analysis "$MIMIR_AETHER_HOME/logs/gateway.log"` — no crash loops |
| AUTO_EVOLVE | `grep MIMIR_AUTO_EVOLVE "$MIMIR_AETHER_HOME/.env"` must **not** be `1` |

### 4.3 Sample path (staging evidence)

Staging reference artifact (Wave 2 acceptance):

```text
~/.mimiraether/data/analysis_artifacts/20260526T135803_训练模型我们用不上么？.json
```

Production samples should live under the **same relative path** under your production `MIMIR_AETHER_HOME`.

---

## 5. Rollback

1. Remove or comment `MIMIR_AUTO_ANALYSIS=1` in `$MIMIR_AETHER_HOME/.env`.
2. `./scripts/restart_gateway_hard.sh`
3. Existing artifacts remain on disk; no automatic skill rollback (AUTO_EVOLVE was never on).

---

## 6. Related docs

| Doc | Topic |
|-----|--------|
| [`docs/proposals/iq-evo-auto-analysis.md`](../proposals/iq-evo-auto-analysis.md) | Original risk / two-step proposal (IQ-EVO-03) |
| [`docs/path-contract.md`](../path-contract.md) | `analysis_artifacts` path |
| [`docs/OPERATIONS_GATEWAY.md`](../OPERATIONS_GATEWAY.md) | Gateway restart, logs, AUTO_EVOLVE rollback |
| [`docs/MIMIR_EXEC_BACKLOG.md`](../MIMIR_EXEC_BACKLOG.md) §15 | IQ-EVO-13 task row |

---

## 7. BRAIN chain integration (2026-06-01)

The BRAIN autonomy chain (see [BRAIN_AUTONOMY_CHAIN.md](../MIMIR_BRAIN_AUTONOMY_CHAIN.md)) activates the following production env vars:

| Var | Effect |
|-----|--------|
| `MIMIR_FEEDBACK_COLLECTOR=1` | Writes `feedback_events.jsonl` — required by AUTO_EVOLVE |
| `MIMIR_WM_VOE_LEARNING=1` | VoE learning data collection (WM Phase 1) |
| `MIMIR_WM_VOE_REPLAN_CTX=1` | VoE surprise triggers replan with context |
| `MIMIR_INTENT_PREDICTOR=1` | Intent classification + `<intent-context>` injection |

All four were **set in production `.env`** as part of BRAIN-00/01/02. No code change needed.

## 8. Revision log

| Date | Note |
|------|------|
| 2026-06-01 | §7 BRAIN chain integration — FEEDBACK_COLLECTOR + WM + INTENT_PREDICTOR enabled |
| 2026-05-26 | IQ-EVO-13: production rollout gate + 7d artifact contract |
