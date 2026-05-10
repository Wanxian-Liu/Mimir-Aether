# Path contract (v1)

Short rules so agent code, gateway, and configs stay aligned. **Update this file** if you introduce a new global path pattern.

## Three roots (do not conflate)

| Layer | What | Typical location / API |
|--------|------|-------------------------|
| **Agent / project home** | Git tree, `config.yaml`, `.env`, `scripts/`, tool caches, logs under this tree | `mimir_constants.get_mimir_home()` — default `~/.openclaw/projects/MimirAether`, override `MIMIR_AETHER_HOME` |
| **Profile layout** | When `HERMES_HOME` points at a profile dir, that path is the active home for resolution; profile siblings live under | `mimir_constants.get_default_hermes_root() / "profiles"` |
| **Platform / gateway config** | `platforms`, merged gateway settings, `api_server` for `/health` | **Primary:** `get_mimir_home()/config.yaml` via [`gateway/config.py`](../gateway/config.py) `load_gateway_config()`. Legacy `~/.openclaw/config.yaml` is **not** required when `MIMIR_AETHER_HOME` is set (see [`MIMIR_RUNTIME_CONTRACT.md`](./MIMIR_RUNTIME_CONTRACT.md)). |

See also: [gateway-cli-health.md](./gateway-cli-health.md) for `api_server` and cron execution notes.

## 协作习惯：Git 真源（与 MAINLINE / ∞ 一致）

避免「备份克隆 / 镜像目录」与主开发树分叉后找不到权威历史。

| 做法 | 说明 |
|------|------|
| **唯一提交与推送根** | 使用 **`~/.openclaw/projects/MimirAether`**（本仓库默认 agent home，与 `get_mimir_home()` 一致）做 `git commit` / `git push` / `./run_ralph_tier0.sh`。 |
| **其他目录** | 独立 checkout、同步包、Cursor 另开工作区时，仅作只读或中转；若有改动，**合并回真源树**再推远端（见 [`AGENTS.md`](../AGENTS.md) 首段）。 |
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

Python under **`skills/**`** and **`optional-skills/**`** should use the same resolution pattern as core code: **`HERMES_HOME`** if set, else **`get_mimir_home()`**, with a small **ImportError** fallback to `~/.openclaw/projects/MimirAether`.

## Skill documentation (`SKILL.md`)

Copy-paste examples in **`skills/**`** and **`optional-skills/**`** use the **default agent home** path `~/.openclaw/projects/MimirAether` (same as `get_mimir_home()` with no overrides). Shell snippets should still prefer **`HERMES_HOME`** when profile installs matter.

## Runtime entry: `mimcore` vs `mimicore`

| 包 / 目录 | 谁在用 | 说明 |
|-----------|--------|------|
| [`mimcore/`](../mimcore/) | [`agent/core_loop.py`](../agent/core_loop.py)（`SessionDB`）等 | 薄 shim：自 `hermes_state` / `mimir_constants` / `hermes_cli.config` 再导出；**不**在此处新增 OpenClaw 硬编码路径。 |
| [`mimicore/`](../mimicore/) | [`cli.py`](../cli.py)、[`api_service.py`](../api_service.py)、技能 `mimiraether-self_evolution`、根目录若干 `run_capsule_*.py` 等 | 历史与测试根路径多；**仅**当某模块被上述主链路 import 且会在「无 `~/.openclaw`」环境执行时，才收敛其默认路径；其余 legacy（如旧项目名测试根）可延后。 |

## Intentionally lower priority

- Ad-hoc notes under **`learnings/`**, **`*_plan.md`**, etc., may lag; align when those docs are next edited.
