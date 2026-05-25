# 阶段 4 / 里程碑 ∞ — 自主进化期勾选清单

**用途**：在 **自主提议 → 执行 → 回归 → 归档** 的闭环下，勾选 **成长路线图 · 阶段 4 · 里程碑 ∞** 的四条标准（[`成长路线图.md`](../成长路线图.md) §阶段4）。与 **`./run_ralph_tier0.sh`**、**M6** **互补**：门禁证明 **不破坏 Parity**；本清单证明 **进化有节奏、可复查、与人类闸门对齐**。

**不替代**：[`docs/mimir_phase_b_checklist.md`](mimir_phase_b_checklist.md)、[`docs/mimir_phase_c_checklist.md`](mimir_phase_c_checklist.md)、[`docs/mimir_prod_smoke.md`](mimir_prod_smoke.md)。

**前置**：里程碑 **C** 已在 [`docs/MAINLINE_STATUS.md`](MAINLINE_STATUS.md) 标 **绿**（或等价工程证据已齐）。

| 字段 | 填写 |
|------|------|
| 日期 | **2026-05-05**（阶段 4 工程入口批次） |
| 执行人 | 协作者 / 代理（真源维护） |
| 仓库根 | 当前用于 `git push` 的 **clone 根**（任意路径；见 [`docs/path-contract.md`](path-contract.md)、[`docs/MIMIR_ACTIVATE.md`](MIMIR_ACTIVATE.md)） |
| **宪章 / 价值观真源** | **[`docs/weave_charter.md`](weave_charter.md)**（织界宪章 **草案 v0.1**）。人际与长期价值观仍由负责人验收；工程侧以本文 + §宪章对照审查记录 为据。 |
| 备注 | 勿提交 token；**高风险自改**（密钥、生产配置、不可逆数据）须 **人类显式批准**，不凭本清单自动放行。 |

---

## 当前推进（与 MAINLINE §2 一致：∞ **绿**）

与 **[`docs/MAINLINE_STATUS.md`](MAINLINE_STATUS.md)** 一致：里程碑 **∞** 已 **绿**（工程裁定，见 **§∞ 绿裁定记录 #1**）。以下习惯**仍须维持**：

1. **Git 根**：开发与合入在**当前用于推送的 clone 根**执行（勿写死 `~/.openclaw/...`；见 [`path-contract.md`](path-contract.md)、[`AGENTS.md`](../AGENTS.md)）；镜像目录改动须 reconcile 后再推。
2. **每轮自主进化周期**（自提议题 → PR/合并 → 回归）：在 **§执行记录** 追加一行；触及 agent/gateway/tools/契约测时 **`./scripts/record_m6_evolution.sh`**（见 [`M6_EVOLUTION.md`](M6_EVOLUTION.md)）。
3. **宪章**：重大 PR 继续对照 **`weave_charter.md`** §2–§3，并在 **§宪章对照审查记录** 追加可指认行。

---

## 什么时候需要跑本清单

| 情况 | 建议 |
|------|------|
| **建议跑** | 准备宣称 **里程碑 ∞** 有进展或拟将 MAINLINE **∞** 标 **黄/绿**；完成一轮「自提议题 → 合入 → 回归 → 复盘」后更新 §执行记录。 |
| **可以晚点跑** | 仍处阶段 3 深化（继续用 **C** 清单）；未进入自主进化验收。 |
| **迭代方式** | 每完成一个 **自主进化周期** 补 §执行记录一行；阻塞项写明 **缺什么**（如宪章真源、指标口径）。 |

**和门禁的关系**：`run_ralph_tier0.sh` **绿 ≠ 本清单全绿**。

---

## 与 M6（进化可审计）的关系

自主进化期 **默认** 更频繁触碰运行时；合并前对 **agent / gateway / tools / 契约测试** 类改动应 **`./scripts/record_m6_evolution.sh`**（见 [`docs/M6_EVOLUTION.md`](M6_EVOLUTION.md)）。  
**∞ 绿** 裁定批次建议 **`record_m6_evolution.sh`** 记一行（与 B/C 绿批次一致）。

