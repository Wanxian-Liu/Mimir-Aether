# MimirAether — HTML 记忆路径契约（理清期 · 目标态）

| 字段 | 值 |
|------|-----|
| **状态** | **目标态契约**（理清期）；**不含实现** |
| **依据** | [`MIMIR_CLARIFY_BASELINE.md`](./MIMIR_CLARIFY_BASELINE.md)（T01）、[`path-contract.md`](./path-contract.md)、负责人裁定（HTML 真源；OpenClaw/weavevault 零部署） |
| **后续** | T06（胶囊改 HTML + `mimircore_tool`）、wiki/obsidian 技能与 `config.yaml` 对齐 |

---

## 1. 范围与非目标

### 1.1 范围

- 定义 **理清期** 记忆与可积累知识的**目录布局**、**文件格式真源**（HTML）、与 **`MIMIR_AETHER_HOME`** 下配置键的**目标映射**。
- 与 [`path-contract.md`](./path-contract.md) 三根（git 根 / 数据根 / profile）**对齐**；记忆库为数据根下的**第四逻辑根**（见 §2）。
- 供 wiki、Obsidian、mimicore 胶囊链在后续任务中**引用同一契约**，避免再出现 T01 §3.3 的路径分裂。

### 1.2 非目标

- **不写** Python/网关实现、不修改 `tools/`、`agent/`、`gateway/`（属 T06 及后续 PR）。
- **不迁移** `~/.openclaw/projects/MimirAether` 或任何 OpenClaw 磁盘树；**不部署** OpenClaw / **weavevault**（仓库内亦无 weavevault 真源，见 T01 §5）。
- **不**在本契约中宣称 Hermes Parity、Evolution 或 MAINLINE 里程碑已达成（见 §7）。
- **不**规定 HTML 转换器、模板引擎、全文检索实现细节（仅最小页面约定，见 §3）。

### 1.3 负责人已定原则（契约边界）

| 原则 | 契约含义 |
|------|----------|
| **HTML 真源** | 可长期积累、可链接、可检索的**知识页**以 `.html` 为 canonical（§3）。 |
| **OpenClaw / weavevault** | **仅借鉴**产品与流程概念；**零部署**、零路径依赖、零默认真源。 |
| **飞书等平台密钥** | **仅** `$MIMIR_AETHER_HOME/.env`（及契约允许的 `config.yaml` 非密钥项）；不得写入 git 根或 `memory/` 树内页面。 |

---

## 2. 三根目录关系（与 path-contract 对齐）

| 根 | 解析 | 存放内容 |
|----|------|----------|
| **Git / 仓库根** | `$(git rev-parse --show-toplevel)` / **`MIMIR_REPO_ROOT`** | 源码、`gateway/`、`agent/`、`skills/`、**git 子模块** `{repo}/mimicore/`（**代码**与过渡归档，见 §5）、测试与 Ralph 门禁。 |
| **运行时数据根** | **`MIMIR_AETHER_HOME`**（默认 `~/.mimiraether`，`get_mimir_home()`） | `.env`、`config.yaml`、`data/`（会话/网关状态）、`logs/`、**`memory/`（记忆库根）**、契约目标下的 **`mimicore/`（数据根副本）**。 |
| **记忆库根** | **`$MIMIR_AETHER_HOME/memory/`** | **本契约定义的 HTML 知识真源树**（胶囊、wiki、索引）；与 `data/` **并列**，不混放密钥与原始运行时 JSON。 |

**禁止混淆**（延续 path-contract）：

- 不得将 `{repo}/mimicore/public/` 或 `~/.openclaw/projects/MimirAether` 当作记忆真源。
- 不得将 `data/persistent.json` 当作 wiki/胶囊的正文存储（见 §4.4）。

---

## 3. HTML 真源规则

### 3.1 Canonical 格式

| 内容类型 | Canonical | 非 canonical（允许存在的位置） |
|----------|-----------|--------------------------------|
| 胶囊（mimicore 产出） | **`memory/capsules/*.html`** | 子模块或过渡区的 `*.md`（§5，只读归档） |
| llm-wiki 编译页 | **`memory/wiki/**/*.html`** | `memory/wiki/_drafts/**/*.md`（导入中间态，见下） |
| 跨页知识、实体/概念页 | **`memory/wiki/`** 下分层目录中的 `*.html` | 同上 |
| 会话压缩、网关状态 | **`data/*.json`**、**`data/*.md`**（运行时） | 不升级为 HTML 真源；见 §4.4 |

