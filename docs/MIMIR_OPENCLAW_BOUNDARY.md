# MimirAether 与 OpenClaw / weavevault 边界声明

| 字段 | 值 |
|------|-----|
| **状态** | 理清期边界（**仅文档**） |
| **依据** | [`MIMIR_CLARIFY_BASELINE.md`](./MIMIR_CLARIFY_BASELINE.md) §5、[`MIMIR_HTML_MEMORY_CONTRACT.md`](./MIMIR_HTML_MEMORY_CONTRACT.md)、[`path-contract.md`](./path-contract.md)、[`AGENTS.md`](../AGENTS.md) |
| **负责人裁定** | OpenClaw / weavevault **零部署**；MA 记忆真源在 **`$MIMIR_AETHER_HOME/memory/`**（HTML）；飞书等密钥仅在 **`$MIMIR_AETHER_HOME/.env`** |

---

## 1. 一句话边界

**OpenClaw** 是历史平台与**对照环境**（含 `~/.openclaw` 下旧布局、织界/weavevault 等概念）；**MimirAether 真源**仅为：**任意 git clone 根**（源码与 Ralph）+ **`$MIMIR_AETHER_HOME`**（`.env`、`config.yaml`、`data/`、`logs/`）+ **`$MIMIR_AETHER_HOME/memory/`** 下 **`.html` canonical 记忆树**（见 [`MIMIR_HTML_MEMORY_CONTRACT.md`](./MIMIR_HTML_MEMORY_CONTRACT.md)）。二者**不得**混为同一部署根或同一记忆真源。

---

## 2. 禁止清单（执行 / Agent 可读）

以下规则对**协作者、Cursor Agent、运维脚本**均适用；违反即视为偏离理清期边界。

1. **不得**将 **`~/.openclaw`**（及其任意子路径）当作 MimirAether 的**运行时数据根**、**配置根**或**记忆真源**。
2. **不得**在 MimirAether 部署中**安装、启动或依赖** OpenClaw 平台进程（含 `openclaw-gateway` 等）作为 MA 网关的运行时。
3. **不得**部署、挂载、引用或默认使用 **weavevault** 的**代码仓库、数据目录、配置路径**；MA 仓库内**不**新增名为 `weavevault` 的目录、技能包或子模块（T01：全仓无 `weavevault` 字符串，应保持）。
4. **不得**在 MA 仓库 **`skills/`**、**`optional-skills/`** 或 **`agent/`** 中新增**以 weavevault 为运行时依赖**的技能或工具（概念借鉴见 §3，与代码路径无关）。
5. **不得**使用 **`~/.openclaw/projects/MimirAether`**（或等价历史 clone 路径）**启动** MimirAether gateway、写入 `.env`、或作为 `MIMIR_AETHER_HOME`；该树仅作**归档 / 只读对照**（负责人已停用旧飞书等旧路径，**禁止**再从此处拉起生产网关）。
6. **不得**把 OpenClaw 侧「织界 wiki / 库房」路径当作 agent 的**默认读写在途记忆**；读写 canonical 记忆**仅**认 [`MIMIR_HTML_MEMORY_CONTRACT.md`](./MIMIR_HTML_MEMORY_CONTRACT.md) 中的 **`memory/`** 树。
7. **不得**将飞书等平台密钥写入 git clone 根 `.env`、OpenClaw 项目目录或 `memory/` 内 HTML 页面；**仅** **`$MIMIR_AETHER_HOME/.env`**（见 [`SECURITY.md`](./SECURITY.md)）。
8. **不得**在文档、脚本默认示例、未注释代码中，把 **`~/.openclaw/projects/MimirAether`** 写成 MA 的推荐部署根（历史路径豁免区除外，见 [`path-contract.md`](./path-contract.md) §历史路径与豁免目录）。

---

## 3. 允许「借鉴」清单（概念级，无 OpenClaw 路径）

下列为**产品 / 架构思路**借鉴，**不**构成路径、依赖或部署义务；落地时**必须**映射到 MA 契约目录，**不是** OpenClaw 磁盘树。

