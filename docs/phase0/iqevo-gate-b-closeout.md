# Gate B — staging `MIMIR_AUTO_EVOLVE=1` closeout

**Date:** 2026-05-26  
**Authorization:** 刘哥 — 「staging 开 AUTO_EVOLVE」  
**Policy:** staging `$MIMIR_AETHER_HOME/.env` only · **production `MIMIR_AUTO_EVOLVE` stays 0** until Gate C

---

## B1 — 开前快照

| Item | Evidence |
|------|----------|
| Git tag | `gate-b1-20260526` |
| Skills tarball | `$MIMIR_AETHER_HOME/data/ops/gate-b1-skills-baseline.tar.gz` (~2.2M) |
| Production skills | No `gate-b-pilot-*` under `$MIMIR_AETHER_HOME/skills/` |

---

## B2/B3 — 5× close + suggestion apply (isolated pilot dir)

Script: `scripts/gate_b_auto_evolve_pilot.py`  
Evidence: `$MIMIR_AETHER_HOME/data/ops/gate-b-pilot/gate-b-pilot-evidence.json`

| Metric | Result |
|--------|--------|
| Closes | 5/5 |
| With suggestions | 5/5 |
| SKILL writes (isolated) | 5/5 |
| `evolution_results` success | 5/5 |

Pilot skills only: `$MIMIR_AETHER_HOME/data/ops/gate-b-pilot/skills/gate-b-pilot-{1..5}/SKILL.md`

---

## B4 — 写入质量

All 5 pilot writes are synthetic (`# before N` → `# after gate-b N`). **OK** — no dangerous content; production skills untouched.

---

## B5 — tier0 三连绿（非 sandbox）

`./run_ralph_tier0.sh` × 3 consecutive — **454+2 PASS** each (2026-05-26 ~21:18–21:22 local).

---

## B6 — 行为冒烟

| Check | Result |
|-------|--------|
| `scripts/session_search_usage_baseline.py` | exit 0 → `session_search_baseline_7d.json` |
| `scripts/mimir_health_check.sh --quick` | READY (Gateway PID 400139 at run time) |
| `scripts/run_evolution_eval.sh` | pass → `memory-retrieval-compare-20260526T131747Z.json` |

---

## B7 — 回滚演练

1. Set `MIMIR_AUTO_EVOLVE=0` in `$MIMIR_AETHER_HOME/.env`
2. `./run_ralph_tier0.sh` — **454+2 PASS**
3. No skills restore needed (pilot used isolated dir only)
4. Restored `MIMIR_AUTO_EVOLVE=1` · Gateway hard restart **PID 401777** · `/health` ok

---

## Staging env (runtime, not git)

`$MIMIR_AETHER_HOME/.env` (2026-05-26):

- `MIMIR_AUTO_ANALYSIS=1`
- `MIMIR_FEEDBACK_COLLECTOR=1`
- `MIMIR_AUTO_TUNER=1`
- **`MIMIR_AUTO_EVOLVE=1`** (Gate B pilot; comment documents Gate C for production)

Gateway: `scripts/restart_gateway_hard.sh` after env change.