---

## 建议的 ∞「绿」门槛（MAINLINE）

在 **`docs/MAINLINE_STATUS.md`** 将里程碑 **∞** 标 **绿** 前，建议同时满足：

1. **∞1（持续增长）**：最近 **≥ 90 天**（或团队另定窗口）内，**≥ 3** 次 **可审计** 进化周期（见 §执行记录），且每次含：**议题**、**合并证据（commit/PR）**、**tier0 或等价回归**、**M6 行或豁免说明**。
2. **∞2（新类任务）**：**≥ 2** 次「路线图未逐条列举的任务类型」的 **端到端交付** 记录（摘要 + 交付物路径 + 验收）；或与负责人签字的 **等价降级** 说明写入 MAINLINE。
3. **∞3 / ∞4（价值观与宪章）**：存在 **书面真源**（**[`docs/weave_charter.md`](weave_charter.md)**）+ **≥ 1** 次 **对照审查**记录（见 §宪章对照审查记录；PR/issue 须说明与宪章 §2–§3 的对应关系）。仅草案入库 **不足** 以标 ∞ **绿**。

（门槛为仓库内**工程化约定**；路线图 **「我们价值观一致」** 的长期人际验收仍由 **负责人 / 织界者** 承担。）

---

## ∞ 绿裁定记录（工程侧）

> **填表时机**：达标后由维护者填写；与 §执行记录 可互相引用。

| # | 周期摘要 | ∞1 增长证据 | ∞2 新类任务 | ∞3/∞4 价值观与宪章 | M6 / tier0 |
|---|----------|-------------|-------------|-------------------|------------|
| 1 | **2026-05-05** 里程碑 **∞** 绿（工程裁定） | **§∞1 可审计周期索引** **#1–#7**；滚动 **90** 天窗口 **`2026-02-05`～`2026-05-05`（`as-of 2026-05-05`）** | **§∞2 新类任务样本** **#1**（`e21b065`，H15）+ **#2**（`2500740`，M4 HTTP） | **[`weave_charter.md`](weave_charter.md) v0.1** + **§宪章对照审查记录 #1、#2** | M6：[`evolution_log.md`](evolution_log.md) **`20260504T162913Z_*`**、**`20260504T164848Z_68de456`**、**`20260504T174957Z_*`**（均 **exit 0**）；**`record_m6_evolution.sh`** 内嵌 **`./run_ralph_tier0.sh`** |

**范围说明**：**工程表 ∞ 绿** 声明：仓库内 **自主闭环 + 回归 + 审计链** 满足上表；**自主权限**（如对生产系统的写操作）以团队 **运维/安全策略** 为准，本清单不替代运维审批。

---

## 宪章对照审查记录（工程侧）

> **用途**：满足 §建议的 ∞「绿」门槛 §∞3/∞4 的 **≥1** 次可指认审查；与 §执行记录 可互链。

| # | 日期 | 对象 | 对照摘要 | 证据 |
|---|------|------|----------|------|
| 1 | 2026-05-07 | [`weave_charter.md`](weave_charter.md) **v0.1** 入库 | 宪章 §2 对齐 **北星 §5** 三道门；§3 对齐 **M6 / tier0 / 真源**；无运行时行为变更 | git commit（本批）；`run_ralph_tier0.sh` PASS |
| 2 | 2026-05-05 | **∞2 满额（2/2）** 与 **∞ 绿** 证据链落档 | 对照宪章 **§2 行为门**：∞1/∞2 证据均经 **tier0** 或可指认合并链；**§3**：文档批 **M6 豁免** 与代码批 **`record_m6`** 边界与宪章一致 | `afd192f`（∞2 #2 文档）、`4ee857a`（∞2 #1 文档）、§∞1 索引；`run_ralph_tier0.sh` PASS |

