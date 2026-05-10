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

## PR checklist (path-related changes)

1. No new **`Path.home() / ".hermes"`** (or other hardcoded legacy roots) for agent-visible paths — use **`get_mimir_home()`**, existing config helpers, or env vars already used in-tree.
2. Run **`./run_ralph_tier0.sh`** before merge (matches pre-push / CI Ralph job).

## Optional skills / bundled scripts

Python under **`skills/**`** and **`optional-skills/**`** should use the same resolution pattern as core code: **`HERMES_HOME`** if set, else **`get_mimir_home()`**, with a small **ImportError** fallback to `~/.openclaw/projects/MimirAether`.

## Skill documentation (`SKILL.md`)

Copy-paste examples in **`skills/**`** and **`optional-skills/**`** use the **default agent home** path `~/.openclaw/projects/MimirAether` (same as `get_mimir_home()` with no overrides). Shell snippets should still prefer **`HERMES_HOME`** when profile installs matter.

## Intentionally lower priority

- Ad-hoc notes under **`learnings/`**, **`*_plan.md`**, etc., may lag; align when those docs are next edited.