### 3.2 Markdown 地位

- **Markdown 仅作导入中间态**：允许存在于 `memory/wiki/_drafts/`、外部剪藏流程或一次性迁移暂存区。
- **入库条件**：进入 `memory/capsules/` 或 `memory/wiki/` 下**非 `_drafts`** 路径前，**必须**转换为 HTML；转换后 MD 可删除或移至 `_drafts/archive/`（实现细节留 T06+，契约只要求「canonical 仅 HTML」）。

### 3.3 最小 HTML 约定（理清期）

每个 canonical 页**至少**满足：

1. **`<title>`**：人类可读标题（与索引、工具列表一致）。
2. **`<meta>`（`name` 以 `mimir-` 为前缀）**，建议最小集：
   - `mimir-kind`：`capsule` | `wiki-entity` | `wiki-concept` | `wiki-index` | …
   - `mimir-id`：稳定 ID（与 mimicore capsule id 或 wiki 页 slug 对齐）
   - `mimir-created` / `mimir-updated`：ISO-8601
   - `mimir-source`：可选（如 `mimicore`、`llm-wiki-import`）
3. **页间链接**：正文内引用其它 canonical 页时使用 **相对路径** `<a href="...">`（便于整树迁移与离线浏览）。
4. **索引**：`memory/index.html` 为记忆库入口；`memory/wiki/index.html` 为 wiki 分区入口（可自动生成，契约要求路径存在且可链出子目录）。

**不强制**完整 CSS/JS；允许极简 HTML5 骨架。富样式、模板由 T06+ 实现，不阻塞本契约生效。

---

## 4. 子目录布局（默认一棵树）

**记忆库根**：`$MIMIR_AETHER_HOME/memory/`

```
memory/
├── index.html                 # 记忆库总索引（链到 capsules / wiki）
├── capsules/                  # mimicore / produce_capsule 契约目标产出（*.html）
│   └── …
├── wiki/                      # llm-wiki 编译知识（*.html）；长期替代默认 ~/wiki
│   ├── index.html
│   ├── SCHEMA.html            # 约定页（可由原 SCHEMA.md 转换）
│   ├── _drafts/               # 仅 *.md 中间态；非 canonical
│   ├── raw/                   # 可选：导入原文（html 或 md 暂存）；子目录结构实现期定
│   ├── entities/
│   ├── concepts/
│   └── comparisons/
├── mimicore-runtime/          # 可选：进化反馈等（若与 capsules 分离）；默认可省略，见 §5
└── README.html                # 可选：给人看的契约摘要（非必须）
```

### 4.1 各目录职责

| 路径 | 职责 |
|------|------|
| **`memory/capsules/`** | **mimicore 胶囊** canonical 落点（HTML）。工具 `list_capsules` / `get_capsule_by_id` 的契约扫描根（T06 改扩展名与路径）。 |
| **`memory/wiki/`** | **llm-wiki** 编译知识；契约目标替代技能默认的 **`~/wiki`**（§6）。 |
| **`memory/wiki/_drafts/`** | 仅 Markdown 草稿；**不得**被 agent 当作长期真源读取。 |

### 4.2 Obsidian 策略（写死：与 wiki 同根）

**不**单独设立 `memory/obsidian-export/` 第二棵树。

- **契约目标**：`OBSIDIAN_VAULT_PATH` 与 `skills.config.wiki.path` **均指向** `$MIMIR_AETHER_HOME/memory/wiki`（同一目录）。
- **人类用 Obsidian 打开该路径时**：仅将 `memory/wiki/_drafts/**/*.md` 视为可编辑草稿；**canonical 仅 `*.html`**，Obsidian 对 HTML 的编辑若发生，须经「导入 → 转 HTML → 写入非 `_drafts` 路径」流程（实现留后续；契约禁止把 Obsidian 内 MD 直接当生产真源）。

### 4.3 与 `data/` 的关系