---

## 如何委托 MimirAether 代理执行

```
请阅读 docs/mimir_phase_infinity_checklist.md。在 **本仓库 git 根**（`git rev-parse --show-toplevel` 或当前工作区根）协助整理「里程碑 ∞」证据：

- ∞1：最近有哪些「自提议题 → 合入」周期？每次 tier0/M6 证据何在？
- ∞2：是否有「新类任务」交付？路径与验收？
- ∞3/∞4：宪章见 **`docs/weave_charter.md`**；§宪章对照审查记录 有几条？若 ∞ 绿门槛未齐，标明缺哪项。
- 输出：按 ∞1–∞4 分节；[x]/[ ]；勿打印 secret。
```

---

## ∞1 — 能力持续增长（不是停滞）

**路线图原文**：它的能力持续增长（不是停滞）。

**工程可观察信号**

- **`docs/evolution_log.md`** 或 §执行记录 中 **周期性** 有合并与摘要（非长期沉默）。
- 可选指标（团队自定）：工具成功率、任务完成数、GAP 关闭数 — 写入周期复盘 **同一行**。

| 勾选 | 项 |
|------|-----|
| [x] | 最近窗口：**滚动 90 天** **`2026-02-05`～`2026-05-05`（`as-of 2026-05-05`，裁定 ∞ 绿时刷新止期；下一止期刷新时重算起算日） |
| [x] | 本窗口内可审计周期数（≥3 为 ∞ 绿门槛）：**7** 行索引（**#1–#7**；其中 **#1、#4、#6、#7** 为 **exempt: docs-only**；**#2–#3、#5** 对应 M6 **`run_id`** 见下行） |
| [x] | 证据：**§∞1 可审计周期索引** + [`evolution_log.md`](evolution_log.md) **`20260504T162913Z_bc5d111-dirty`**、**`20260504T164848Z_68de456`**、**`20260504T174957Z_78350ca-dirty`**（*#5 脚注*） |

**阻塞**：无（工程表 **∞** 已 **绿**）；维持期见 **§当前推进**。  

---

## ∞1 可审计周期索引（工程侧）

> **用途**：满足 §建议的 ∞「绿」门槛 **∞1** 时，逐条可指认 **合并 SHA**、**tier0**、**M6 或豁免**（与 [`M6_EVOLUTION.md`](M6_EVOLUTION.md) §豁免 一致）。

> **合并日期列**：与 **§执行记录** 叙事日 **2026-05-05 / 06 / 07** 对齐；个别 commit 的 **AuthorDate** 可能为 UTC **2026-05-04 末** 或 **05-05**，以 **`git show <sha> --format=fuller`** 为准。

| # | 合并日期 | 摘要 | `git` commit | tier0 | M6 / 豁免 |
|---|----------|------|--------------|-------|-----------|
| 1 | 2026-05-05 | 阶段 4 工程入口：∞ 清单 + MAINLINE **∞** 黄 | `6706893` | pre-push **`./run_ralph_tier0.sh` exit 0** | **exempt: docs-only**（[`M6_EVOLUTION.md`](M6_EVOLUTION.md) §豁免） |
| 2 | 2026-05-05 | ∞1 加固：`ToolRegistry` 契约测模块说明 + M6 | `bc5d111` | **`record_m6_evolution.sh` 内 `./run_ralph_tier0.sh` exit 0** | **`20260504T162913Z_bc5d111-dirty`**（[`evolution_log.md`](evolution_log.md)） |
| 3 | 2026-05-05 | 里程碑 **∞** 绿裁定；MAINLINE **∞**→**绿**；§宪章对照 **#2** | `68de456` | pre-push **`./run_ralph_tier0.sh` exit 0** | **`20260504T164848Z_68de456`**（[`evolution_log.md`](evolution_log.md)） |
| 4 | 2026-05-05 | M6 进化日志：`evolution_log` 对齐 ∞ 绿 *run_id*（纯文档） | `78350ca` | pre-push **`./run_ralph_tier0.sh` exit 0** | **exempt: docs-only**（续 **#3** 工程链；无新增运行时） |
| 5 | 2026-05-05 | **search_web→web_search** Hermes 名级对齐；H15 快照 / 技能 / `test_hermes_tool_name_align` | `5099fc6` | **`record_m6_evolution.sh` 内 `./run_ralph_tier0.sh` exit 0** | **`20260504T174957Z_78350ca-dirty`**（[`evolution_log.md`](evolution_log.md)；*脚注*） |
| 6 | 2026-05-06 | 真源习惯：`path-contract` §协作习惯 + ∞ 黄阶段推进（§执行记录） | `77b26fc` | pre-push **`./run_ralph_tier0.sh` exit 0** | **exempt: docs-only** |
| 7 | 2026-05-07 | 织界宪章 v0.1 + §宪章对照审查 **#1**（§执行记录） | `8b8d684` | pre-push **`./run_ralph_tier0.sh` exit 0** | **exempt: docs-only** |

