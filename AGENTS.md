# Notes for agents and contributors

## Progress inquiries

When the user asks for **进度 / 主线 / 完成度** (or similar):

1. **Read** **`docs/MAINLINE_STATUS.md`** first.
2. Refresh it from current repo truth (milestones, growth stages, optional `./run_ralph_tier0.sh` if relevant).
3. Set **最近更新** to today and append a one-line **更新日志** entry if anything changed.
4. Reply with a concise summary; the file is the durable snapshot the user can diff over time.

## Direction (do not drift)

Read **`docs/DEVELOPMENT_NORTH_STAR.md`** before large changes: **Parity** (Hermes-aligned behavior with evidence) and **Evolution** (measurable gain + regression). It scopes this repo vs isolated clones and links the Ralph contract, migration lossy points, and the three gates.

## Repository vs runtime data

Do **not** conflate the **git checkout** (code) with **`MIMIR_AETHER_HOME`** (persistent config, `.env`, `data/`, logs).

| Concept | Typical resolution |
|--------|---------------------|
| **Git / repo root** | Whatever directory holds this repository (e.g. `~/src/MimirAether`). Use `git rev-parse --show-toplevel` or set **`MIMIR_REPO_ROOT`** for scripts that must `cd` before running `cli.py`. |
| **Runtime / data home** | **`MIMIR_AETHER_HOME`** (or `MIMIRAETHER_HOME` / `HERMES_HOME` per `mimir_constants`). Default when unset: **`~/.mimiraether`** — see `mimir_constants.get_mimir_home()` and `docs/path-contract.md`. |

After a fresh clone, run **`git submodule update --init mimicore`** from the repo root (see **`docs/MIMIR_ACTIVATE.md`** section **「Clone 后必做」**); do not bump the submodule pointer unless you intend to ship a submodule change.

Commits, pushes, and `./run_ralph_tier0.sh` run from **your active clone** (the repo root Cursor opened). Older checkouts under `~/.openclaw/projects/` may still exist as copies; reconcile or push from there **before** treating them as obsolete.

**Cursor:** Open the **clone root** as the workspace so the sandbox may write under the repo (including `docs/evolution_log.md` from `./scripts/record_m6_evolution.sh`). If a command must modify paths **outside** the workspace (e.g. under `$MIMIR_AETHER_HOME`), run it **without** the sandbox (e.g. tool permission `all`) for that step only.

## Paths and config

Follow **`docs/path-contract.md`**: agent home vs profile roots, `.openclaw` literal rules under `agent|gateway|tools`, and the tier0 advisory script (`OPENCLAW_STRING_WARN_THRESHOLD`, default 60 — loose on purpose; tighten via env only if you want stricter drift detection). **历史路径豁免**见 `docs/path-contract.md` 小节「**历史路径与豁免目录**」；新代码勿从 `learnings/`、`llms-full.txt`、`archive/` 等豁免区抄部署路径当作默认真源。Avoid ad-hoc home-dir logic in new code.

For **standalone / de-platformed** runs, set **`MIMIR_AETHER_HOME`** (and align **`HERMES_HOME`**) per **`docs/MIMIR_RUNTIME_CONTRACT.md`**.

Gateway ops checklist (start, logs, human smoke, systemd notes — no secrets): **`docs/OPERATIONS_GATEWAY.md`**.

## Security (self-hosted)

- **Overview** (threat boundary, `api_server` bind/key rules, adapters, skills install / `--force`, secrets): **`docs/SECURITY.md`**.
- **API server**: default loopback; non-loopback requires strong **`API_SERVER_KEY`**; loopback without key = no auth for local HTTP — see SECURITY §2 and [`gateway/platforms/api_server.py`](../gateway/platforms/api_server.py).
- **Skills**: `mimir skills install` uses quarantine + **`tools/skills_guard`** + **`INSTALL_POLICY`**; treat **`--force`** as human-gated only.
- **Skills 增删治理**：真源 **`docs/skills/SKILLS_POLICY.md`**。Agent 删 bundled 技能前必须 **`skill_view('mimiraether-skill-prune')`**（禁止盲目 `rm` / 批量 `skill_manage(delete)`）。增改见 **`mimiraether-skill-solidify`**；触发意识见 **`mimiraether-tool-triggers`** §skill_prune。
- **Secrets**: keep **`$MIMIR_AETHER_HOME/.env`** out of git; align env with [`MIMIR_RUNTIME_CONTRACT.md`](./MIMIR_RUNTIME_CONTRACT.md) / [`MIMIR_ACTIVATE.md`](./MIMIR_ACTIVATE.md).

## Ralph mode (strict iteration)

When **Ralph 模式** is requested: follow **`docs/RALPH_MODE.md`** — iterate in the sandbox with **`./run_ralph_tier0.sh`**, log each round (问题 → 修复 → 验证), and require **3 consecutive** full passes with zero failures before calling the task done.

## Merge gate

Before pushing, **`./run_ralph_tier0.sh`** must pass (repository pre-push hook runs the same checks). After a green run, the hook may print an **M6 reminder** if you changed `agent/` / `gateway/` / `tools/` / contract tests but not `docs/evolution_log.md` — see **`docs/M6_EVOLUTION.md`**. Optional wider pytest (not a merge gate): **Actions → Pytest wide (optional)** or **`docs/CI_SUBMODULE.md`** if Ralph CI fails on submodules.

## M6 — evolution audit (minimal)

For changes that touch **agent / gateway / tools / parity tests**, append one row to **`docs/evolution_log.md`** before merging (or immediately after, same commit if squashed). Prefer:

```bash
./scripts/record_m6_evolution.sh "what changed; metrics or metrics: n/a"
```

Rules and template: **`docs/M6_EVOLUTION.md`**.