| 借鉴概念（OpenClaw / 织界语境） | MimirAether 落点（契约） |
|--------------------------------|---------------------------|
| 库房分区、公域/私域分离 | `memory/wiki/` 分层（`entities/`、`concepts/` 等）+ `memory/capsules/`；运行时私域状态仍在 `data/`（见 HTML 契约 §4.3） |
| 可选 enrich、编译入库 | 导入 → **`memory/wiki/_drafts/`**（MD 中间态）→ 转 **HTML** 入库；非 weavevault 管道 |
| 关键词检索 + 语义检索分工 | 实现期在 `memory/` 上建索引；**不**接 OpenClaw 检索服务 |
| 跨页链接、索引页 | `memory/index.html`、`memory/wiki/index.html` 与页间 `<a href>`（见 HTML 契约 §3.3） |
| 胶囊化知识、GDI/发布门槛 | `memory/capsules/*.html` + `$MIMIR_AETHER_HOME/mimicore/`（见 HTML 契约 §5） |
| 迁移对照、行为差异分析 | 文档与 **`optional-skills/migration/openclaw-migration`**（一次性工具，§5） |

**再次强调**：借鉴 **= 设计词汇与流程**；**禁止** 把 OpenClaw 安装目录或 weavevault 数据目录列为 MA 配置默认值。

---

## 4. 路径对照表

| 概念 | OpenClaw（勿用为 MA 真源） | MimirAether 真源 |
|------|---------------------------|------------------|
| **源码 / 开发** | OpenClaw 平台仓库、旧项目镜像 | **`{git clone}`**（`git rev-parse --show-toplevel` / `MIMIR_REPO_ROOT`） |
| **运行时数据** | `~/.openclaw/...`（含历史 `gateway.systemd.env`、平台 config） | **`$MIMIR_AETHER_HOME`**（默认 `~/.mimiraether`；`get_mimir_home()`） |
| **密钥** | OpenClaw 平台 env 文件 | **`$MIMIR_AETHER_HOME/.env`** 仅 |
| **网关配置** | `~/.openclaw/config.yaml` 等 | **`$MIMIR_AETHER_HOME/config.yaml`** |
| **记忆 / /wiki** | weavevault、织界 wiki（OpenClaw 侧实现与路径） | **`$MIMIR_AETHER_HOME/memory/`**（**`*.html` canonical**，见 HTML 契约） |
| **胶囊发布** | OpenClaw 项目内历史 `mimicore/public/*.md` 等 | **`$MIMIR_AETHER_HOME/memory/capsules/*.html`** |
| **旧 MA 代码镜像** | **`~/.openclaw/projects/MimirAether`** | **归档 / 只读**；真源 clone 在 **`~/src/MimirAether`** 等独立路径 |
| **网关进程 cwd** | 从旧 OpenClaw 项目目录启动 | 从 **git clone 根** 启动（如 `python3 {clone}/gateway/run.py`） |

---

## 5. 与迁移技能的关系

| 项 | 说明 |
|----|------|
| **技能位置** | [`optional-skills/migration/openclaw-migration/`](../optional-skills/migration/openclaw-migration/)（含 `scripts/openclaw_to_hermes.py`） |
| **性质** | **一次性迁移 / 对照工具**；用于从 OpenClaw 布局**导出**配置、记忆、技能等到 Hermes/MA 兼容形态；**不是** MA 运行时依赖，**不得**在 gateway 启动路径或 agent 默认工具链中自动加载。 |
| **产物落点** | 迁移得到的**可积累知识**应写入 **`$MIMIR_AETHER_HOME/memory/`**（理清期目标为 HTML；过渡期 MD 仅 `_drafts/`），并更新 **`$MIMIR_AETHER_HOME/.env` / `config.yaml`**；**不得**将 OpenClaw 目录设为迁移后的「主真源」或双向同步源。 |
| **迁移后** | OpenClaw 侧数据**不回流**为 MA 真源；MA 侧变更**不要求**写回 `~/.openclaw`。 |
| **有损点** | 迁移脚本已知有损项见 [`DEVELOPMENT_NORTH_STAR.md`](./DEVELOPMENT_NORTH_STAR.md) §4；迁移完成 **≠** Parity 已达成。 |

---

## 6. 验收

阅读本文 + [`path-contract.md`](./path-contract.md) 后，**新人 / Agent** 应能回答：