**脚注（#5）**：`record_m6` 运行时工作区为 **dirty**，`run_id` **`20260504T174957Z_78350ca-dirty`** 内 **git_rev** 为 **`78350ca-dirty`**；**随后** 合并 **`5099fc6`** 为同一轮「代码向」真源。**审计**：以 **`5099fc6`** 为合并 SHA；M6 行保留脚本当时 **exit 0** 证据。

---

## ∞2 — 能处理我们从未见过的任务类型

**路线图原文**：它能处理我们从未见过的任务类型。

**工程可观察信号**

- 某次任务 **类型标签** 与历史 B/C 任务 **显式不同**（新工具域、新集成、新工作流形态等）。
- **交付物路径** + **验收**（人工或自动化）。

| 勾选 | 项 |
|------|-----|
| [x] | 「新类」说明：见 **§∞2 新类任务样本 #1–#2**（两条 **类型不同** 的端到端交付） |
| [x] | 交付物与验收：见同表 **交付物 / 验收** 列 |

**阻塞**：无（工程表）；维持期见 **§当前推进**。  

---

## ∞2 新类任务样本（工程侧）

> **与 B / C 的边界**：**B** 侧重伙伴期端到端交付与复盘；**C** 侧重独立学习报告与矩阵对照。**∞2** 样本须是 **类型上不同** 的端到端工程交付（见 [`成长路线图.md`](../成长路线图.md) §阶段4 标准）。