| 现有路径（T01） | 契约态度 |
|-----------------|----------|
| **`data/persistent.json`** | **保留** — 运行时/agent 结构化状态；**非** HTML 记忆真源；不强制迁入 `memory/`。 |
| **`data/cross-session-context.md`** | **保留** — 跨会话压缩上下文；**只读参考**可链向 `memory/`，但**不**升级为 wiki/capsule 真源。 |
| **`data/episode_aggregation.jsonl`** 等 | **保留** — 日志型/聚合型；与 `memory/` 分离。 |
| **`data/logs/`** vs **`logs/`** | 沿用现状；**不在本契约合并**（运维见 `OPERATIONS_GATEWAY.md`）。 |

**逐步迁**：若某字段已在 `persistent.json` 中重复存储「长文知识」，理清期**不自动双写**；待 T06+ 显式迁移任务将正文迁入 `memory/**/*.html` 后，JSON 仅留指针（`mimir-id` / 相对路径）。

---

## 5. mimicore 路径（对齐 T01 §3.3）

### 5.1 目标态

| 项 | 契约目标 |
|----|----------|
| **`MIMIR_CORE_PATH`（或 `MIMIR_CORE_ROOT`）默认** | **`$MIMIR_AETHER_HOME/mimicore`**（数据根下的 **代码 + 运行时** 树，可与 git 子模块 **同版本** 同步安装） |
| **胶囊 canonical 发布** | **`$MIMIR_AETHER_HOME/memory/capsules/*.html`**（不再以 `{repo}/mimicore/public/*.md` 为真源） |
| **Python import** | 实现期应保证 `import mimicore.*` 解析到 **数据根或 repo 子模块之一**，且与发布目录一致（T06）；本契约只要求**默认意图**在数据根。 |

### 5.2 现状差距（T01 摘要）

- 文档/代码默认 `get_mimir_home()/mimicore`，本机 **数据根下该目录不存在**。
- 子模块 **`{repo}/mimicore/public/*.md`** 有历史胶囊；**`list_capsules` 扫描数据根 → 返回 0**。
- `agent/`、`gateway/` **不** import mimicore；胶囊链在 `tools/mimircore_tool.py`。

### 5.3 过渡策略（写死，仅契约）

**选用：「发布与索引只认数据根；子模块 `public/` 只读归档」**

| 规则 | 说明 |
|------|------|
| **新写入** | 理清期起，**契约上**仅承认写入 `$MIMIR_AETHER_HOME/memory/capsules/`（HTML，T06 起）及 `$MIMIR_AETHER_HOME/mimicore/`（代码/配置）；**禁止**将 `{repo}/mimicore/public/` 作为新胶囊真源。 |
| **历史 `{repo}/mimicore/public/*.md`** | **只读归档**；可一次性导入到 `memory/capsules/`（转 HTML）或 `memory/wiki/_drafts/`（MD 中间态），**导入脚本属 T06/单独 chore**，本契约不实现。 |
| **子模块 `{repo}/mimicore/`** | 仍为 **git 源码** 与 Ralph/开发检出；与数据根 `mimicore/` **可并存**，但**运行时发布目录**以数据根为准。 |

**验收标准（契约级，供 T06 与负责人验收）**

1. 存在目录 **`$MIMIR_AETHER_HOME/memory/capsules/`** 且至少一份 **`*.html`** 为 canonical 样本（或负责人签署「导入完成」）。  
2. **`$MIMIR_AETHER_HOME/mimicore/`** 存在且 `import mimicore.capsule_generator` 解析路径**优先**数据根（或与 repo 子模块版本 pin 一致，文档记录在 `config.yaml`）。  
3. 等价于 `list_capsules` 的工具/脚本**仅扫描** `memory/capsules/*.html`，在导入或新发布后 **total ≥ 1**（不得再依赖空的数据根 `mimicore/public`）。  
4. **`{repo}/mimicore/public/`** 无新文件 mtime 晚于契约生效日（归档只读；以负责人抽查或 CI 可选检查为准）。

---

## 6. 配置入口映射表

