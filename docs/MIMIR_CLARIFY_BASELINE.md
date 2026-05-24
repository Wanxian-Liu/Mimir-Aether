# MimirAether「理清」只读基线审计

| 字段 | 值 |
|------|-----|
| **审计时间（UTC）** | 2026-05-16T06:41:29Z |
| **审计机** | Cursor 工作区所在主机（`linux`） |
| **范围** | 只读；仅新增本文档，未改 agent/gateway/tools 业务逻辑 |
| **方法** | 本机命令 + 仓库内 `grep`；路径均为实测或标明「未测/推断」 |

---

## 1. 真源路径（实测）

| 项 | 实测结果 |
|----|----------|
| **Git 仓库根** | `git rev-parse --show-toplevel` → **`/home/rayliu/src/MimirAether`** |
| **`get_mimir_home()`** | **`/home/rayliu/.mimiraether`**（在**当前 shell** 中 `MIMIR_AETHER_HOME` 已设为该路径时测得） |
| **`get_hermes_home()`** | **`/home/rayliu/.mimiraether`**（与上同） |
| **干净 env 下默认 home** | `env -i` 仅保留 `HOME`/`PATH` 时，`get_mimir_home()` 仍为 **`/home/rayliu/.mimiraether`**（与 `mimir_constants` 默认一致） |
| **仓库根 `.env`** | **`/home/rayliu/src/MimirAether/.env`** — **不存在** |
| **数据根 `.env`** | **`/home/rayliu/.mimiraether/.env`** — **存在**（仅记录键名，无密钥真值）：`MINIMAX_API_KEY`, `DEEPSEEK_API_KEY`, `DEFAULT_MODEL`, `MIMIR_MODEL`, `FEISHU_*`, `TAVILY_API_KEY`, `BAIDU_API_KEY` 等 |
| **数据根 `config.yaml`** | **`/home/rayliu/.mimiraether/config.yaml`** — 存在 |
| **契约** | 与 [`path-contract.md`](./path-contract.md)、[`AGENTS.md`](../AGENTS.md) 一致：**代码在任意 clone 根；运行时数据在 `MIMIR_AETHER_HOME`（默认 `~/.mimiraether`）** |

**说明**：当前会话/进程环境中 `HERMES_HOME` 未单独设置；以 `MIMIR_AETHER_HOME` 为准即可。

---

## 2. 运行进程（实测）

| 项 | 实测结果 |
|----|----------|
| **`gateway/run.py`** | **有**。PID 示例：`558878` — `/usr/bin/python3 /home/rayliu/src/MimirAether/gateway/run.py`（**来自 git 真源 clone**，非 `~/.openclaw/projects/...`） |
| **`openclaw-gateway`** | **未发现** 名为 `openclaw-gateway` 的进程（`pgrep -af openclaw` 仅命中 Cursor sandbox 与其它 `~/.openclaw/skills/...` 脚本，非 MA 网关） |
| **`cli.py gateway start`** | **未测** 是否由 systemd/cron 拉起；当前可见进程为直接 `python3 .../gateway/run.py` |
| **网关状态文件** | **`/home/rayliu/.mimiraether/data/gateway.pid`**、**`gateway_state.json`** 存在（数据根与进程分离） |
| **日志（数据根）** | **`/home/rayliu/.mimiraether/logs/gateway.log`**（约 26KB，本机有写入）；另有 `agent.log`、`errors.log` |

---

## 3. mimicore 触点

**子模块**：仓库内 **`/home/rayliu/src/MimirAether/mimicore`** 存在；`git rev-parse --short HEAD` → **`561aa18`**（子模块已检出）。

**`agent/`、`gateway/`**：**无** `mimicore` 字符串 import（tier0 主路径与网关未直接依赖子模块）。

### 3.1 胶囊链（运行时工具 / 主链路相关）

| 文件 | 用途 |
|------|------|
| `tools/mimircore_tool.py` | `produce_capsule` / `list_capsules` / `get_capsule_by_id` / `improve_capsule`；`MIMIR_CORE_PATH` 默认 `get_mimir_home()/mimicore`；导入 `mimicore.capsule_generator` |
| `agent/core_loop.py` | 启动时 `import tools.mimircore_tool` 注册 mimircore 工具集 |
| `agent/tool_guard.py` | 为 `produce_capsule`、`list_capsules` 等标注风险等级 |
| `run_capsule_*.py`、`run_subagent_capsule.py` | 脚本侧直接 `from mimicore.capsule_generator import ...` |
| `scripts/step3_append_generate_and_evaluate.py` | 胶囊生成批处理 |
| `skills/mimiraether/mimiraether-self_evolution/__init__.py` | `from mimicore.evolve.three_ring_architecture import ThreeRingClosedLoop` |