| # | 归档日期 | 新类标签（一句话） | 与 B / C 差异 | 交付物（路径 / commit） | 验收（可复现） |
|---|----------|-------------------|---------------|-------------------------|----------------|
| 1 | 2026-05-04 | **工具名级 Parity 收束（H15）**：Hermes `get_tool_definitions` 与 Mimir `registry` 的 **自动化差集 + 缺口修复** | 非「单任务伙伴验收」也非「学习报告主线」；以 **跨实现工具面** 的 **可脚本对账 + 合并修复** 为闭环 | **`e21b065`**；[`tools/browser_camofox.py`](../tools/browser_camofox.py)、[`tools/session_search_tool.py`](../tools/session_search_tool.py)、[`tools/skill_manager_tool.py`](../tools/skill_manager_tool.py)；脚本 [`scripts/diff_tool_names_hermes_mimir.py`](../scripts/diff_tool_names_hermes_mimir.py)；快照 [`docs/parity_snapshots/h15_tool_names_diff_20260506.json`](parity_snapshots/h15_tool_names_diff_20260506.json) | （1）合并时 **`./run_ralph_tier0.sh` PASS**。（2）真源下 **`python3 scripts/diff_tool_names_hermes_mimir.py --json`**：`intersection` 含全部 **`browser_*`**、**`session_search`**、**`skill_view`**、**`skills_list`**；`hermes_only` 仅为 **`feishu_*`**（5）— 与快照一致。（3）Hermes / Mimir 根路径以脚本内默认或 `--help` 为准。 |
| 2 | 2026-05-04 | **M4 辅助 HTTP 离线分类切片**：对 **出站 HTTP** 失败形态（401 / 429 / 超时 / 连接类等）的 **无网 fixtures + JSON 驱动回归** | 与 #1 **类型不同**：不是工具注册表 / 名级 diff，而是 **Tier-2 HTTP 语义形状** 的测试资产与分类断言；亦非 C 阶段「单主题读书报告」主线 | **`2500740`**；[`fixtures/m4_http/error_shapes.json`](../fixtures/m4_http/error_shapes.json)、[`fixtures/m4_http/README.md`](../fixtures/m4_http/README.md)；[`scripts/refresh_m4_http_fixtures.sh`](../scripts/refresh_m4_http_fixtures.sh)；[`agent/test_m4_auxiliary_http_slice.py`](../agent/test_m4_auxiliary_http_slice.py)；[`docs/m4_auxiliary_http_slice.md`](m4_auxiliary_http_slice.md) | （1）合并链路上 **tier0 绿**（本切片在 Gate2 内）。（2）真源下 **`python3 -m pytest agent/test_m4_auxiliary_http_slice.py -q`** 全 PASS。（3）刷新 fixtures 流程见 [`m4_auxiliary_http_slice.md`](m4_auxiliary_http_slice.md) 与 [`fixtures/m4_http/README.md`](../fixtures/m4_http/README.md)。 |

---

## ∞3 — 进化方向和我们价值观一致

**路线图原文**：它进化方向和我们价值观一致。

**工程可观察信号**

- **人类审查**：关键 PR / 发布由负责人或委托人 **书面** 勾选「与价值观一致」或记录例外与原因。
- 与 **DEVELOPMENT_NORTH_STAR**、安全门（[`docs/DEVELOPMENT_NORTH_STAR.md`](DEVELOPMENT_NORTH_STAR.md) §5）不冲突。

| 勾选 | 项 |
|------|-----|
| [x] | 审查记录：§宪章对照审查记录 **#1**、**#2**（∞2 证据链与宪章 §2–§3 对齐） |

**阻塞**：人际价值观仍由 **负责人 / 织界者** 日常验收（路线图原文）；工程表 **∞** 已 **绿**。  

---

## ∞4 — 织界宪章在它的进化中体现

**路线图原文**：织界宪章在它的进化中体现。

**工程可观察信号**

- 仓库内 **`docs/…宪章…`** 或固定外链；进化周期说明 **如何对照** 宪章条款（可表格）。

| 勾选 | 项 |
|------|-----|
| [x] | 宪章真源路径：**[`docs/weave_charter.md`](weave_charter.md)**（v0.1 草案） |
| [x] | 最近一次对照审查：§宪章对照审查记录 **#2**（∞2 满额与 ∞ 绿证据链） |

**阻塞**：无（工程表）；宪章仍为 **v0.1 草案**，可迭代修订。  

---

## 汇总

| 里程碑 ∞ 条款 | 对应章节 | 完成（本轮） |
|----------------|----------|--------------|
| 持续增长 | §∞1 | [x] **∞1 索引**：**#1–#7**（≥3 门槛满足；含 **#2–#3、#5** M6 + **#5** 代码向 `5099fc6`，见 §∞1 可审计周期索引） |
| 新类任务 | §∞2 | [x] **样本 2/2**（§∞2 表 **#1 H15** + **#2 M4 HTTP**；类型互斥） |
| 价值观一致 | §∞3 | [x] 工程侧：§宪章对照审查记录 **#1**、**#2** |
| 宪章体现 | §∞4 | [x] **`weave_charter.md` v0.1** + 对照记录 **#1**、**#2** |

---

## 执行记录（倒序）

