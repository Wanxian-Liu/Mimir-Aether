# Path contract (v1)

Short rules so agent code, gateway, and configs stay aligned. **Update this file** if you introduce a new global path pattern.

## Three roots (do not conflate)

| Layer | What | Typical location / API |
|--------|------|-------------------------|
| **Git / repo root** | Source tree (`cli.py`, `gateway/`, `scripts/`, tests). Not implied by `get_mimir_home()`. | Your clone (e.g. `~/src/MimirAether`), or **`MIMIR_REPO_ROOT`**, or `$(git rev-parse --show-toplevel)`. |
| **Runtime / data home** | `.env`, `config.yaml`, `gateway.json`, `data/`, tool DBs, logs — **may differ** from the clone | **`mimir_constants.get_mimir_home()`**: `MIMIR_AETHER_HOME` → `MIMIRAETHER_HOME` → `HERMES_HOME` → default **`~/.mimiraether`**. Legacy env aliases: **[ADR-003](./adr/003-runtime-env-aliases.md)**. |
| **Profile layout** | When `HERMES_HOME` points at a profile dir, that path is the active home for resolution; profile siblings live under | `mimir_constants.get_default_hermes_root() / "profiles"` |
| **Platform / gateway config** | `platforms`, merged gateway settings, `api_server` for `/health` | **Primary:** `get_mimir_home()/config.yaml` via [`gateway/config.py`](../gateway/config.py) `load_gateway_config()`. Optional legacy OpenClaw files may still exist on disk; new installs should not assume a fixed clone under `~/.openclaw/projects/` (see [`MIMIR_RUNTIME_CONTRACT.md`](./MIMIR_RUNTIME_CONTRACT.md)). |

See also: [gateway-cli-health.md](./gateway-cli-health.md) for `api_server` and cron execution notes.

## Observability — execution trace SoT

Per-session **authoritative** tool/agent trace for evolution and post-hoc analysis:

| SoT | Path | API |
|-----|------|-----|
| **ExecutionRecorder JSONL** | `get_mimir_data_dir() / "trajectories" / "<date>" / "<session_id>.jsonl"` | `execution_pipeline.start_execution_pipeline` → `record_tool_call` → `close_execution_pipeline` |

**Not SoT:** `sessions.db` aggregates, `monitor_alerts.json`, Insights metrics, legacy `{repo}/trajectory/*.jsonl`, or `trajectory_samples.jsonl` batch files. Full rules: **[ADR-005](./adr/005-observability-execution-sot.md)** (IEVO-03 / D6-1).

## 历史路径与豁免目录

本节固定：**哪些树可以出现旧机器 / OpenClaw 布局字符串**，以及它们**不是**当前默认真源。新代码与新文档**禁止**从下列区域复制路径当作默认部署根。

### 1) 真源不变述

- **Git / 代码真源**：任意 clone 根；以你执行 `git push` 的仓库根为准（`$(git rev-parse --show-toplevel)` 或 `MIMIR_REPO_ROOT`）。
- **运行时 / 数据真源**：**`MIMIR_AETHER_HOME`**（未设置时默认 **`~/.mimiraether`**），见 `mimir_constants.get_mimir_home()` 与 [MIMIR_RUNTIME_CONTRACT.md](./MIMIR_RUNTIME_CONTRACT.md)。

### 2) 豁免目录与文件（字符串可非零命中；勿当默认抄）

| 路径 | 说明 |
|------|------|
| **`learnings/`**（含子目录） | 历史笔记、迭代记录；可含旧 home / OpenClaw 片段。 |
| **`tasks/`** | 任务/计划快照。 |
| **仓库根 `llms-full.txt`** | 大上下文导出/快照类。 |
| **`archive/`**（含如 `archive/hermes_tasks/`） | 归档材料。 |
| **根目录 `SKILL.md`**（若存在） | 顶层技能说明草稿。 |
| **`evolver_prompt.md`** | 进化/提示实验笔记。 |
| **`MIMIRAETHER_AUDIT_REPORT.md`** | 审计报告类导出。 |

上述区域**不要求**与「运行相关树」同一套 `rg` 零命中门禁；脱敏、整理应使用**单独 chore PR**，勿与功能 PR 混用。

### 3) CI / 门禁范围

- **硬门槛与阻断**：以 **运行相关树** 为准（`agent/`、`gateway/`、`tools/`、`mimir_cli/`、契约测试等；与 [`run_ralph_tier0.sh`](../run_ralph_tier0.sh) / CI 一致）。
- **豁免区**：不要求 `rg` 零命中；也不得把豁免区里的旧路径**反向写回**运行树作为未注释的默认。

### 4) 与 `.openclaw` advisory 的关系

- 仓库末尾 **非阻断** 扫描：[`scripts/warn_openclaw_literals.py`](../scripts/warn_openclaw_literals.py)（由 `run_ralph_tier0.sh` 调用），仅统计 `.openclaw` 子串并 advisory。
- **本任务不**将其改为阻断；若将来要收紧阈值或改扫描范围，须**另开变更单**并与本节、`AGENTS.md` 同步。

### 5) 运行树内保留的 legacy 字面量（须旁注 + 本节登记）

以下文件含 **Historical / legacy layout only** 含义的路径片段，用于**迁移对照、容器内旧布局 remap、sudo 下 home 重映射**，**不是**未设置 env 时的默认数据根：