### 3.2 其它（配置 / CLI / 进化 / 诊断 / ACP）

| 文件 | 用途 |
|------|------|
| `cli.py`、`api_service.py` | `mimicore.config.model_defaults`（模型列表/默认模型） |
| `scripts/smoke_mimir_home.sh` | smoke：`get_model()` |
| `acp_adapter/session.py`、`acp_adapter/server.py` | 配置加载 / 版本号 |
| `activate_self_evolution.py`、`skills/.../mimiraether-self_evolution` | `mimicore.evolve.*` 三环/自驱 |
| `test_fix_2_dangerous_cmd.py`、`test_fix_3_fence.py` | 测试 mimicore mini_agent / gateway 片段 |
| `scripts/diag_capsule.py`、`scripts/fix_capsule.py`、`scripts/aggregator_bridge.py` 等 | 维护/诊断脚本，直接读写 `mimicore/` 树 |
| `tools/delegate_tool.py` | 硬编码相对路径 `../mimicore/config/config.yaml`（仓库内子模块） |

### 3.3 路径不一致（实测，产品层关键）

| 声明/代码 | 实测 |
|-----------|------|
| `mimircore_tool` 文档写 canonical：`{MIMIR_AETHER_HOME}/mimicore/` | **`/home/rayliu/.mimiraether/mimicore` 不存在** |
| 子模块代码实际位置 | **`/home/rayliu/src/MimirAether/mimicore/`**（含 **`public/`**，大量 `*.md` 胶囊） |
| `import mimicore.capsule_generator` | 在本机**可成功**，解析到 **`.../src/MimirAether/mimicore/capsule_generator.py`**（依赖 repo 在 `sys.path` 上，而非数据根） |
| `list_capsules` 扫描目录 | 扫描 **`MIMIR_CORE_PATH/public`** → 本机返回 **`total: 0`**（数据根下无 `mimicore/public`） |

---

## 4. 记忆落盘

### 4.1 胶囊（Mimir-Core / `mimircore_tool`）

| 项 | 实测 / 代码 |
|----|-------------|
| **发布扩展名** | **`*.md`**（`public_dir.glob("*.md")`） |
| **代码声明的发布目录** | `Path(MIMIR_CORE_PATH) / "public"` → 本机为 **`~/.mimiraether/mimicore/public`**（**目录不存在**） |
| **子模块内实际胶囊库** | **`/home/rayliu/src/MimirAether/mimicore/public/*.md`**（本机存在，文件数多） |
| **命名模式** | `{capsule_id前12位}_{标题slug}.md`（见 `produce_capsule` 写文件逻辑） |

### 4.2 技能侧「胶囊」元数据（非 mimicore）

| 项 | 说明 |
|----|------|
| `agent/skill_curator.py` | dormant 技能生成 **`capsule.md`**，目录在 **`skills/`** 树下（`dormant_dir / "capsule.md"`），与 mimicore `public/` **不是同一路径** |

### 4.3 运行时 JSON / 会话数据（数据根）

| 路径（相对 `MIMIR_AETHER_HOME`） | 说明 |
|----------------------------------|------|
| `data/persistent.json` | 存在（本机约 18KB） |
| `data/episode_aggregation.jsonl` | 存在 |
| `data/cross-session-context.md` | 存在 |
| `data/logs/` | 存在（与顶层 `logs/` 并存，注意分工） |

### 4.4 llm-wiki / Obsidian 技能配置入口

| 技能 | 配置入口 |
|------|----------|
| **`skills/research/llm-wiki/SKILL.md`** | `skills.config.wiki.path` in **`$MIMIR_AETHER_HOME/config.yaml`**；默认 **`~/wiki`** |
| ~~`skills/note-taking/obsidian`~~ | **已裁**（2026-05-24）；笔记/wiki 用 **`llm-wiki`** 或 `optional-skills`。见 **`docs/skills/SKILLS_POLICY.md`** |

