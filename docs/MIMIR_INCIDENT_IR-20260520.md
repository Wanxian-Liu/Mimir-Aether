# IR-20260520 — Mixin split incident (recovery checklist)

**Trigger:** `bccad39` (E-002/E-003 gateway/agent mixin split) → missing cross-module imports → `NameError` → Recovery **Level 3 TRUNCATE** amplified data loss in **in-memory** `conversation_history`.

**Not the same as d7 (E-004 CLI_CONFIG):** d7 code was still queued; do not mix incident fixes with E-004/E-005 PRs.

## What was lost vs preserved

| Layer | Status | Notes |
|-------|--------|-------|
| `~/.mimiraether/data/sessions/*.jsonl` | Preserved | ~34 files; source for narrative recovery |
| `persistent.json` / soul | Mostly intact | `session_count` may disagree with `cross-session-context.md` |
| In-memory history (active Feishu thread) | **Damaged** | Log showed inject ~58 → 2 on 2026-05-20; not “300 messages in RAM” |
| Tools “100% KeyError: name” | Misleading | Logs: **NameError** + `exec_mixin` logging bug; see `44061e2` |

## Engineering phases

| Phase | Status | Deliverable |
|-------|--------|-------------|
| 1–2 | Done (`44061e2`, `3c8e5a1`) | `_shared.py`, recovery guard, `exec_mixin` `func_name`, command_handlers indent |
| 3 | Done (this batch) | Gate1 mixin imports, `test_recovery_mixin_*`, `test_gateway_mixin_import_smoke`, `SPLIT_PLAN` completion definition |
| 4 | Open | Unify session_count truth; optional jsonl → cross-session summary (no auto-fill `conversation_history`) |
| 5 | Blocked on 1–3 | E-004 `CLI_CONFIG`, E-005 chat decouple, E-008 drop `cli.py` |

## Post-fix verification (human / Mimir)

```bash
# Baseline (should stop growing after fix deploy)
grep -c 'Level 3 TRUNCATE' ~/.mimiraether/logs/agent.log

cd ~/src/MimirAether
MIMIR_AETHER_HOME=~/.mimiraether ./scripts/restart_gateway_hard.sh
```

Then: Feishu `/status` + one message that triggers a tool → confirm `agent.log` has `turn 1: … N tools` and **no** new TRUNCATE on `NameError`.

## References

- HTML report: `~/.openclaw/workspace/mimir-crash-report-2026-05-20.html`
- Wiki commentary (do not edit HTML audits): `docs/MIMIR_D17_WIKI_AUDIT_COMMENTARY.md`
- Mimir smoke tasks: `docs/MIMIR_D17_AUDIT_AND_TASKS.md`
