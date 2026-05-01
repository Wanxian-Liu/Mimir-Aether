# Gateway health checks vs `api_server`

## Single codebase vs two config files

There is **one** MimirAether tree: resolve it with `mimir_constants.get_mimir_home()` (default `~/.openclaw/projects/MimirAether`, overridable via `MIMIR_AETHER_HOME`). That directory is the git project root and where `gateway/`, `cli.py`, and `cron/` live.

Separately, the gateway loads **platform** settings from **`~/.openclaw/config.yaml`** (`gateway/config.py` → `load_gateway_config()`). That file is **not** a second product or repo — it is the OpenClaw-scoped layer for `platforms`, `gateway.json` merge, etc. The project’s own `config.yaml` (under the MimirAether root) is still used by `gateway/run.py` for agent/terminal bridging into env vars; **enabling `api_server` for health checks belongs in `~/.openclaw/config.yaml`**, unless you symlink the two.

---

`python3 cli.py gateway health` and status views call **`http://127.0.0.1:18999/health`** (override with `MIMIR_PORT` if you change the bind port).

That HTTP endpoint is served by the **`api_server` platform adapter** (`gateway/platforms/api_server.py`). If **no** platform provides it, the gateway process may still run (e.g. only Telegram/Discord), but **the CLI health check will fail** — that is expected, not necessarily a crash.

## Make health checks pass

1. Edit **`~/.openclaw/config.yaml`** (this is what `load_gateway_config()` reads; see “Single codebase vs two config files” above).
2. Enable the adapter and align the port with the CLI (default **18999**):

```yaml
platforms:
  api_server:
    enabled: true
    extra:
      host: "127.0.0.1"
      port: 18999
```

3. Restart: `python3 cli.py gateway restart` (or `stop` then `start`).

Local bind on `127.0.0.1` can run without `API_SERVER_KEY`; exposing to a non-loopback interface should use a key (see adapter logs / docs).

## Quick verify

```bash
curl -sS "http://127.0.0.1:18999/health"
python3 cli.py gateway health
```

## Cron jobs

Scheduled jobs in `cron/jobs.json` are **executed from the gateway process** (`GatewayRunner.execute_cron_job` on each tick). A standalone `python3 cli.py cron run` loop only calls `cron.scheduler.tick` **without** a runner — it will log that jobs are due but will **not** run the agent. Keep the gateway up for automatic cron execution.