| 文件 | 用途 |
|------|------|
| [`mimir_cli/paths.py`](../mimir_cli/paths.py) | `openclaw_style_project_root_for_user()`：文档性「历史 clone 布局」`<home>/.openclaw/projects/MimirAether`；与 `openclaw_migration_source_default()`（仅 `~/.openclaw` 迁移源）并列。 |
| [`tools/environments/file_sync.py`](../tools/environments/file_sync.py) | `_remap_credential_container_path`：与 `/root/.hermes` 并列的旧容器根前缀 remap。 |
| [`tools/credential_files.py`](../tools/credential_files.py) | 文档字符串列举旧容器布局示例。 |
| [`mimir_cli/gateway.py`](../mimir_cli/gateway.py) | `_hermes_home_for_target_user` docstring：sudo 下 root→目标用户的**历史** openclaw 风格根对照说明。 |

## Collaboration: git truth vs data home

Avoid confusing **where the code lives** with **where state lives**.

| 做法 | 说明 |
|------|------|
| **提交与推送** | 在**当前 clone 根**执行 `git commit` / `git push` / `./run_ralph_tier0.sh`（与 CI 一致）。路径随机器变化；不要写死某一用户的 `~/.openclaw/...`。 |
| **运行时** | 生产/常驻进程应设置 **`MIMIR_AETHER_HOME`**（及通常 **`HERMES_HOME`** 与之相同），指向你希望存放配置与 `data/` 的目录；默认 **`~/.mimiraether`**。 |
| **其他目录** | 备份或镜像 clone 仅作只读或中转；若有改动，合并回你用于推送的 clone 再推远端。 |
| **问进度时** | 以 [`MAINLINE_STATUS.md`](./MAINLINE_STATUS.md) 为准；阶段 4 勾选见 [`mimir_phase_infinity_checklist.md`](mimir_phase_infinity_checklist.md)；进化价值对照见 [`weave_charter.md`](weave_charter.md)。 |
| **子模块 `mimicore`** | Clone 后须在仓库根执行 `git submodule update --init mimicore`；典型报错与说明见 [`MIMIR_ACTIVATE.md`](./MIMIR_ACTIVATE.md) 小节 **「Clone 后必做」**。 |

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

## Semantic session search (ChromaDB · P2-LONG-SEM)

Per **[ADR-006](./adr/006-semantic-memory-chromadb.md)**:

| Asset | Path / API |
|-------|------------|
| Chroma persist root | `{get_mimir_data_dir()}/chroma_sessions/` unless **`MIMIR_CHROMA_DIR`** |
| Transcript SoT (read) | **`get_mimir_session_search_db_path()`** → `sessions_search.db` (same as LIKE/FTS) |
| Backend switch | **`SESSION_SEARCH_BACKEND`** — default **`hybrid`** (IQ-EVO-11); also `like` / `fts5` / `semantic` / `semantic_hybrid` |
| Chroma incremental | **`MIMIR_CHROMA_INCREMENTAL`** default `1` — upsert on `sessions_search` write (IQ-EVO-11) |
| Eval artifacts | `{get_mimir_data_dir()}/evolution_eval/memory-retrieval-*.json` (extend in SEM-04) |
| Post-close analysis artifacts | `{get_mimir_home()}/data/analysis_artifacts/*.json` when **`MIMIR_AUTO_ANALYSIS=1`** (IQ-EVO-07/13); rollout [`ops/MIMIR_AUTO_ANALYSIS_ROLLOUT.md`](./ops/MIMIR_AUTO_ANALYSIS_ROLLOUT.md) |

New code must **not** place chroma data under the git clone or under `.openclaw/projects/`.

## Optional skills / bundled scripts

Python under **`skills/**`** and **`optional-skills/**`** should use the same resolution pattern as core code: **`HERMES_HOME`** if set, else **`get_mimir_home()`**, with a small **ImportError** fallback to **`Path.home() / ".mimiraether"`** (matches `mimir_constants` default).

## Skill documentation (`SKILL.md`)

Copy-paste examples in **`skills/**`** and **`optional-skills/**`** should use **`$MIMIR_AETHER_HOME/...`** (or `~/.mimiraether/...` when illustrating defaults), not a fixed user clone path. Shell snippets should still prefer **`HERMES_HOME`** when profile installs matter.

## Runtime entry: `mimcore` vs `mimicore`

| 包 / 目录 | 谁在用 | 说明 |
|-----------|--------|------|
| [`mimcore/`](../mimcore/) | **已删除（2026-05-12）** — 薄 shim 已移除；`agent/core_loop.py` 和 `mcp_serve.py` 改为直接从 `mimir_state` 导入 `SessionDB` |
| [`mimicore/`](../mimicore/) | [`cli.py`](../cli.py)、[`api_service.py`](../api_service.py)、技能 `mimiraether-self_evolution`、根目录若干 `run_capsule_*.py` 等 | 子模块路径真源：**[`adr/004-mimicore-openclaw-boundary.md`](./adr/004-mimicore-openclaw-boundary.md)** · `mimicore/mimir_paths.py`；tier0 契约 `tests/contract/test_mimicore_openclaw_boundary_ind04.py` |

## Intentionally lower priority

- Ad-hoc notes under **`learnings/`**, **`*_plan.md`**, etc., may lag; align when those docs are next edited.（历史路径豁免见上文「历史路径与豁免目录」。）