**未测**：本机 `config.yaml` 内是否已配置 `skills.config.wiki.path` / `OBSIDIAN_VAULT_PATH`（未解析 yaml 内容，避免泄露配置细节）。

---

## 5. OpenClaw 关系

| 项 | 实测结果 |
|----|----------|
| **仓库内 `weavevault` 字符串** | **无匹配**（全仓 `grep`，含大小写变体） |
| **`~/.openclaw/projects/MimirAether`** | **存在**（独立目录树，含 `agent/`、`gateway/`、`AGENTS.md` 等；**不是**当前 `git rev-parse` 真源） |
| **与当前运行网关关系** | 运行中网关指向 **`/home/rayliu/src/MimirAether/gateway/run.py`**；OpenClaw 项目目录为**历史/并行 checkout**，勿当作 MA 数据或代码真源（见 [`path-contract.md`](./path-contract.md) §历史路径与豁免目录） |
| **本机其它 OpenClaw 痕迹** | `~/.openclaw/skills/...` 有独立技能仓（如 loki-blueprint），与 MA 仓库无 `weavevault` 耦合 |

---

## 6. 理清对照摘要

[`MAINLINE_STATUS.md`](./MAINLINE_STATUS.md) 记载：**工程 M0–M6 绿**、产品阶段 **A–∞ 绿**（清单/证据链可审计）。本只读审计在**同一台机**上看到的**产品层/路径层差距**如下（供负责人判断「理清」工作量，非否定 tier0）。

| MAINLINE 表述 | 本审计发现（差距） |
|---------------|-------------------|
| 工程里程碑全绿；`run_ralph_tier0.sh` 可过 | **一致**（本次未重跑 tier0，非必须）；门禁不覆盖「双 clone + mimicore 落盘路径」一致性 |
| 真源：clone 根 vs `~/.mimiraether` 已区分 | **部分落地**：进程与 `config.yaml`/`.env` 在数据根；**仍存在** `~/.openclaw/projects/MimirAether` 大型并行树，易误操作 |
| 产品阶段 A：gateway + 飞书 smoke 绿 | **进程实测**：网关来自 **`~/src/MimirAether`**；与 OpenClaw 路径无 `openclaw-gateway` 进程 |
| 阶段 C/∞：学习与自主进化「工程可审计」 | **mimicore 进化**仍散落在 `scripts/`、`activate_self_evolution.py`、技能包；**未**与 `agent/`/`gateway/` 统一 import 图 |
| Parity / Evolution 健康度「强」 | **胶囊记忆**：`list_capsules` 对默认 `MIMIR_CORE_PATH` **返回 0 条**，而子模块 `mimicore/public/` **有内容** — 工具可见性与 MAINLINE「能力已绿」体验不一致 |
| 路径契约：默认 `~/.mimiraether` | **`get_mimir_home()` 实测正确**；**`~/.mimiraether/mimicore` 缺失**，与 `mimircore_tool` 文档 canonical 不一致 |
| 脱钩 OpenClaw（文档叙事） | 仓库**无 `weavevault`**；**无** OpenClaw 平台网关进程名；磁盘上 **OpenClaw 项目镜像仍在** |
| 记忆「宫殿」/ 多源笔记（路线图隐含） | **至少三条入口**：mimicore `public/*.md`、skill_curator `capsule.md`、`llm-wiki`/`obsidian` 外部目录 — **未**在本机验证统一索引或单一真源 |

### 6.1 建议负责人优先澄清的问题（非战略，仅基线）

1. **mimicore 代码与胶囊库**应落在 **git 子模块**、**`$MIMIR_AETHER_HOME/mimicore`**，还是 **仅 env `MIMIR_CORE_ROOT`**？
2. **`~/.openclaw/projects/MimirAether`** 是否只读归档，还是仍会改/部署？与 **`~/src/MimirAether`** 的同步策略？
3. **Agent 工具 `list_capsules` 返回空**是否接受为已知 bug，直至 T06 或路径修复？

---

## 附录：本审计未做事项

- 未部署 OpenClaw / weavevault；未迁移 `~/.openclaw` 数据  
- 未删旧目录；未改网关绑定 / trust 算法 / 胶囊格式  
- 未 commit（按 T01 要求）  
- 未重跑 `./run_ralph_tier0.sh`（可选，非必须）
