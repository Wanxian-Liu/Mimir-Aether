# MimirAether — shell activation (repo vs data home)

Use this when you want a repeatable shell session: **code** lives in the git clone; **config, secrets, and `data/`** resolve under **`MIMIR_AETHER_HOME`** (default `~/.mimiraether` when unset).

## Variables

| Variable | Purpose |
|----------|---------|
| **`MIMIR_REPO_ROOT`** | Directory containing `cli.py` (this repo). If unset, scripts may use `git rev-parse --show-toplevel` from the repo tree. |
| **`MIMIR_AETHER_HOME`** | Runtime root: `$MIMIR_AETHER_HOME/.env`, `$MIMIR_AETHER_HOME/config.yaml`, `$MIMIR_AETHER_HOME/data/`, etc. Default when unset: **`~/.mimiraether`**. |
| **`HERMES_HOME`** | Legacy alias: set to the **same path** as `MIMIR_AETHER_HOME` until all call sites converge (`scripts/start.sh` can align these). |

## Example (bash)

From your clone (adjust paths):

```bash
export MIMIR_REPO_ROOT="${MIMIR_REPO_ROOT:-$(git -C ~/src/MimirAether rev-parse --show-toplevel)}"
export MIMIR_AETHER_HOME="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
export HERMES_HOME="$MIMIR_AETHER_HOME"
cd "$MIMIR_REPO_ROOT"
python3 cli.py --help
```

## Dev-only: point data home at the clone

Some contributors keep `.env` and `config.yaml` in the repo root for local work:

```bash
export MIMIR_REPO_ROOT="$(git rev-parse --show-toplevel)"
export MIMIR_AETHER_HOME="$MIMIR_REPO_ROOT"
export HERMES_HOME="$MIMIR_AETHER_HOME"
```

Production-style installs usually keep **`MIMIR_AETHER_HOME`** on a user data path (e.g. `~/.mimiraether`) so the clone can be deleted or replaced without losing state.

See also: [`path-contract.md`](./path-contract.md), [`MIMIR_RUNTIME_CONTRACT.md`](./MIMIR_RUNTIME_CONTRACT.md).