| 问题 | 期望答案要点 |
|------|----------------|
| MA 记忆写哪？ | **`$MIMIR_AETHER_HOME/memory/`**，canonical **`*.html`**（[`MIMIR_HTML_MEMORY_CONTRACT.md`](./MIMIR_HTML_MEMORY_CONTRACT.md)） |
| OpenClaw 还能用来干什么？ | **仅**：历史对照、阅读旧树、**一次性迁移**（openclaw-migration）、**概念借鉴**（§3）；**不能**作 MA 运行或记忆真源 |
| weavevault 与 MA 关系？ | **不部署、不共用路径**；无 MA 仓库内 weavevault 真源 |
| 旧路径 `~/.openclaw/projects/MimirAether`？ | **归档 / 只读**；**禁止**从此启动 gateway 或当作 `MIMIR_AETHER_HOME` |
| 飞书密钥放哪？ | **`$MIMIR_AETHER_HOME/.env`** |

**文档自检**：§1–§6 齐全；§2 禁止项可执行；§4 对照表覆盖代码/数据/记忆/旧 clone；与 T02 交叉引用已建立（§1、§2、§3、§4、§6）。

---

## 7. 全量审计结案（2026-05-24 · GitHub #2）

母 issue **#2** 与子项 **#10 / #12 / #13** 已按优先级闭合；运行时默认路径不再指向 `~/.openclaw`。

| 区域 | Issue | 状态 | 证据 |
|------|-------|------|------|
| `tools/` 运行时 5 处 | #10 / #12 | **closed**（PR **#23**） | `code_execution_tool` → `get_mimir_home()`；`skills_guard` 动态 `mimir_paths`；`file_sync` 含 `/root/.mimiraether` remap |
| `mimicore/` ~30 处 | #13 | **closed**（PR **#24** + memory-hall `cbde44b`） | `mimicore/mimir_paths.py` 对齐 `get_mimir_home()` |
| `agent/` · `gateway/` · `tools/` advisory | — | **6 matches**（阈值 60） | [`scripts/warn_openclaw_literals.py`](../scripts/warn_openclaw_literals.py)；均为注释 / 迁移 remap / 历史说明 |
| `mimir_cli/` 迁移 CLI | — | **有意保留** | [`mimir_cli/claw.py`](../mimir_cli/claw.py)、[`paths.py`](../mimir_cli/paths.py)；见 [`path-contract.md`](./path-contract.md) §5 |
| `docs/` · `learnings/` · `optional-skills/migration/` | — | **豁免 / 边界文档** | 见 path-contract §历史路径与豁免目录 |
| Tier-0 门禁 | — | **245+2 PASS** | `./run_ralph_tier0.sh`（2026-05-24） |

**剩余 6 处字面量（运行树，非默认路径）：**

| 文件 | 性质 |
|------|------|
| `agent/prompt_builder.py` | 历史注释 |
| `gateway/hooks.py` | 注释（未启用 hooks） |
| `gateway/session.py` | 注释 |
| `tools/credential_files.py` | docstring 迁移示例 |
| `tools/environments/file_sync.py` | legacy 容器 remap 元组 |

**身份混淆**：根因是硬编码默认路径与 prompt 语境；**LLM 路由不经 OpenClaw**。修复后新环境无 `~/.openclaw` 仍可运行；OpenClaw 仅作迁移源与对照（§5）。

**后续**：勿在 `agent/` / `gateway/` / `tools/` 新增无注释的 `.openclaw` 默认路径；advisory 超阈值时再开 chore issue。

---

## 相关文档

- [`MIMIR_HTML_MEMORY_CONTRACT.md`](./MIMIR_HTML_MEMORY_CONTRACT.md) — 记忆 HTML 真源与 `memory/` 布局  
- [`MIMIR_CLARIFY_BASELINE.md`](./MIMIR_CLARIFY_BASELINE.md) — T01 实测（§5 OpenClaw）  
- [`path-contract.md`](./path-contract.md) — 三根与历史路径豁免  
- [`OPENCLAW_ENV_LEGACY.md`](./OPENCLAW_ENV_LEGACY.md) — 遗留 `OPENCLAW_*` 环境变量  
- [`SECURITY.md`](./SECURITY.md) — 密钥与 `.env`  
- [`AGENTS.md`](../AGENTS.md) — 协作者总则  
