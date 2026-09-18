# MimirAether — shell activation (repo vs data home)

Use this when you want a repeatable shell session: **code** lives in the git clone; **config, secrets, and `data/`** resolve under **`MIMIR_AETHER_HOME`** (default `~/.mimiraether` when unset).

## Clone 后必做

**（2026-09-18 更新）本步骤已取消 —— 无子模块。** `mimicore` 域于 2026-09-18 归档
（纪念堂仪式：主体解绑 + tag `mimicore-archived-20260918`，本体移至
`~/src/archive/mimicore-prototype/`）⇒ 从远端 clone 后**不需要**、也**不应**执行
`git submodule update --init mimicore`（主仓已无该子模块条目，该命令只会报错）。

历史指令（存档，勿再照做）：~~`git submodule update --init mimicore`~~ —— 归档前用于
拉取 `mimicore` 子模块内容。若你在旧 clone 上仍见到
`ModuleNotFoundError: No module named 'mimicore'`：MimirAether 自 2026-09-18 起**不依赖**
该域，等价实现见 `mimir_cli/model_config/`（2026-09-18 批1 迁移）。CI 侧同样已无子模块步骤
（`docs/CI_SUBMODULE.md` 属历史文档）。防复发：活树里再出现 `import mimicore` 会被
`.mimir-archived-domains.txt` + `scripts/check_scripts_syntax.py` 判红。

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
