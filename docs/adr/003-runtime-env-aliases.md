# ADR-003: Runtime environment variable aliases

> **Status:** Accepted (2026-05-25)  
> **Scope:** Wave D **IND-01** · D7 partial  
> **Supersedes:** scattered notes in `OPENCLAW_ENV_LEGACY.md` (this ADR is canonical)

---

## Context

MimirAether de-platformed from OpenClaw/Hermes deploy layouts. Production sets **`MIMIR_AETHER_HOME`**; older systemd units and docs still export **`HERMES_HOME`** or **`OPENCLAW_*`**. New code must resolve paths through **`mimir_constants`** so runtime home and git clone never diverge silently.

---

## Canonical home resolution

**Variable:** `MIMIR_AETHER_HOME` (preferred)

**Resolver:** `mimir_constants.get_mimir_home()` — order:

1. `MIMIR_AETHER_HOME`
2. `MIMIRAETHER_HOME` (rename era)
3. `HERMES_HOME` (legacy read — systemd / old deploys)
4. Default `~/.mimiraether` (not the git checkout)

**Data directory:** `get_mimir_data_dir()` → `{home}/data`

---

## Legacy read aliases (sunset TBD 2026-Q3)

| Variable | Read in | Purpose | Replacement |
|----------|---------|---------|-------------|
| `HERMES_HOME` | `get_mimir_home()` fallback | Old unit files set only this | Set `MIMIR_AETHER_HOME` to same path |
| `MIMIRAETHER_HOME` | `get_mimir_home()` fallback | Rename-era installs | `MIMIR_AETHER_HOME` |
| `OPENCLAW_SESSION_DB` | `get_mimir_session_search_db_path()` | Session search SQLite override | **`MIMIR_SESSION_DB`** (IND-03) |
| `OPENCLAW_FTS5_DB` | `session_search_tool._default_fts5_db_path()` | FTS5 index path override | Document only; prefer under `data/` |
| `OPENCLAW_GATEWAY_LOCK_DIR` | `gateway/status.py` `_get_lock_dir()` | Lock dir override | `MIMIR_GATEWAY_LOCK_DIR` or `data/gateway-locks` |
| `HERMES_HOME_MODE` | `mimir_cli/config.py` | Profile mode string | CLI-only; not a path root |
| `MIMIR_AETHER_OPTIONAL_SKILLS` | `get_optional_skills_dir()` | Optional skills tree | Rare override |

**Rule:** Existing readers may keep legacy names with comment `# legacy: ADR-003`. **New features MUST NOT** add new `OPENCLAW_*` readers.

---

## Forbidden in new code (IND-02)

- Using `os.getenv("HERMES_HOME")` or `os.environ.get("HERMES_HOME")` as the **sole** default home root without going through `get_mimir_home()`.
- Defaulting runtime data to `{git_clone}/data/` or `Path.home() / ".openclaw"` without env resolution.
- Writing `persistent.json` outside `get_mimir_data_dir()` (see ADR-001 / IND-05).

**Enforcement:** `tests/contract/test_runtime_path_independence_ind02.py` (tier0).

**Historical allowlist:** path literals in files listed in [`path-contract.md`](../path-contract.md) §5 (migration / container remap only).

---

## Session search DB (IND-03)

**Canonical:** `MIMIR_SESSION_DB` → absolute path to `sessions_search.db`

**Precedence:** `MIMIR_SESSION_DB` > `OPENCLAW_SESSION_DB` (legacy) > `{data_dir}/sessions_search.db`

**Resolver:** `mimir_constants.get_mimir_session_search_db_path()`

---

## Sunset policy

| Milestone | Action |
|-----------|--------|
| 2026-Q3 (target) | Deprecate `OPENCLAW_*` in ops docs; warn on read |
| Post-IND-05 | Single-writer for `persistent.json` (ADR-001) |
| Post-IND-06 | `MIMIR_OPENCLAW_BOUNDARY.md` §8 sign-off |

---

## References

- [`path-contract.md`](../path-contract.md)
- [`OPENCLAW_ENV_LEGACY.md`](../OPENCLAW_ENV_LEGACY.md)
- [`MIMIR_RUNTIME_CONTRACT.md`](../MIMIR_RUNTIME_CONTRACT.md)
- `mimir_constants.py`