| 能力 | 当前入口（T01 / 技能） | 契约目标 env / yaml 键 | 契约目标路径 |
|------|------------------------|-------------------------|--------------|
| 运行时数据根 | `MIMIR_AETHER_HOME` / `get_mimir_home()` | 同左 | `~/.mimiraether`（默认） |
| llm-wiki 知识库 | `skills.config.wiki.path` in `config.yaml`；默认 **`~/wiki`** | **`skills.config.wiki.path`** | **`$MIMIR_AETHER_HOME/memory/wiki`** |
| Obsidian vault | **`OBSIDIAN_VAULT_PATH`** in `.env`；默认 **`~/Documents/Obsidian Vault`** | **`OBSIDIAN_VAULT_PATH`** | **`$MIMIR_AETHER_HOME/memory/wiki`**（与 wiki 同根，§4.2） |
| mimicore 包根 | **`MIMIR_CORE_ROOT`** env；否则 `get_mimir_home()/mimicore` | **`MIMIR_CORE_ROOT`**（可选覆盖） | 默认 **`$MIMIR_AETHER_HOME/mimicore`** |
| 胶囊列表/发布 | `tools/mimircore_tool` → `MIMIR_CORE_PATH/public/*.md` | （实现键待定，T06）扫描目录 | **`$MIMIR_AETHER_HOME/memory/capsules/*.html`** |
| 飞书 / 模型密钥 | `$MIMIR_AETHER_HOME/.env` | 同左 | **仅数据根 `.env`** |
| 网关 / 平台 | `$MIMIR_AETHER_HOME/config.yaml` | 同左 | 不放入 `memory/` |

**说明**：`HERMES_HOME` 与 `MIMIR_AETHER_HOME` 对齐规则不变（见 [`MIMIR_ACTIVATE.md`](./MIMIR_ACTIVATE.md)）。

---

## 7. 与 MAINLINE 关系

- [`MAINLINE_STATUS.md`](./MAINLINE_STATUS.md) 记录的是 **工程门禁（M0–M6）** 与 **阶段清单（A–∞）** 的**工程裁定**；**不**因本文档自动变更其绿/黄状态。
- 本文档 **不宣称** Parity（Hermes 行为一致）或 Evolution（可证收益）已达成。
- 本文档 **仅** 定义理清期 **记忆 HTML 真源** 与目录契约；实现落地后，应在 MAINLINE 或专项 checklist 中**单独**增加「记忆路径对齐」证据行（由负责人决定，非本文义务）。

---

## 8. 验收（文档完成判据）

负责人阅读本文后，**无需读代码**即可回答：

| 问题 | 契约答案 |
|------|----------|
| 胶囊写哪？ | **`$MIMIR_AETHER_HOME/memory/capsules/*.html`** |
| wiki 写哪？ | **`$MIMIR_AETHER_HOME/memory/wiki/**/*.html`**（索引 `memory/wiki/index.html`） |
| Obsidian 指哪？ | **与 wiki 同根**：`$MIMIR_AETHER_HOME/memory/wiki`；canonical 仍仅 HTML，草稿 MD 仅在 `_drafts/` |
| 扩展名真源？ | **`.html`**（MD 仅 `_drafts` 中间态） |
| 真源在哪一棵树？ | **`$MIMIR_AETHER_HOME/memory/`**（与 `data/`、`logs/` 并列于数据根下） |
| mimicore 代码放哪？ | 默认 **`$MIMIR_AETHER_HOME/mimicore/`**；`{repo}/mimicore` 子模块为开发/归档 |
| OpenClaw / weavevault？ | **零部署**；路径不得作真源 |

**文档自检**：§1–§8 齐全；§4 目录树自洽；§5 过渡策略唯一且含验收标准；§6 映射表覆盖 T01 三项入口。

---

## 相关文档

- [`MIMIR_CLARIFY_BASELINE.md`](./MIMIR_CLARIFY_BASELINE.md) — T01 只读基线  
- [`path-contract.md`](./path-contract.md) — 仓库根 vs 数据根  
- [`MIMIR_ACTIVATE.md`](./MIMIR_ACTIVATE.md) — 环境变量  
- [`SECURITY.md`](./SECURITY.md) — 密钥与 `.env`  
- [`OPERATIONS_GATEWAY.md`](./OPERATIONS_GATEWAY.md) — 网关与日志（非记忆树）
