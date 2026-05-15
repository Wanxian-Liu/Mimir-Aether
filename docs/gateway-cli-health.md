# Gateway health checks vs `api_server`

For the short **path rules** (git clone vs runtime home vs profiles), see **[path-contract.md](./path-contract.md)** and **[MIMIR_ACTIVATE.md](./MIMIR_ACTIVATE.md)**.

## One codebase, two path roles

- **Repo root** (where `cli.py` / `gateway/` live): your git checkout. Resolve with **`MIMIR_REPO_ROOT`** or `$(git rev-parse --show-toplevel)` when writing scripts.
- **Runtime home** (`mimir_constants.get_mimir_home()`): where **`config.yaml`**, **`.env`**, **`data/`**, and `gateway.json` live. Set with **`MIMIR_AETHER_HOME`** (recommended in production). When unset, the code defaults to **`~/.mimiraether`** — this is **not** required to be the same directory as the clone.

`gateway/config.py` → **`load_gateway_config()`** reads **`get_mimir_home() / "config.yaml"`** (and legacy `gateway.json` beside it). There is **no** separate requirement to edit `~/.openclaw/config.yaml` for normal gateway operation.

`python3 cli.py gateway health` and status views call **`http://127.0.0.1:18999/health`** (override with `MIMIR_PORT` if you change the bind port).

That HTTP endpoint is served by the **`api_server` platform adapter** (`gateway/platforms/api_server.py`). If **no** platform provides it, the gateway process may still run (e.g. only Telegram/Discord), but **the CLI health check will fail** — that is expected, not necessarily a crash.

## Make health checks pass

1. Edit **`$MIMIR_AETHER_HOME/config.yaml`** (or your runtime home’s `config.yaml`; see `get_mimir_home()` above).
2. Enable the adapter and align the port with the CLI (default **18999**):

```yaml
platforms:
  api_server:
    enabled: true
    extra:
      host: "127.0.0.1"
      port: 18999
```

3. Restart: `python3 cli.py gateway restart` (or `stop` then `start`) from the **repo root** (after `cd` / `MIMIR_REPO_ROOT`).

Local bind on `127.0.0.1` can run without `API_SERVER_KEY`; exposing to a non-loopback interface should use a key (see adapter logs / docs).

## Quick verify

```bash
curl -sS "http://127.0.0.1:18999/health"
python3 cli.py gateway health
```

## Cron jobs

Scheduled jobs in `cron/jobs.json` are **executed from the gateway process** (`GatewayRunner.execute_cron_job` on each tick). A standalone `python3 cli.py cron run` loop only calls `cron.scheduler.tick` **without** a runner — it will log that jobs are due but will **not** run the agent. Keep the gateway up for automatic cron execution.

Optional `job["script"]` paths are **relative to `get_mimir_home()/scripts`** — the same root used by `cronjob` tool validation (`tools/cronjob_tools.py`).
