# Path contract (v1)

Short rules so agent code, gateway, and configs stay aligned. **Update this file** if you introduce a new global path pattern.

## Three roots (do not conflate)

| Layer | What | Typical location / API |
|--------|------|-------------------------|
| **Git / repo root** | Source tree (`cli.py`, `gateway/`, `scripts/`, tests). Not implied by `get_mimir_home()`. | Your clone (e.g. `~/src/MimirAether`), or **`MIMIR_REPO_ROOT`**, or `$(git rev-parse --show-toplevel)`. |
| **Runtime / data home** | `.env`, `config.yaml`, `gateway.json`, `data/`, tool DBs, logs — **may differ** from the clone | **`mimir_constants.get_mimir_home()`**: `MIMIR_AETHER_HOME` → `MIMIRAETHER_HOME` → `HERMES_HOME` → default **`~/.mimiraether`**. |
| **Profile layout** | When `HERMES_HOME` points at a profile dir, that path is the active home for resolution; profile siblings live under | `mimir_constants.get_default_hermes_root() / "profiles"` |
| **Platform / gateway config** | `platforms`, merged gateway settings, `api_server` for `/health` | **Primary:** `get_mimir_home()/config.yaml` via [`gateway/config.py`](../gateway/config.py) `load_gateway_config()`. Optional legacy OpenClaw files may still exist on disk; new installs should not assume a fixed clone under `~/.openclaw/projects/` (see [`MIMIR_RUNTIME_CONTRACT.md`](./MIMIR_RUNTIME_CONTRACT.md)). |

See also: [gateway-cli-health.md](./gateway-cli-health.md) for `api_server` and cron execution notes.

## Collaboration: git truth vs data home

Avoid confusing **where the code lives** with **where state lives**.

| 做法 | 说明 |
|------|------|
| **提交与推送** | 在**当前 clone 根**执行 `git commit` / `git push` / `./run_ralph_tier0.sh`（与 CI 一致）。路径随机器变化；不要写死某一用户的 `~/.openclaw/...`。 |
| **运行时** | 生产/常驻进程应设置 **`MIMIR_AETHER_HOME`**（及通常 **`HERMES_HOME`** 与之相同），指向你希望存放配置与 `data/` 的目录；默认 **`~/.mimiraether`**。 |
| **其他目录** | 备份或镜像 clone 仅作只读或中转；若有改动，合并回你用于推送的 clone 再推远端。 |
| **问进度时** | 以 [`MAINLINE_STATUS.md`](./MAINLINE_STATUS.md) 为准；阶段 4 勾选见 [`mimir_phase_infinity_checklist.md`](mimir_phase_infinity_checklist.md)；进化价值对照见 [`weave_charter.md`](weave_charter.md)。 |

## `.openclaw` 字面量（`agent/` · `gateway/` · `tools/`）

- **不要**在 `agent/`、`gateway/`、`tools/`（**不含** vendored [`tools/hermes_cli/`](../hermes_cli/)）里新增「无说明的」**唯一默认** `Path.home() / ".openclaw"`；应使用 **`mimir_constants.get_mimir_home()`** / `get_mimir_data_dir()` 等。
- **允许**：迁移文案、注释、正则、技能守卫模式、以及**有注释**的历史兼容分支。新增此类例外时请在 PR 说明意图。
- **非阻断门禁**：[`scripts/warn_openclaw_literals.py`](../scripts/warn_openclaw_literals.py) 在 [`run_ralph_tier0.sh`](../run_ralph_tier0.sh) 末尾统计子串 `.openclaw` 出现次数；超过 **`OPENCLAW_STRING_WARN_THRESHOLD`**（默认 **60**）会向 stderr 打 warning（仍 exit 0）。默认阈值刻意留宽余量，**不**依赖逐条白名单；若需更敏感可在 CI 或本地把该环境变量调低。

## 合并与发版门槛（与 CI 同源）

- **硬门槛**：合并进 `main` / `master` 或与 PR 同源的 CI 前，本地应能通过 [`run_ralph_tier0.sh`](../run_ralph_tier0.sh)（与 [`.github/workflows/ralph.yml`](../.github/workflows/ralph.yml) 一致：Gate1 编译/import、Gate2 指定 pytest、Gate3 E2E、末尾 `.openclaw` advisory）。
- **大合并 / 发版前（可选）**：连续跑 3 次降低偶发环境问题：`for n in 1 2 3; do ./run_ralph_tier0.sh || exit 1; done`（与 [`MAINLINE_STATUS.md`](./MAINLINE_STATUS.md) M0 说明一致）。
- **更宽回归（非阻断）**：手动触发 [`.github/workflows/pytest-wide.yml`](../.github/workflows/pytest-wide.yml)（`agent/` + `gateway/` + `tools/`，排除 vendored `hermes_cli` 与未纳入 tier0 的 `agent/test_integration.py`）。CI 子模块拉取失败时见 [`CI_SUBMODULE.md`](./CI_SUBMODULE.md)。

## PR checklist (path-related changes)

1. No new **`Path.home() / ".hermes"`** (or other hardcoded legacy roots) for agent-visible paths — use **`get_mimir_home()`**, existing config helpers, or env vars already used in-tree.
2. No new unexplained **`Path.home() / ".openclaw"`** defaults under `agent/`, `gateway/`, or `tools/` (excluding vendored `hermes_cli`) — same resolution helpers as above.
3. Run **`./run_ralph_tier0.sh`** before merge (matches pre-push / CI Ralph job).

## Optional skills / bundled scripts

Python under **`skills/**`** and **`optional-skills/**`** should use the same resolution pattern as core code: **`HERMES_HOME`** if set, else **`get_mimir_home()`**, with a small **ImportError** fallback to **`Path.home() / ".mimiraether"`** (matches `mimir_constants` default).

## Skill documentation (`SKILL.md`)

Copy-paste examples in **`skills/**`** and **`optional-skills/**`** should use **`$MIMIR_AETHER_HOME/...`** (or `~/.mimiraether/...` when illustrating defaults), not a fixed user clone path. Shell snippets should still prefer **`HERMES_HOME`** when profile installs matter.

## Runtime entry: `mimcore` vs `mimicore`

| 包 / 目录 | 谁在用 | 说明 |
|-----------|--------|------|
| [`mimcore/`](../mimcore/) | **已删除（2026-05-12）** — 薄 shim 已移除；`agent/core_loop.py` 和 `mcp_serve.py` 改为直接从 `mimir_state` 导入 `SessionDB` |
| [`mimicore/`](../mimicore/) | [`cli.py`](../cli.py)、[`api_service.py`](../api_service.py)、技能 `mimiraether-self_evolution`、根目录若干 `run_capsule_*.py` 等 | 历史与测试根路径多；**仅**当某模块被上述主链路 import 且会在「无 `~/.openclaw`」环境执行时，才收敛其默认路径；其余 legacy（如旧项目名测试根）可延后。 |

## Intentionally lower priority

- Ad-hoc notes under **`learnings/`**, **`*_plan.md`**, etc., may lag; align when those docs are next edited.
