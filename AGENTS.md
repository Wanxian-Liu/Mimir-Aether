# Notes for agents and contributors

## Progress inquiries

When the user asks about **智商 / 进化 / 变聪明** (or Mimir self-improvement direction):

1. **Read** **`docs/MIMIR_IQ_EVOLUTION_DIRECTION.md`** and **`docs/MIMIR_EXEC_BACKLOG.md` §15** (Mimir queue) or **§14** (Cursor SEM engineering).
2. Follow collaboration rules in direction doc **§3** (proposal vs self-dev vs Cursor); no “evolution complete” without measurable evidence.

When the user asks for **进度 / 主线 / 完成度** (or similar):

1. **Read** **`docs/MAINLINE_STATUS.md`** first.
2. Refresh it from current repo truth (milestones, growth stages, optional `./run_ralph_tier0.sh` if relevant).
3. Set **最近更新** to today and append a one-line **更新日志** entry if anything changed.
4. Reply with a concise summary; the file is the durable snapshot the user can diff over time.

## Parallel tasks & delegation (A6 — delegate 习惯化)

> 依据 Multi-Agent Systems Architect 角色卡（Pattern 2/3 核心规则）；验证记录见 `wiki/concepts/Mimir-A6-delegate习惯化报告.md`。

**默认委派，不是可选**：任务满足任一条件 → **默认 delegate_task**：
- 总步骤 >20 步，且可拆分为独立子任务（无共享文件/状态）
- 多个互不依赖的领域需要并行推进

**Fan-out 模式**（Pattern 2 — 独立子任务→并行→合成）：
- 每批 **≤5 个子任务**（>7 超合成质量阈值——角色卡原话）
- 子任务必须真正独立：无共享可变状态、无同文件写冲突
- 合成器显式处理三态：全部成功 / 部分成功 / 全部失败

**Orchestrator 职责**：分解 → 委派 → 合成——**不是执行**（Pattern 3）。你做协调，子代理做事。

**失败处理**：部分子任务失败 → 合成器处理缺失分支，不整体失败；子代理输出带结构化结果 + 置信度信号。

**可观测性**：每次 delegate 调用记录——派了什么（tasks/goals）、结果如何（status/summary/duration）、失败原因；tool_quality DB 为真源。

**反模式**：单步小操作（curl/grep/单文件读）不 delegate——简单任务不触发。

**示例**：
- ✅ 批量补 source（15 张卡）→ `delegate_task(tasks=[3 子任务 × 5 张])` 并行
- ❌ 单步小操作（curl/grep）→ 直接做，不 delegate

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