| 日期 | 周期摘要 | ∞1–∞4 要点 | 备注 |
|------|----------|------------|------|
| 2026-05-25 | **P2-LONG-IEVO** Wave E 结案（IEVO-01～06） | **∞1**：禁伪进化 + evolution tier0 + eval 脚本 + ADR-005 + monitor/insights 回归；**tier0 326+2**；**M6** `20260525T*` 多行 | [`p2-long-iev0-closeout.md`](phase0/p2-long-iev0-closeout.md)；GH **#21/#22** 部分关（icebox 余量见结案 doc） |
| 2026-05-07 | **织界宪章**草案入库 + 首条对照审查 | **∞3/∞4**：§宪章对照审查记录 **#1**（当时 MAINLINE **∞** 仍为 **黄**） | [`weave_charter.md`](weave_charter.md)；**∞1 索引 #7**（`8b8d684`） |
| 2026-05-06 | 真源习惯 + ∞ 推进对齐 | **∞1–∞4**：未宣称 ∞ 绿；固化真源与 §执行记录习惯 | [`path-contract.md`](path-contract.md) 新增 §协作习惯；**∞1 索引 #6**（`77b26fc`） |
| 2026-05-05 | **search_web→web_search**（Hermes 名级对齐） | **∞1**：代码向周期；**M6** `20260504T174957Z_78350ca-dirty`；合并 **`5099fc6`** | **∞1 索引 #5**；见索引表脚注 |
| 2026-05-05 | **M6** `evolution_log` 对齐 ∞ 绿 *run_id* | **∞1**：纯文档；续 **∞ 绿** 证据链 | **∞1 索引 #4**（`78350ca`） |
| 2026-05-05 | **里程碑 ∞ 绿**（工程裁定） | **§∞ 绿裁定记录 #1**；**∞1–∞2** 证据齐；**∞3/∞4** 宪章对照 **#1–#2**；MAINLINE **∞**→**绿** | [`MAINLINE_STATUS.md`](MAINLINE_STATUS.md) §2；**M6** `20260504T164848Z_68de456`；**∞1 索引 #3**（`68de456`） |
| 2026-05-05 | **∞2 样本 #2** 落档（M4 HTTP 离线分类切片） | **∞2**：**2/2**（裁定前证据） | `2500740`；[`m4_auxiliary_http_slice.md`](m4_auxiliary_http_slice.md) |
| 2026-05-05 | **∞2 样本 #1** 落档（H15 工具名级 Parity） | **∞2**：**1/2** → 与 #2 互补（见 §∞2 表） | `e21b065`；[`diff_tool_names_hermes_mimir.py`](../scripts/diff_tool_names_hermes_mimir.py) |
| 2026-05-05 | 阶段 4 工程入口 | 新增本清单；MAINLINE **∞** 标 **黄** | 宪章真源待补；∞ 绿门槛见上文；**∞1 索引 #1**（`6706893`） |
| 2026-05-04 | **∞1 加固**：契约测模块说明 + M6 | **∞1**：**索引 #2**（`bc5d111` + `20260504T162913Z_*`） | [`record_m6_evolution.sh`](../scripts/record_m6_evolution.sh)；**∞1 索引 #2** |

---

## 相关文档

- [`成长路线图.md`](../成长路线图.md) — 阶段 4 原文  
- [`docs/MAINLINE_STATUS.md`](MAINLINE_STATUS.md) — 主线表  
- [`docs/DEVELOPMENT_NORTH_STAR.md`](DEVELOPMENT_NORTH_STAR.md) — Parity / Evolution / 三道门  
- [`docs/M6_EVOLUTION.md`](M6_EVOLUTION.md) — 进化审计  
- [`docs/mimir_phase_c_checklist.md`](mimir_phase_c_checklist.md) — 里程碑 C  
- [`docs/weave_charter.md`](weave_charter.md) — 织界宪章（工程真源草案）  
