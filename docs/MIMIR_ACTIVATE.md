# MimirAether — shell activation (repo vs data home)

Use this when you want a repeatable shell session: **code** lives in the git clone; **config, secrets, and `data/`** resolve under **`MIMIR_AETHER_HOME`** (default `~/.mimiraether` when unset).

## Clone 后必做

从远端 **clone** 或 **浅 clone** 后，在仓库根执行一次（拉取 [`mimicore`](../.gitmodules) 子模块内容；**不**改子模块指针，仅检出当前 superproject 已记录的 commit）：

```bash
git submodule update --init mimicore
```

若未执行，常见现象包括：Python **`ModuleNotFoundError: No module named 'mimicore'`**（或无法从 `mimicore/` 导入），以及 git 报错类似 **`fatal: clone of '…' into submodule path 'mimicore' failed`**（网络 / SSH 权限 / 未配置 host key）或 **`fatal: not a git repository: mimicore/.git`**（目录存在但未完成子模块初始化）。CI 子模块拉取失败时另见 [`CI_SUBMODULE.md`](./CI_SUBMODULE.md)。

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

## CLI entry points (D7-1)

| Entry | Role | Notes |
|-------|------|--------|
| **`mimir …`** | **Preferred** | Installed/console script → `mimir_cli.main`; `mimir chat` uses `mimir_cli.chat_runner` (not `cli.main`). |
| **`python cli.py …`** | Legacy | Monolithic router in repo root; still used for some subcommands. **Do not** add new features here — extend `mimir_cli` instead. |
| **`python -m mimir_cli.main`** | Dev | Same as `mimir` when run from repo root with `PYTHONPATH` / editable install. |

Chat one-shot: `mimir -q "task"` or `mimir chat -q "task"`. Interactive: `mimir` or `mimir chat`.

See also: [`path-contract.md`](./path-contract.md), [`MIMIR_RUNTIME_CONTRACT.md`](./MIMIR_RUNTIME_CONTRACT.md).
