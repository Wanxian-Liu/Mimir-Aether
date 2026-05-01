# Gateway health checks vs `api_server`

`python3 cli.py gateway health` and status views call **`http://127.0.0.1:18999/health`** (override with `MIMIR_PORT` if you change the bind port).

That HTTP endpoint is served by the **`api_server` platform adapter** (`gateway/platforms/api_server.py`). If **no** platform provides it, the gateway process may still run (e.g. only Telegram/Discord), but **the CLI health check will fail** — that is expected, not necessarily a crash.

## Make health checks pass

1. Edit **`~/.openclaw/config.yaml`** (this is what `load_gateway_config()` reads; not the copy under the project root unless you symlink).
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
