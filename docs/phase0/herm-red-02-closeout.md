# HERM-RED-02 closeout — ops redact rules

**Grain:** `HERM-RED-02` · Wave 12 Task 7  
**Backlog:** `docs/MIMIR_EXEC_BACKLOG.md` §18.2 / §19.1

## Problem

Built-in `agent/redact.py` patterns are code-only; ops could not extend query-param / JSON-field / custom regex rules without a deploy.

## Delivered

- **`data/redact_rules.json`**: repo template (query params + JSON field extras)
- **`agent/redact_rules.py`**: load/compile/apply; path resolution:
  1. `MIMIR_REDACT_RULES` (explicit file)
  2. `$MIMIR_AETHER_HOME/data/redact_rules.json` when present
  3. repo `data/redact_rules.json`
- **`agent/redact.py`**: `redact_sensitive_text` → built-ins → `apply_loaded_rules`
- Tests: `tests/agent/test_redact_rules.py`, `tests/contract/test_horizon_herm_red_02.py`

## Ops

```bash
cp data/redact_rules.json "$MIMIR_AETHER_HOME/data/redact_rules.json"
# edit JSON; invalid regex entries are skipped with a log warning
# bad JSON → built-ins only (no crash)
```

## Verify

```bash
python3 -m pytest tests/agent/test_redact_rules.py tests/contract/test_horizon_herm_red_02.py -q
./run_ralph_tier0.sh
```

## Gateway

**No hard restart required** for RED-02 alone — rules load on first `redact_sensitive_text` / log format call per process. After editing JSON, restart gateway/agent process to pick up cache (or set `MIMIR_REDACT_RULES` to a new path before start).

If SCR streaming changes are not yet live: do one **Gateway hard restart** before smoke (independent of RED-02).

## Next

- **HERM-CTX-02** — Feishu cross-session smoke
