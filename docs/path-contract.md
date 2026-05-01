# Path contract (v1)

Short rules so agent code, gateway, and configs stay aligned. **Update this file** if you introduce a new global path pattern.

## Three roots (do not conflate)

| Layer | What | Typical location / API |
|--------|------|-------------------------|
| **Agent / project home** | Git tree, `config.yaml`, `.env`, `scripts/`, tool caches, logs under this tree | `mimir_constants.get_mimir_home()` — default `~/.openclaw/projects/MimirAether`, override `MIMIR_AETHER_HOME` |
| **Profile layout** | When `HERMES_HOME` points at a profile dir, that path is the active home for resolution; profile siblings live under | `mimir_constants.get_default_hermes_root() / "profiles"` |
| **Platform / OpenClaw config** | `platforms`, merged gateway settings, `api_server` for `/health` | `~/.openclaw/config.yaml` via `load_gateway_config()` — **not** a second product repo |

See also: [gateway-cli-health.md](./gateway-cli-health.md) for `api_server` and cron execution notes.

## PR checklist (path-related changes)

1. No new **`Path.home() / ".hermes"`** (or other hardcoded legacy roots) for agent-visible paths — use **`get_mimir_home()`**, existing config helpers, or env vars already used in-tree.
2. Run **`./run_ralph_tier0.sh`** before merge (matches pre-push / CI Ralph job).

## Intentionally out of scope

- Bulk edits to **`skills/**` / `optional-skills/**`** markdown that still say `~/.hermes` in examples — treat as documentation backlog unless users copy-paste them into production paths.
