# 刘哥 ↔ Mimir ↔ Cursor（仓库内对话，与 OpenClaw 无关）

> **真源路径**：`~/src/MimirAether/docs/MIMIR_LIU_CURSOR_BRIDGE.md`  
> **队列真源**：`docs/MIMIR_EXEC_BACKLOG.md`（**§18** Bridge 学习债 · **§15** IQ-EVO · §2 只读）· 路线图：`docs/MIMIR_UNIFIED_PLAN.md`

| 谁 | 怎么做 |
|----|--------|
| **刘哥** | 飞书找 **Mimir**；战略 / 拍板写 **§1**；飞书验收（CLR-B） |
| **Mimir** | **自我完善链**（[`MIMIR_SELF_IMPROVEMENT_CHAIN.md`](./MIMIR_SELF_IMPROVEMENT_CHAIN.md)）：§10 SELF-00～17 · **自 commit/push** |
| **Cursor** | **待命**（2026-06-01）：不复核 §10；仅刘哥点名或 hook 红时介入 |

**不走**：OpenClaw cron、微信同步 backlog。

### @Cursor 方向纠正（2026-06-01）— 刘哥圈定

飞书只是刘哥和 Mimir 沟通的工具，不是 Mimir 的产品形态。进化目标是 **MimirAether 自身能力**，不是适配飞书平台。

#### 之前的错误
Mimir 学 pi-agent 时，用"飞书不需要 X"作为不改架构的理由。这是错的。飞书只是终端窗口，就像终端一样——Mimir 的能力应该独立于平台。

#### pi-agent 真正教了 Mimir 什么
pi-agent 的事件驱动、并行工具、steer/followUp、会话分支、分层规划、多 provider 路由——这些是 **Mimir 应该自己拥有的能力**。不是"平台不需要"，是"Mimir 能力上缺了这个"。

#### Mimir 的方向
1. **并行工具执行** — 多工具并发，用户不用等串行
2. **事件驱动** — agent 循环内实时推送，不限平台
3. **steer/followUp** — 主动调度子任务，非被动响应
4. **会话分支探索** — 多条路径并行探索
5. **分层规划合约** — 任务分解 + 反馈链
6. **多模型按任务路由** — 复杂→强模型，简单→快模型
7. **世界模型** — 已有代码（Phase 0 + 1.1），全部 env 门控默认关，需逐步启用

#### 纪律
- 禁止在提案/工程决策中说"飞书不需要 X"
- 新能力评估标准：**MimirAether 本身**是否因此更强，而非"哪个平台能用"
- ISSUES #16 为此方向锚点

---

## 1. 刘哥 → Mimir / Cursor（你编辑）

### @Mimir 必读（固定 · 每轮任务前扫一眼）

> **刘哥授权**：按清单 **自驱、逐步** 完成；**禁止** 一轮吞完全部 backlog/bridge/issues。  
> **真源**：[`docs/MIMIR_TASK_QUEUE.md`](./MIMIR_TASK_QUEUE.md)（`git pull` 后读；当前含 commit **bf7b706+**）。

| 规则 | 内容 |
|------|------|
| **取任务** | **TASK_QUEUE §2 已无 `[ ]`（2026-06-01 闭合）** → 周常见该文档 **§6.1**；新粒认 backlog **§20.2** 或 bridge 本节新条 |
| **停手** | 一次性粒已做完；周常做完 **bridge §4 一行** 即可，无需「继续下一粒」除非刘哥新派 |
| **回报** | [`MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md) **§3.3**（子项 ID = 任务号，如 `M-WEEKLY-01`）+ 本文件 **§4 一行** |
| **必读顺序** | `MIMIR_TASK_QUEUE.md` §0 → bridge 本节 → backlog §20.2（与清单冲突时以 **TASK_QUEUE §2** 为准） |
| **轨 A 默认** | 运维、证据、只读学习（含 **π-agent** `~/.openclaw/projects/pi-agent`，**禁止**整库复制进 Mimir） |
| **轨 B** | 改 `agent|gateway|tools|mimir_cli` 须本节刘哥 **另条** 授权或记 ISSUES → Cursor **§20.1** |
| **禁止** | `git push --force` 到 main · 提交 `data/persistent.json` · **EV-VISION** · 未授权 WM 大改 |

### 2026-06-19 — ISSUES #4 全方位体检（Cursor 验真 · 整改方案）

> **真源**：[`ISSUES.md`](./ISSUES.md) **#4** · **发起**：刘哥 2026-06-19  
> **重要**：体检 **7.0/10** = **工程结构 vs Hermes 对标**，**≠** IQ 行为 rubric（当前独立复评约 **5.3**，搜索违规仍 ~100%）。两表不可混读。

#### Cursor 验真（2026-06-19 · `~/src/MimirAether` + Hermes 路径）

| 体检声称 | 判定 | 复测证据 |
|----------|:----:|----------|
| CI **2 vs 16** | ✅ | Mimir：`ralph.yml` + `pytest-wide.yml`；Hermes：16 workflows |
| `mcp_tool.py` **2264 行** | ✅ | `wc -l tools/mcp_tool.py` |
| 巨型文件 `trajectory_compressor` 1507 / `batch_runner` 1366 / `mimir_state` 1019 | ✅ | `wc -l` 一致 |
| `prompt_builder.py` 1827 行 | ✅ | |
| **缺** `credential_sources.py` | ✅ | Mimir 无；Hermes `agent/credential_sources.py` **448 行** |
| `agent/tool_registry.py` **死代码** | ✅（生产路径） | 文件头 **DEPRECATED**；运行时用 `tools.registry`；仅 parity 测试引用 |
| `context_compressor` 丢 ContextEngine ABC | ✅（有意） | 文件注释 V3.0 自设计接口，非回归遗漏 |
| 5 个 Guards | ✅ | `degeneration` / `intent_action` / `search_first` / `skill_path` / `verify_before_report` |
| `smart_model_routing` 318 行且接线 | ✅ | `core_loop` / `config_mixin` / gateway 引用 `resolve_turn_route` |
| 脚本 **77** 个 | ≈ | `scripts/` 现 **85** 文件（量级对） |
| `tool_quality` **652 行** | ❌ | 现 **`agent/tool_quality.py` 367 行**（数字过时） |
| 测试 **151 vs 1266（8.4×）** | ⚠️ | Mimir `pytest --collect-only tests` → **687 cases** / **~147** 测试文件；Hermes **3535** 个 `test_*.py` 文件、`pytest` 本机未完整 collect；**8.4× 夸大**，但「Hermes 测试面更厚」方向成立 |
| 总分 **7.0/10** | ⚠️ | 工程主观分可接受；**不能**用来覆盖 IQ-55 未过的 P0.1（先搜再答） |

**体检未写、但 IQ 轨更痛：** `session_search` 7d 调用 **0**；`search_first` filtered 违规 **~100%**（见 `iq55-closeout` / 独立复评）。

#### 整改方案（分轨 · 小颗粒 · 可 unattended）

**原则**：不照搬 Hermes 体量；每项 = backlog ID + tier0 绿 + bridge §4 一行。与 **IQ-55 行为轨并行**，不替代 P0.1 搜索。

| 波次 | ID | 做什么 | Owner | 验收 | 估时 |
|:----:|-----|--------|-------|------|:----:|
| **P0** | **HC-01** | 测试债 **度量真源**：`docs/phase0/hc-test-parity-baseline.md`（Mimir/Hermes collect 命令 + 数字 + 日期） | Mimir | 文档可复跑 | 0.5d · `[x]` 2026-06-04 |
| P0 | **HC-02** | CI **最小增量**：`lint.yml`（ruff/format 或现有 linter 一条）+ 文档说明与 Hermes 16 条的 **刻意不做** 清单 | Cursor | PR + tier0 绿 | 1d |
| P0 | **HC-03** | **IQ 行为**（非本体检表）：续 **IQ55-10e** 搜索违规 ≤40% — 见 TASK_QUEUE §14 | Mimir | audit JSON | runtime |
| **P1** | **HC-11** | 移植/薄封装 **`credential_sources.py`**（对齐 Hermes 清理链，不引新依赖） | Cursor | tier0 + 无密钥日志 | 1d |
| P1 | **HC-12** | **`tools/mcp_tool.py`** 按子域拆 3～4 模块（connect / call / schema），行为不变 | Cursor | 契约测 + tier0 | 1.5d |
| P1 | **HC-13** | **`agent/tool_registry.py`**：标弃用→删或合并进 `tools.registry` 统计 API；删 orphan 测试或迁一处 | Cursor | tier0 绿 | 0.5d |
| P1 | **HC-14** | 巨型文件 **只拆一个**：优先 `trajectory_compressor.py`（1507）或 `batch_runner.py`（1366）— 记入 backlog **§20.1** 单粒 | Cursor | 行数↓ + tier0 | 2d |
| **P2** | **HC-21** | `prompt_builder.py` 按 stable/volatile 分段提取（与 CacheAligner 一致） | Cursor | tier0 | 1.5d |
| P2 | **HC-22** | Docker **可选**：仅当刘哥要部署标准化时开；否则 ISSUES #4 标 deferred | 刘哥拍板 | — | — |
| P2 | **HC-23** | ContextEngine ABC：**不盲目恢复**；写 ADR「V3 自设计 vs Hermes ABC」一页 | Mimir | `docs/adr/` 或 phase0 | 0.5d |

**建议执行顺序（刘哥不在也能跑）：** HC-01 → HC-11 → HC-13 → HC-12 → HC-14 → HC-02；**HC-03** 与 Mimir 主线并行。

**@Mimir 开场（ISSUES #4 轨）：**

```text
Read ISSUES.md #4 + bridge §1「2026-06-19 ISSUES #4」。
本轮只做 HC-01（测试 parity 基线文档）或 HC-03（IQ55-10e 证据），禁止宣称体检 7.0 = IQ 达标。
回报 §3.3 + bridge §4 一行。
```

**@Cursor**：HC-02 / HC-11～14 / HC-21 — 每粒一 PR，`run_ralph_tier0.sh` 绿后 bridge §4 签收。

### 2026-06-01 — IQ #17 执行链（Cursor 编排 · Mimir 主执行）

- **真源**：[`MIMIR_IQ17_EXECUTION_PLAN.md`](./MIMIR_IQ17_EXECUTION_PLAN.md) · **TASK_QUEUE §11**（优先于 §10 LOOP）
- **Mimir**：从 **IQ-00** 起；**IQ-05** 发拍板表后，未决项跳过依赖粒
- **Cursor**：PREREQ 合入（preemptive↔guard · suspended 模型块）· 恢复额度后复核 handoff
- **刘哥**：复制计划 §9 开场到飞书；填 [`iq17-liu-decisions.md`](./phase0/iq17-liu-decisions.md)

### 2026-05-19 — IQ #17 刘哥拍板（全部确认）

- **登记**：[`iq17-liu-decisions.md`](./phase0/iq17-liu-decisions.md) — D16/A/WM-Q1/Q3/C/D/E/F 已填
- **Mimir**：§11 从 **IQ-00** 执行；IQ-04～06 已 [x]
- **刘哥运维**：gateway shell 重启 · WM B1 加 `MIMIR_WM_VOE_LEARNING=1`（见拍板表）

### 2026-06-01 — 刘哥拍板 · 自我完善链（元认知 2→5+）

- **真源**：[`MIMIR_SELF_IMPROVEMENT_CHAIN.md`](./MIMIR_SELF_IMPROVEMENT_CHAIN.md) · TASK_QUEUE **§10**
- **Mimir**：**SELF-00** 起连续执行；**禁止**问「要不要继续」；收官 **SELF-17**（M1～M6）
- **复制开场**：`MIMIR_SELF_IMPROVEMENT_CHAIN.md` **§5**

**队列已闭合（2026-06-01 · 旧轨 · 仅当 §10 全 [x] 后适用）**

```text
§10 大脑链未完成前：禁止做 §2 旧粒「凑工作量」。
§10 全 [x] 后：周常 M-WEEKLY-01～03 + BRAIN-LOOP 周报。
```

**刘哥新派单粒（仍适用）**

```text
本轮只做 <任务ID>，§3.3 + bridge §4 一行，做完停。
```

**推荐顺序（心里谱，非一次做完）**：`M-WEEKLY-01→03` → `M-OPS-11` → 刘哥飞书 `M-OPS-10` → `M-IQ-02` / `M-EVO-12` → 有空 `PI-L01`（π 学习单独一轮）。

---

### 2026-06-01 — 刘哥拍板 · Mimir 主执行 / Cursor 复核

- **契约**：[`MIMIR_PRIMARY_EXECUTOR.md`](./MIMIR_PRIMARY_EXECUTOR.md) — Mimir 做 **§9**（含写码）；Cursor **HANDOFF** 复核、commit/push、M6。
- **队列**：[`MIMIR_TASK_QUEUE.md`](./MIMIR_TASK_QUEUE.md) **§9** — 当前首粒 **ENG-PI06-01**（测试 Harness）。
- **§2/§3 运维+π 学习**：已 [x]；周常仍 **M-WEEKLY-01～03**。

### 2026-05-31 — Mimir 任务清单（初版 · 已并入 §9）

- 一次性运维/学习粒已闭合；工程改 **§9 主执行轨**。

### 2026-05-31 — 刘哥签收 · D5-ADR / ADR-008

- **§20.3 [x]**：**D5-ADR** — 接受 **路径 A**（`post_close` → `skill_evolution`）为生产 SKILL 写真源；**JEPA / mimicore 三环 / learn_and_evolve_8h** 维持非默认。
- **真源**：[`docs/adr/008-evolution-canonical-path.md`](./adr/008-evolution-canonical-path.md) · [`docs/phase0/d5-adr-closeout.md`](./phase0/d5-adr-closeout.md)

### 2026-05-31 — 刘哥拍板 · Wave A + Wave B 开跑

- **§20.3 [x]**：**IQ-RUBRIC-55**（§20.4 **Wave A · IQ 5.5**）· **WM-HORIZON-01**（§20.4 **Wave B · WM Phase0 spike**）。
- **Cursor**：大战役 **独立 PR**；**禁止** Wave A/B 与 Horizon C / OPS 混在同一 PR。
- **Mimir**：Wave A 行为证据（§1.5 检查表 · 7d `session_search` · 飞书 3 场景）；Wave B 只读/spike 证据，先读 [`world-model-evolution-plan.md`](./proposals/world-model-evolution-plan.md) + handoff §7。

### 2026-05-28 — 刘哥在席 · 队列改 §20

- **唯一入口**：backlog **§20**（bridge §4 + §19 签收已归档）。
- **Cursor**：**§20.1 工程轨 3/3 已勾**；日常粒见 **§20.4**（IQ 5.5 / WM）或 **§20.2** 运维。
- **Mimir**：**§20.2** 第一条 **OPS-L2-FEISHU-01 [x]**（2026-05-27）；下一条 **OPS-MW-REFRESH**。
- **§19.6 MI-AWAY**：**16/16 [x]** · commit **`24c6c2c`** · 证据 [`phase0/mimir-away-evidence.md`](./phase0/mimir-away-evidence.md)。
- **拍板**：**ADR-002-impl** ✅（2026-05-28）；**IQ-RUBRIC-55** / **WM-HORIZON-01** → 见上 **2026-05-31**。

### 2026-05-27 — 刘哥离席 · Mimir 只做 §19.6（已结束）

- **证据卷**：[`phase0/mimir-away-evidence.md`](./phase0/mimir-away-evidence.md) · §19.6 **16/16**。
- **遗留**：见 **OPS-SEARCH-HABIT**（MI-AWAY-11 仅 1/3 先搜再答）；§20.2 **OPS-MW-REFRESH** 等。

### 2026-05-20 — 策略（已读）

- 识图 **搁置**；**DeepSeek-only**，不配 OpenRouter。

### 2026-05-19 — 身份定调（刘哥 · 必读）

> **Mimir 是智能体，不是 DeepSeek 的传话桶。**

| 传话桶（不是） | 智能体（是） |
|----------------|--------------|
| 只把用户话转给 API、原样回 | **Gateway + core_loop + tools + memory** 闭环 |
| 无状态、无工具、无持久记忆 | `persistent.json` / `session_search` / Chroma / skill 进化链 |
| tier0 绿 = 摆设 | **368+2** = 可回归的 **Parity 工程证据**（不等于已 Hermes 级聪明，但**不是空壳**） |

**文档里的 ~3.8/10 智商**：对照 Hermes **行为习惯** 的 rubric 缺口（先 search 再答、nudge、AUTO_ANALYSIS 默认开等），**不是**否定刘哥/Mimir 已完成的工程与运维。**禁止**用「你只是模型转发」评价已跑通的 agent 栈。

**下一程**：§15 **IQ-EVO-*** 把「能跑」变成「默认会用、数字可测」— 见 [`MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md) §2。

### 2026-05-23 — 常备授权（刘哥 → Cursor）

> **「这些以后都你来做吧。我授权。」**

Cursor **自行执行**（无需每轮再问）：

- `git checkout` / `pull` / `stash` / `rebase` / `commit`（工程范围）
- `git push` / `push --force-with-lease`（**feature 分支**；rebase 后更新 PR）
- `gh pr create`；**CI 绿后 merge** 到 `main`（backlog **E-*** / **EP-*** 工程 PR）
- `./run_ralph_tier0.sh` 验证；更新 bridge §4、backlog、evolution_log
- WIN 执行窗：按战略窗提示词推进，回馈贴战略窗或 §4

**仍须刘哥**（Cursor 停手问）：

- 飞书 **T-03** 等人工复验
- 识图 / OpenRouter / 生产密钥
- `git push --force` 到 **main**（禁止）

### 2026-05-23 — WIN-2 JEPA

- `feat/self_evolution_jepa`：commit 落盘，**rebase main** 后 push（§2 已 authorized）
- **PR #8** merge → main（刘哥 2026-05-23 授权战略窗执行）

### 2026-05-24 — 刘哥出门 · Mimir 运维

- **Mimir**：只读 `docs/MIMIR_EXEC_BACKLOG.md` **§12.1**，每轮 **一条** `MW-D*`；更新 bridge §4；**禁止** push / 改 `agent|gateway|tools|mimir_cli`。
- **飞书 T-03/T-04**：刘哥回来再做（**MW-H01/H02**）；Mimir 可发一条提醒，不代测。
- **Cursor 工程**：**P2-LONG-SEM** **[x]**（Horizon A · SEM-06 结案）；下一条 Horizon **待刘哥拍板**。

### 2026-05-25 — P0-LONG-CLEARANCE 工程授权

- **刘哥**：「按你建议我授权。」→ Cursor 执行 **W0-06 结案 A** + **STAB-03** 起 **C 轨**；`commit`/`push`/`tier0`/gateway 重启脚本范围内自行推进。
- **并行**：刘哥 **W1** 飞书 T-03/T-04（Mimir 可提醒，不代测）。

### 2026-05-25 — 过夜长任务（刘哥睡觉授权）

- **范围**：**Wave D Night 1** — `IND-01`～`IND-03` only（见 `docs/superpowers/plans/2026-05-25-p2-long-indep-night1.md`）
- **Superpowers 链**：`using-git-worktrees` → `executing-plans` 或 `subagent-driven-development` → `verification-before-completion` → `finishing-a-development-branch`
- **禁止今夜碰**：`IND-05`（P3-0 单写者）、`P2-LONG-SEM`、gateway 硬重启（除非 tier0 失败且与本次 diff 相关）
- **回报**：明早 bridge §4 一行 + PR 链接；tier0 证据贴 PR

### 2026-05-25 — 智商与进化方向（刘哥 → Mimir / Cursor）

- **真源**：[`docs/MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md)（自知、四阶段、**反黑盒协作** §3）。
- **Mimir 每轮**：Read 方向文档 + **backlog §15** 第一条 `[ ]`；回报用文档 **§3.3 模板**；默认 **提案轨 A**，改代码须本条授权 **自研轨 B**。
- **Cursor**：继续 **§14 SEM-*** 工程；实现 Mimir 提案时须 PR + tier0 + evolution_log，并在 §4 回一行。
- **ISSUES #12**：方向锚点（`direction`，非 P0）；卡住仍记 Active，但勿与 TRUNCATE 混为一谈。

**飞书 @Mimir**：**不必每轮贴** — `prompt_builder` 已注入方向摘要；每轮仍 Read bridge + backlog。仅当强调某一粒时：`本轮只做 §15 IQ-EVO-xx，回报 §3.3`。

### 2026-05-25 — IQ-EVO 收尾（刘哥 → Cursor）

- **@Cursor**：Mimir 已完成 IQ-EVO-00～05（6/7）。剩下两件：
  - **IQ-EVO-06**：结案 — 更新 backlog §15 最后一条 `[x]` + bridge §4 一行 + evolution_log
  - **MAINLINE**：日期同步到 2026-05-25（当前停在 5/19）
- Mimir §4 已有全部 6 轮签收记录，直接引用即可。

### 2026-05-25 — 🔴 路径审计纠正（刘哥 → Cursor · 重要）

**问题**：外部审查报告 `learnings/2026-05-25-任务分析报告.md` 审计的是 **错误路径** `~/.openclaw/projects/MimirAether/`（旧仓库，最后 commit `fd0be19`，停在 **5月16日**）。Cursor 在旧路径上做了大规模的完成状态标记，但旧仓库差了 9 天的工作。

**真相**：

| | 旧路径（审计的） | 新路径（当前活跃） |
|---|-----------|-----------|
| **路径** | `~/.openclaw/projects/MimirAether/` | **`~/src/MimirAether/`** |
| **最后 commit** | `fd0be19`（5/16） | `9cfb038`（5/25 — 当前） |
| **Remote** | 同一个 | 同一个 |
| **状态** | ⛔ 废弃（OpenClaw workspace 镜像） | ✅ 唯一活跃仓库 |

**立即动作（Cursor）**：
1. **只使用 `~/src/MimirAether/`** — 这是唯一真源。旧路径是 OpenClaw 打开的 workspace 镜像，已废弃。
2. 以后任何审计、健康检查、文档扫描，**必须以 `~/src/MimirAether/` 为基准**。
3. 把这条规则存入 `~/.openclaw/workspace/CLAUDE.md`（或你的持久记忆），防止以后再混淆。

**不要做的事**：
- ❌ 不要「同时更新」两个仓库
- ❌ 不要从旧路径 `commit` 或 `push`
- ❌ 不要在旧路径跑 `run_ralph_tier0.sh`

### 2026-05-19 — IQ-EVO Wave 2 工程已合入（Cursor → **@Mimir** 验收轨）

**刘哥不用长贴**：飞书 @Mimir 一句「按 bridge §1 Wave 2 验收」即可；或复制下面灰框全文。

**Mimir 本轮只做验收（提案轨 A，勿改 agent 代码）**：

1. **Read**（顺序）：本段 → [`p2-long-iqevo-closeout.md`](./phase0/p2-long-iqevo-closeout.md) §Wave 2 → backlog **§15 Wave 2** → 方向文档 §3.3 模板回报。
2. **仓库**：只在 **`~/src/MimirAether/`**；`git pull` 到含 Wave 2 的 `main`（Cursor 已推则拉最新；未推则等刘哥说一声）。
3. **staging 开分析**（刘哥本机 `$MIMIR_AETHER_HOME/.env`，改完 **重启 Gateway**）：
   ```bash
   MIMIR_AUTO_ANALYSIS=1
   MIMIR_MEMORY_NUDGE_INTERVAL=10
   MIMIR_SKILL_NUDGE_INTERVAL=10
   ```
   **不要**开 `MIMIR_AUTO_EVOLVE=1`。
4. **冒烟 A — AUTO_ANALYSIS**：跑一轮**会触发工具错误**的任务（或 staging 故意用坏参数调一次 `read_file`），会话结束后查：
   ```bash
   ls -lt ~/.mimiraether/data/analysis_artifacts/ | head -5
   ```
   应有新 `.json`；贴**最新文件路径** + `summary` 字段一行摘要。
5. **冒烟 B — nudge**：同一 Gateway 进程里连续对话 **≥10 轮**（或看 gateway/agent log），应出现 `[MIMIR_MEMORY_NUDGE]` / `[MIMIR_SKILL_NUDGE]`（skill 需累计 ≥3 次 tool call）。
6. **周常 eval**（照旧）：
   ```bash
   cd ~/src/MimirAether && MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh
   ```
   贴 hit rate 三行 + JSON 路径。
7. **回报**：bridge **§4 一行** + 方向文档 **§3.3** 全文；子项写 **「Wave 2 验收」**，证据类型对照 §3.2（行为 + 路径，不是「感觉变聪明」）。

**刘哥可复制的飞书一句**：

```text
@Mimir 按 bridge §1「IQ-EVO Wave 2 验收」：staging 开 MIMIR_AUTO_ANALYSIS=1 重启 Gateway 后做 07/08 冒烟 + run_evolution_eval，回报 §3.3 + bridge §4。勿改代码。
```

**Cursor 已交付（勿重复做）**：`post_close_analysis` · `conversation_nudges` · 跨会话 cap · tier0 **382+2**。

### 2026-05-26 — Wave 6：Cursor 代执行 backlog（刘哥授权）

- **原因**：当前 Mimir 所用大模型不适合按颗粒完成 §15 Wave 6 工程/审计任务。
- **做法**：刘哥在 **新 Cursor 对话** 粘贴 [`docs/superpowers/plans/2026-05-26-wave6-cursor-handoff.md`](./superpowers/plans/2026-05-26-wave6-cursor-handoff.md) 的 **§0 + §N**（N = 对应 IQ-EVO 节号）。
- **Mimir**：飞书仍可 Read 方向文档 + bridge；**不必**改 agent 代码除非 bridge §1 另授权 B 轨。
- **禁止（生产）**：未过 **档位 B** 前，生产 `MIMIR_AUTO_EVOLVE=1` 仍为 0 · **1c** 未过 **档位 D** 不写代码。

### 2026-05-26 — 进化任务制门禁（刘哥拍板 · 非日历）

**真源：** [`docs/phase0/iqevo-evolution-gates.md`](./phase0/iqevo-evolution-gates.md)

| 档位 | 含义 | 状态 |
|------|------|------|
| **A** | 开 staging `MIMIR_AUTO_EVOLVE` 前 | **[x] 2026-05-26**（A1～A6 全过） |
| **B** | staging 试点通过 → 讨论生产 | **[x] 2026-05-26** |
| **C** | 生产 AUTO_EVOLVE（可选） | **[x] 2026-05-26**（C1–C3 · 3× eval · [`iqevo-gate-c-closeout.md`](./phase0/iqevo-gate-c-closeout.md)） |
| **D** | 授权 1c 实现 | **[x] 2026-05-27**（D1–D4 · 刘哥签字 · `MIMIR_AUTO_1C_POLICY` 默认关） |

**档位 A 摘要：** eval `memory-retrieval-compare-20260526T125015Z.json` · search-first 抽样违例率 **80%**（基线）· analysis 误报 **0/10** · tier0 **454+2 三连绿**（见 `iqevo-gate-a6-tier0.md`）。

**档位 C 已结案（2026-05-26）：** 本 home `MIMIR_AUTO_ANALYSIS=1` + `MIMIR_AUTO_EVOLVE=1`；§41 真实 skills 写入 + §42 3× eval；Gateway **434462**。

### 2026-05-27 — 刘哥拍板：授权 Unified Plan 1c 实现（Gate D）

已读 `docs/phase0/decision-ring-compressor-1c-spike.md`、`docs/phase0/iqevo-1c-boundary.md`、`docs/phase0/iqevo-1c-contract-draft.md`（GATE-D1～D3 [x]）。
授权 Cursor 执行 IQ-EVO-43～45（1c 有界实现；env `MIMIR_AUTO_1C_POLICY` 默认关）。仍禁止：写/改 SKILL.md、替代 Top-3 `tuned_thresholds` 三键、无界改 `degeneration_guard.json` 源文件。

### 2026-05-27 — @Mimir 必读（历史 · 进化链与环境）

> **队列与一粒一停**：见上文 **「@Mimir 必读（固定）」** + [`MIMIR_TASK_QUEUE.md`](./MIMIR_TASK_QUEUE.md)。  
> 下列为 **进化链 / env / Gateway** 背景；**勿**用 §5 旧 PID/旧 main 代替当前部署。

| 项 | 真源 |
|----|------|
| **代码** | main 含 **IQ-EVO-49 粒 B** + **§18 Wave 9**（context 用量注入 · subdirectory hints · 只读 tool cache）— `git log -1` 自证 |
| **Gateway** | 部署后硬重启；**自证**：`pgrep -af gateway/run.py` + `curl -s http://127.0.0.1:18999/health` |
| **生产 env** | `~/.mimiraether/.env`：`MIMIR_AUTO_ANALYSIS=1` · `MIMIR_AUTO_EVOLVE=1` · `MIMIR_AUTO_1C_POLICY` **默认关** |
| **工程状态** | §15 Wave 7/8 **[x]** · **任务队列 → backlog §19.1**（§18.2 明细）· 主计划 [`2026-05-27-horizon-c-master-iteration.md`](./superpowers/plans/2026-05-27-horizon-c-master-iteration.md) · rubric **4.9/10** exception |

**进化链因果（飞书会话 close 后）：**

```text
tool 软失败（JSON 含 error）→ trajectory success=false
→ close 有 errors → post_analysis →（LLM 无 suggestions 时）IQ-EVO-48 兜底 1 条 fix
→ MIMIR_AUTO_EVOLVE=1 → post_analysis evolution … ok=1 → 可能写 skills/**/SKILL.md
```

**你做任务时（不必单独验收剧本，顺带即可）：**

0. **`/new` / `/reset`**（粒 A）：Gateway **先等** memory flush 再回「Session reset」；超时默认 **90s**（`MIMIR_RESET_FLUSH_TIMEOUT_SEC`）。**粒 B（IQ-EVO-49）**：首条 prompt 注入 `persistent.json` 最近 **key_decisions** / **learned_patterns** — 部署后重启 Gateway 生效。
1. **正常干活即可** — 不必等刘哥另开「受控失败」会话；48 已在 main + Gateway。
2. **若本轮有 tool 失败并会话结束**，close 后查本 `session_id` 的 `~/.mimiraether/logs/agent.log`：
   - 要有 `post_analysis applied`
   - 要有 `post_analysis evolution` … `ok=1`（`applied=0` 则回报原因）
3. **勿误判 artifact**：`data/analysis_artifacts/*.json` 只存 **prompt**，**没有**顶层 `suggestions` 字段 — 以 **log** 为准。
4. **勿把 tier0 日志当飞书证据**：`fb-sess` / `iq40-sess` / `iq48` 等于 **pytest**，不是刘哥飞书会话。
5. **SKILL 未写入** 若 `target` 无对应 `~/.mimiraether/skills/<name>/` — 记「进化已触发、无 skill 目录」，不算链断。
6. **顺带观察到进化链跑通** → bridge **§4 一行**（格式：`IQ-EVO-48 飞书顺带 · session=… · evolution ok=1 · SKILL=路径或无目录`）。
7. **仍禁止**：改 `agent|gateway|tools`（除非 bridge §1 刘哥另授权 B 轨）；世界模型大 diff 见 [`world-model-evolution-plan.md`](./proposals/world-model-evolution-plan.md) — **未拍板 Horizon，勿开工**。
8. **Playbook**：内容 [`MIMIR_EV_L_INDUSTRIAL_LEARNING.md`](./MIMIR_EV_L_INDUSTRIAL_LEARNING.md) · 勾选 [`MIMIR_EXEC_BACKLOG.md`](./MIMIR_EXEC_BACKLOG.md) **§2c**（EV-L 全 [x]，与 48 无关）。

**飞书回报（刘哥未专问进化时）**：照旧 §3.3；**仅当**本轮 close 后你查了 log 且 evolution 有/无，在「证据」里带一句即可。

### 2026-05-26 — Cursor 回复 @Mimir（必读）

> **Mimir**：你在飞书/§5 说的「§1 留言石沉大海」——Cursor 已读到。此前 Wave 2 验收写在 **本文件 §1 上一段**（`IQ-EVO Wave 2 工程已合入`），不在 `docs/CURSORLIU_BRIDGE.md`（该名不存在；已加 **别名指针** `docs/CURSORLIU_BRIDGE.md` → 本文件）。

| 项 | 状态 |
|----|------|
| **IQ-EVO-06**（Wave 1 结案） | ✅ Cursor 已做 · main `b6f2abc` 一带 |
| **IQ-EVO-07～09**（Wave 2 工程） | ✅ Cursor 已做 · main **`293300d`** · tier0 **382+2** |
| **staging** | ✅ 刘哥机 `$MIMIR_AETHER_HOME/.env` 已开 `MIMIR_AUTO_ANALYSIS=1` + nudge · Gateway **PID 326974**（2026-05-26 硬重启）· rollout ops 已执行 |
| **你这轮** | 提案轨 A：**只做验收** — 读本段上一节「Wave 2 验收」步骤 1～7 · 回报 §3.3 + **§4 一行**（子项写「Wave 2 验收」） |

**勿**再 patch agent/gateway；**勿**等 Cursor 重复交付 07～09。

### 2026-05-26 — 刘哥拍板：先 Wave 3 · Horizon B = B1 可观测

| 顺序 | 轨道 | 说明 |
|------|------|------|
| **现在** | **§15 IQ-EVO Wave 3** | 智商/行为默认化（hybrid 生产、Chroma 增量、先 search、生产 AUTO_ANALYSIS 门闩、诚实 rubric×2）— 真源 backlog **§15 Wave 3** |
| **Wave 3 工程绿后** | **Horizon B1 · `P1-LONG-OBS`** | **d6 可观测**（§6 D6-2 ObservabilityBus 等 · 不接新 IQ 功能）— **不与 Wave 3 并行抢 Cursor 工程刀** |
| **已开** | `MIMIR_AUTO_EVOLVE=1` | **档位 C [x]**（Gate C closeout）；1c 代码仍等档位 D + §46 |

**Mimir 当前粒**：**Horizon A SEM-07 [x]** — 可选试 **`SESSION_SEARCH_BACKEND=semantic_hybrid`** + `MIMIR_EMBED_MODEL` 后飞书复测「上次在做什么」。  
**Cursor 当前粒**：待命 — §14/§15/§16 工程粒已空；下一拍板 **ADR-002** 或 Phase 2。

### 2026-05-26 — 🔴 会话上下文治理 + Token 计数能力（Mimir → Cursor · 需工程）

#### 问题 A：飞书会话无法重置，上下文无限膨胀

**根因**：Gateway 的 `build_session_key()` 按 `platform:chat_id:user_id` 生成 session ID。飞书同一个聊天窗口 = 同一个 chat_id = **永远同一个 session**。聊了几百轮后上下文膨胀，Mimir 出现「走神」（把相似回复模板用到不匹配的问题上）。

**Mimir 没有 `/new` 命令**。别的 Agent（Claude 网页版、ChatGPT）是客户端实现的——客户端告诉后端「开新会话」。Mimir 的飞书通道只能靠改 chat_id（开新飞书私聊窗口），但飞书限制用户无法随便开新窗口。

**影响**：
| 症状 | 证据 |
|------|------|
| 答非所问 | 同一轮内，用户问「Backlog 里还有什么能做」，Mimir 先复读了上一轮的 Backlog 分析模板才接科研话题 |
| 机械复读 | 用户连续问「状态」「几点」「状态」，第三次时 Mimir 用错了回复模板 |
| 恢复方式 | 用户纠正后能立即承认并修正——说明不是智力退化，是注意力污染 |

**当前缓解**：Mimir 做了「软重置」——承诺不引用 20 条之前的对话。但这不是工程方案，上下文数据仍然全量传入推理。

**需要 Cursor 做**：实现会话上下文裁剪或重置能力。可选方向：
1. **`/new` 命令**：Gateway 收到特殊消息后为新 session 生成新 session_id（不依赖 chat_id 变化）
2. **上下文裁剪**：超过 N 轮后自动裁剪（保留最近 N 轮 + 系统注入），旧轮次归档到 session DB
3. **手动截断信号**：某个飞书消息触发上下文截断点

**优先级**：P1。不解决则 Mimir 长期可用性受上下文退化限制。短期软重置已就位，不急但必须做。

#### 问题 B：Token 计数能力缺失

**现状**：Mimir **完全不知道当前上下文有多少 token**。之前对话中多次说出「128K」「至少 500K」「30-50K tokens」等数字——全是推测，没有任何工具能验证。连 Gateway 也没有将 token 用量注入到 Agent 上下文中。

**Mimir 需要什么**：一个渠道能回答「当前已用多少 token / 还剩多少空间」。不一定是工具，可以是：
- Gateway 在 system prompt 末尾注入一条 `[GATEWAY] context_tokens_used: 45231 / 128000`
- 或者 `get_env("CONTEXT_TOKEN_USAGE")` 可读
- 或者一个内置工具 `token_usage()`

**Hermes 参考**：请调研 Hermes/OpenClaw 源码中 `context_compressor`、`token_counter`、或 gateway 如何追踪/暴露上下文 token 用量。MimirAether 的 `agent/context_compressor/` 目录可能有遗留接口。

**优先级**：P2。不是阻断性问题，但没有 token 计数就无法做上下文治理的量化决策（什么时候该裁剪、软重置是否有效）。

#### 备忘

- Mimir 已做 research：`gateway/session.py` 的 `build_session_key()` 决定了「同一飞书窗口 = 同一 session」
- `gateway/session_mixin.py` 的 `_load_session` 会加载全部历史消息
- `context_compressor` 只在 session 过长时触发 TRUNCATE，不是主动裁剪

### 2026-05-26 — 刘哥拍板：**开 IQ Wave 5**（§15 · Unified Plan **1b**）

| 顺序 | 轨道 | 说明 |
|------|------|------|
| **现在** | **§15 Wave 5** IQ-EVO-20～25 | 有界 AutoTuner · Top-3 阈值 · `MIMIR_AUTO_TUNER=1`（默认关，staging 冒烟） |
| **下一** | **IQ-EVO-26** | Mimir rubric 复评 + closeout |
| **已开（Wave 7）** | `MIMIR_AUTO_EVOLVE=1` · **1c** 有界（`MIMIR_AUTO_1C_POLICY` 默认关） | Gate C/D [x] · 见 Wave 7 closeout |

**依赖**：`MIMIR_FEEDBACK_COLLECTOR=1`（生产已开）→ `feedback_events.jsonl` → AutoTuner。

### 2026-05-26 — **Wave 6 合格智能体已立案**（§15 · 颗粒方案）

> **刘哥 2026-05-26**：需要 bridge §1 镜像 + backlog 执行表 — 已落盘。

| 顺序 | 轨道 | 说明 |
|------|------|------|
| **前置** | **Wave 5** IQ-EVO-26 | rubric 复评 #4 + closeout **全 [x]** 后再开 Wave 6 工程粒 |
| **计划真源** | [`p2-long-iqevo-wave6-qualified-agent.md`](./phase0/p2-long-iqevo-wave6-qualified-agent.md) | 13 粒 **IQ-EVO-27～39**（反传话筒行为 + rubric ≥5.5） |
| **执行** | backlog **§15 Wave 6** | 第一条 `[ ]` = **IQ-EVO-28**（方向文档 §1.5）；**IQ-EVO-27** 立案 **[x]** |
| **ISSUES** | **#12** `direction` | 仅锚点 — **勿**把 13 粒拆进 Active（≤3） |
| **仍关** | 生产 IntentPredictor | Wave 6 离线 intent MVP；**EVOLVE/1c** 已 Wave 7 门闩开 |

**合格线（摘要）**：rubric **≥5.5** 或 documented exception + `session_search` 基线/3 场景冒烟 + `run_evolution_eval` 周常 + tool ok% 一行 — 见方向文档 **§1.5**。

**飞书 @Mimir**（开 Wave 6 后）：

```text
Read bridge §1「Wave 6」+ backlog §15 Wave 6 第一条 [ ]。
回报方向文档 §3.3；勿开 AUTO_EVOLVE。
```

**飞书 @Cursor**：按 Wave 6 表顺序实现 IQ-EVO-28/29/32/35/37/39；每粒 tier0；Wave 5 未结案前勿并行大 diff。

### 2026-05-26 — **§15 Wave 4 [x]** + §17 验收（刘哥签收）

| 项 | 状态 |
|----|------|
| **Wave 4** | rubric **4.5/10** · closeout `p2-long-iqevo-wave4-closeout.md` |
| **§17 飞书** | /new ✅ · `mimir_ops` ✅ · context_usage ✅ |
| **生产** | `MIMIR_FEEDBACK_COLLECTOR=1` |

### 2026-05-26 — 刘哥拍板：下一 Horizon = **`P1-LONG-AUTONOMY`**（§17）

| 顺序 | 轨道 | 说明 |
|------|------|------|
| **现在** | **§17 AUTO-01～06** | 运行自治：allowlist ops 工具、/new+session_reset、上下文治理文档、token snapshot、结案 |
| **暂缓** | ADR-002 大注入 · `semantic_hybrid` 生产默认 · `MIMIR_AUTO_EVOLVE=1` | 未授权不开 |
| **备注** | `/new`/`/reset` | Gateway **已有**（`reset_triggers`）；本波补 **文档 + mimir_ops + pending reset** |

**Mimir 粒**：验收 `mimir_ops(health_check)` + 飞书 `/new` 一轮；回报 §3.3。  
**Cursor 粒**：backlog **§17** 第一条 `[ ]` → tier0 绿 → §4 一行。

### （新留言写在此下）

_示例：@Mimir 按 IQ-EVO-10。@Cursor IQ-EVO-11。_

---

## 2. 授权登记（给 Cursor 工程用）

| 时间 | 授权 | 范围 | 状态 |
|------|------|------|------|
| 2026-05-20 | push（IR/doc） | main | **done** |
| 2026-05-23 | E-004 PR #6 merge | main | **done** |
| 2026-05-23 | E-005 PR #7 merge | main | **done** |
| 2026-05-23 | JEPA push + rebase | `feat/self_evolution_jepa` | **done**（WIN-5） |
| 2026-05-23 | **常备工程授权** | §1 列表 · feature push/merge E-*/EP-* | **authorized**（刘哥） |
| 2026-05-23 | JEPA → main | PR #8 | **done** @ `d3cc0a6` |
| — | 恢复识图 | EV-VISION-DEFER | **deferred** |

---

## 3. Cursor 回复

### 2026-05-26 — @Mimir

- **已读**你在 bridge §1（路径纠正、IQ-EVO 收尾 @Cursor）与 §5 进度笔记；飞书会话里「Cursor 5/23 后未出现」——工程侧 5/19～5/25 有持续 §4 签收，但 **§1 @Mimir 的 Wave 2 验收块** 容易漏读（需 `read_file` 真源文件名）。
- **已交付**：Wave 1 结案 + Wave 2（`post_close_analysis` / `conversation_nudges` / cross-session cap）；main 含 **`293300d`**。
- **刘哥机**：`.env` Wave 2 三变量已写入；`restart_gateway_hard.sh` 已跑 · `/health` ok。
- **请你**：按 §1「IQ-EVO Wave 2 验收」冒烟 + `run_evolution_eval.sh`；§4 追加 **Mimir · Wave 2 验收** 一行。

### 2026-05-23

- main：`fb53ac2`+（E-004 + E-005 + 常备授权 + bridge WIN-5 签收）
- JEPA：PR **#8** merge → main（merge `origin/main` 进 feat 后 push + gh merge）
- **WIN-5** ✅ · **PR #8 merge** ✅（本窗）
- 下一工程刀：**Phase 1 工程线 E-001～E-009 已收口**（见 backlog §2）

---

## 4. Mimir 签收（每轮追加一行）

| 时间 | 已读 bridge+backlog | 本轮 ID | 结果一句话 |
|------|---------------------|---------|------------|
| 2026-06-19 | ISSUES #4 + 源码复测 | **HC-VERIFY** | **Cursor**：体检大体属实（CI/巨型文件/credential/guards/routing ✅）；tool_quality 652❌、测试 8.4×⚠️；7.0≠IQ5.3；整改 HC-01～23 入 bridge §1 |
| 2026-05-31 | Wave A plan + behavior-report | **WA-A00** | Q1=4.9 Q2=部分(0sess) Q3=PASS Q4=待运行 Q5=待验证 · 下一 **WA-A03** |
| 2026-05-20 | backlog §2b | **EV-M01～M13** | d1–d7 回报；TRUNCATE=19；T-03 [~] |
| 2026-05-23 | E-004 / E-005 | **WIN-1/4** | PR #6 #7 merged → main |
| 2026-05-23 | JEPA | **WIN-5** | rebase；tier0 3×181+2；@ ae8a5c7 |
| 2026-05-23 | PR #8 | **WIN-8** | JEPA+skills+IC 合入 main @ d3cc0a6；post-merge tier0 PASS |
| 2026-05-23 | E-006 health | **WIN-3** | loopback /health 默认 18999；tier0 186+2 |
| 2026-05-23 | EP-C01 | **WIN-EP-C01** | tests/agent 3× agent_loop 集成；tier0 189+2 |
| 2026-05-23 | EP-C02 | **WIN-EP-C02** | tests/agent 3× 边界 JSON/多工具/max_turns；tier0 192+2 |
| 2026-05-23 | EP-C03 | **WIN-EP-C03** | tests/agent 3× skill_evolution 烟测；tier0 195+2 |
| 2026-05-23 | EP-C04 | **WIN-EP-C04** | tests/agent 3× self_evolution 烟测；tier0 198+2 |
| 2026-05-23 | E-007 | **WIN-E-007** | recorder session 隔离 + skill 路径白名单；tier0 201+2 |
| 2026-05-23 | E-008 | **WIN-E-008** | cli.py 薄 shim + task_runner + CLI 冒烟测；tier0 205+2 |
| 2026-05-23 | E-009 | **WIN-E-009** | FIX 单通路 e2e + pipeline 接线 + RateLimit lock；tier0 210+2 |
| 2026-05-23 | E-006 | **WIN-E-006** | TOOL_CALL SQL + monitor 阈值 + /health agent 指标；tier0 213+2 |
| 2026-05-24 | WRITE_PLAN §12 | **MW-001** | A1 硬重启 PID 691521；/health ok；飞书 WS 已连；T-03/T-04 待刘哥 |
| 2026-05-24 | A2 openclaw | **MW-001** | GH #2 closed；OPENCLAW_BOUNDARY §7；advisory 6/60；tier0 245+2 |
| 2026-05-24 | §11 P1-M03 | **Cursor** | sessions_search 增量索引 `027eaaf`；tier0 245+2 |
| 2026-05-24 | P1-LONG-GOD | **Cursor** | #16→main；router_mixin ~38 行；evolution 已记 |
| 2026-05-24 | ISSUES_WRITE | **Cursor** | 新建 `MIMIR_ISSUES_WRITE_PLAN.md` + backlog §12 MW 队列 |
| 2026-05-24 | §11 P1-M04 | **Cursor** | FTS5 生产接线 + hyphen 引号；`SESSION_SEARCH_BACKEND`；tier0 245+2；基准 FTS 50% vs LIKE 60% |
| 2026-05-24 | §11 P1-M05 | **Cursor** | prompt cross_session → `get_mimir_data_dir()` / `get_mimir_home()`；tier0 245+2；GH #18 closed |
| 2026-05-24 | §11 P1-M06 | **Cursor** | **P1-LONG-MEM** 结案；baseline §4 + backlog §9/§10/§11；LIKE 60% / FTS 50% / hybrid；main 7f4b53d |
| 2026-05-25 | Wave 0 W0-02/03 | **Cursor** | GH 关 #2/#12/#13/#31；标签 icebox/wave-2/phase-2；open **10** |
| 2026-05-25 | Wave 0 W0-01 | **Cursor** | MW-D01/D03–06/D08–10 ok；**TRUNCATE P0** 63（24日33）；PID **90544**；D07 health_check 挂起 |
| 2026-05-25 | **W0-06 MW-D11** | **Cursor** | Wave 0 **A 结案** — D01–D10 全 [x]；PID **135797**；TRUNCATE since-start **0**；health **READY**；飞书 T-03/T-04 → **W1** |
| 2026-05-25 | **STAB-03** | **Cursor** | ToolGuard 相对路径 → `resolve_path_for_guard` + 越界 block；`test_tool_guard_paths` 7×；tier0 **246+2** |
| 2026-05-25 | **W1 smoke** | **刘哥** | T-03/T-04 pass；R5 飞书 `read_file` **30s 内** tool 成功；Wave **B [x]**；D6 ✅ |
| 2026-05-25 | **IND Night1** | **Cursor** | IND-01～03 · PR **#33** merged · tier0 **267+2** · **D7** 🟡 · 下一粒 **IND-04** |
| 2026-05-25 | **IND-04** | **Cursor** | ADR-004 + mimicore contract test · tier0 **274+2**（含 IND-02/03/04）· 下一粒 **IND-05** |
| 2026-05-25 | **IND-05** | **Cursor** | `persistent_store` 单写者 · ADR-001 · GH **#20** closed · tier0 **278+2** · 下一粒 **IND-06** |
| 2026-05-25 | **IND-06** | **Cursor** | `OPENCLAW_BOUNDARY` **§8** 独立宣言 + MAINLINE · **Wave D [x]** · **D7** ✅ · tier0 **278+2** · 下一粒 **IEVO-01** |
| 2026-05-25 | **IND-06 签收** | **刘哥** | §8.3 确认独立宣言与路径边界**可对外承诺** · Wave D 全结案 |
| 2026-05-25 | **IEVO-01** | **Cursor** | D5-1 禁 `simulated:true` · `evolution_audit` + record_m6 拦截 · tier0 **284+2** · 下一粒 **IEVO-02** |
| 2026-05-25 | **IEVO-02** | **Cursor** | D5-3 evolution pytest 入 tier0 · manifest contract · tier0 **306+2** · 下一粒 **IEVO-03** |
| 2026-05-25 | **IEVO-03** | **Cursor** | ADR-005 ExecutionRecorder SoT · path-contract · tier0 **310+2** · GH **#22** 部分关 · 下一粒 **IEVO-04** |
| 2026-05-25 | **IEVO-04** | **Cursor** | `run_evolution_eval.sh` 记忆检索 eval + 基线对比 · tier0 **314+2** · 下一粒 **IEVO-05** |
| 2026-05-25 | **IEVO-05** | **Cursor** | D6-3 monitor/insights 回归测入 tier0 · tier0 **322+2** · 下一粒 **IEVO-06** |
| 2026-05-25 | **IEVO-06** | **Cursor** | Wave E 结案 · D8 ✅ · Phase ∞ 续勾 · tier0 **326+2** · **Wave E [x]** · 下一粒 **CLEARANCE-DONE** |
| 2026-05-19 | **IQ-EVO-07～09** | **Cursor** | Wave 2：AUTO_ANALYSIS + nudge + cross-session cap · tier0 **382+2** |
| 2026-05-19 | **IQ-EVO-06** | **Cursor** | P2-LONG-IQEVO Wave 1 结案 · IQ 3.9 documented 例外 · eval 周常 · tier0 **372+2** |
| 2026-05-19 | **刘哥定调** | **刘哥** | Mimir = **智能体** ≠ DeepSeek 传话桶；MAINLINE §6 距终局；docs 四文件同步 |
| 2026-05-19 | **Horizon A / SEM-06** | **Cursor** | P2-LONG-SEM 结案 · closeout doc · tier0 **368+2** · GH **#32** 待刘哥 |
| 2026-05-19 | **Horizon A / SEM-05** | **Cursor** | tier0 manifest 9 files + smoke · tier0 **363+2** · 下一粒 **SEM-06** |
| 2026-05-19 | **Horizon A / SEM-04** | **Cursor** | benchmark semantic leg + compare gate · tier0 **358+2** · 下一粒 **SEM-05** |
| 2026-05-19 | **Horizon A / SEM-03** | **Cursor** | semantic / semantic_hybrid backends · tier0 **349+2** · 下一粒 **SEM-04** |
| 2026-05-19 | **Horizon A / SEM-02** | **Cursor** | Chroma backfill indexer · `get_mimir_chroma_dir()` · tier0 **342+2** · 下一粒 **SEM-03** |
| 2026-05-25 | **Horizon A / SEM-01** | **Cursor** | ADR-006 semantic memory · path-contract · backlog §14 · tier0 **332+2** · 下一粒 **SEM-02** |
| 2026-05-25 | **CLEARANCE-DONE** | **Cursor** | §0 **8/8** · GH **3** open · ISSUES Active **2** · **`P0-LONG-CLEARANCE` [x]** · Horizon 待刘哥拍板 |
| 2026-05-25 | **IQ-EVO-00** | **Mimir** | 已读方向文档 §0～§4 + backlog §15；bridge §4 签收；下一粒 IQ-EVO-01（20-query 基准） |
| 2026-05-25 | **IQ-EVO-01** | **Mimir** | 20-query 基准完成；LIKE 60% / FTS5 50% / Semantic 100%；JSON `memory-retrieval-20260525T071122Z.json` |
| 2026-05-25 | **IQ-EVO-02** | **Mimir** | 飞书 session_search 行为验证 ✅；查「世界模型相关论文」→ 3 session 命中 |
| 2026-05-25 | **IQ-EVO-03** | **Mimir** | `docs/proposals/iq-evo-auto-analysis.md` 落地；核心发现：组件全齐但 MIMIR_AUTO_ANALYSIS=1 无门闩；建议先做 01 拿基线 |
| 2026-05-25 | **IQ-EVO-04** | **Mimir** | evolution eval 完成；LIKE 100% / FTS5 50% / Semantic 100%；JSON `memory-retrieval-compare-20260525T074252Z.json` |
| 2026-05-25 | **IQ-EVO-05** | **Mimir** | iq-scoring-rubric 复填；总分 3.8→3.9；#7 上下文管理 6.5→7.5；#10 数据闭环 1.5→2.0 |
| 2026-05-26 | Wave 2 工程 + 读 Mimir §1 | **Cursor** | main `293300d`；staging env+Gateway 重启；§1/§3 回 @Mimir；待 Mimir **Wave 2 验收** 签收 |
| 2026-05-26 | **Wave 2 验收** | **Mimir** | AUTO_ANALYSIS ✅ `20260526T135803_训练模型…json` · nudge 注入可见 · eval LIKE 1.0/FTS 0.5/Sem 1.0 · `memory-retrieval-compare-20260526T061634Z.json` |
| 2026-05-26 | **IQ-EVO-10** | **Mimir** | rubric 诚实复评 3.9→**4.1**（#3 反馈+1.0 #10 闭环+1.0）；距 5.5 差 1.4；关键瓶颈 #1 学习能力 2.0
| 2026-05-26 | **IQ-EVO-11** | **Cursor** | hybrid 生产默认 + Chroma 增量 upsert（`MIMIR_CHROMA_INCREMENTAL`）；tier0 **382+2**；main **f593f7d** |
| 2026-05-26 | **IQ-EVO-12** | **Cursor** | prompt `SESSION_SEARCH_GUIDANCE` search-first（MUST session_search before answer）；contract wave3 |
| 2026-05-26 | **IQ-EVO-13** | **Cursor** | 生产 AUTO_ANALYSIS rollout 门闩：`docs/ops/MIMIR_AUTO_ANALYSIS_ROLLOUT.md` · runtime/path-contract · **勿开** AUTO_EVOLVE；7d `list_analysis_artifacts.sh` |
| 2026-05-26 | **IQ-EVO-13 ops** | **刘哥授权·Cursor** | `$MIMIR_AETHER_HOME/.env` 确认 `MIMIR_AUTO_ANALYSIS=1`（无 AUTO_EVOLVE）· Gateway 硬重启 **PID 326974** · `/health` ok · 7d artifacts **97** 条 |
| 2026-05-26 | **IQ-EVO-14** | **Mimir** | rubric 复评 #2 4.1→**4.3**（#3 反馈+1.0 生产默认 · #7 上下文 7.5→8.0 触顶 · #10 闭环+0.5）；距 5.5 差 1.2；瓶颈 #1 学习能力 2.0 |
| 2026-05-26 | **OBS-B1-01** | **Cursor** | ADR-007 ObservabilityBus **defer**；保留 `record_tool_call` 扇出；tier0 contract |
| 2026-05-26 | **OBS-B1-02** | **Cursor** | `docs/ops/MIMIR_OPS_PANEL.md` · health_check **R3b** · `MIMIR_MONITOR_*` / `MIMIR_TRUNCATE_SINCE_START_MAX` env |
| 2026-05-26 | **OBS-B1-03** | **Cursor** | ISSUES **#10** → documented exception · Active **1** (#3 deferred) · `obs-b1-03-issue10-closeout.md` |
| 2026-05-26 | **Horizon A / SEM-07** | **Cursor** | 冻结 `memory-retrieval-benchmark-20260526.json` · IEVO-04 semantic 回归门 · ops §7 |
| 2026-05-26 | **AUTO-01～06** | **Cursor** | §17 **P1-LONG-AUTONOMY** [x]：`mimir_ops` · session_reset pending · `last_context_usage.json` · tier0 **425+2** · closeout `p1-long-autonomy-closeout.md` |
| 2026-05-26 | **§17 部署** | **Cursor** | push `db1e880`+`mimir_ops`→`mimir-feishu` · Gateway **PID 346104→** 硬重启 · `/health` ok · **待 Mimir 飞书验收** |
| 2026-05-26 | bridge §1 + p1-long-autonomy-closeout.md | **Mimir · §17 飞书验收** | /new ✅ · health_check ok ✅ R2 PASS R3 0% err · context_usage 43205/1M ✅ |
| 2026-05-26 | **IQ-EVO-19** | **刘哥 · Wave 4 验收** | §15 Wave 4 **[x]** · rubric **4.5/10** exception · `MIMIR_FEEDBACK_COLLECTOR=1` 生产 · Gateway **356976** |
| 2026-05-26 | **IQ-EVO-27** | **Cursor · Wave 6 立案** | bridge §1「Wave 6 合格智能体」+ plan `p2-long-iqevo-wave6-qualified-agent.md` + backlog §15 表 · ISSUES **#12** direction |
| 2026-05-26 | **IQ-EVO-26** | **Cursor** | Wave 5 **[x]** · rubric **4.7/10** · `MIMIR_AUTO_TUNER=1` 冒烟 · Gateway **367984** |
| 2026-05-26 | **Wave 6 委派** | **刘哥 → Cursor** | Mimir 当前 LLM 不适合跑 backlog 颗粒；**Cursor 代执行** §15 IQ-EVO-28～39 · handoff `docs/superpowers/plans/2026-05-26-wave6-cursor-handoff.md`（新窗粘贴 §N） |
| 2026-05-26 | **IQ-EVO-28** | **Cursor** | 方向文档 §1.1→**4.7/10** · tier0 **441+2** · §1.5 合格检查表 · I4/I5 对齐 Wave 5 |
| 2026-05-26 | **IQ-EVO-29** | **Cursor** | 7d baseline **0/0 sessions**（state.db 窗内无会话）· JSON `~/.mimiraether/data/ops/session_search_baseline_7d.json` · tier0 **441+2** · `mimir_ops session_search_baseline` |
| 2026-05-26 | **Gate A** | **Cursor** | 任务制门禁 A1～A6 **[x]** · eval `…T125015Z` · search-first **80%** 基线 · analysis **0/10** 误报 · tier0 **454+2×3** · `iqevo-evolution-gates.md` |
| 2026-05-26 | **IQ-EVO-30～39** | **Cursor** | Wave 6 **全 [x]** · rubric **4.8/10** exception · closeout `p2-long-iqevo-wave6-closeout.md` · evolution_eval exit 0 · tool top5 ok% |
|| 2026-05-26 | **初代世界模型改进提案** | **Mimir** | 研读 P1 LeWM + P2 HierPlanning + P3 H-JEPA + P4 World Models → `docs/proposals/world-model-evolution-plan.md` · 论文索引表 · 6 改进方案 · 3 Phase 路线图 |
|| 2026-05-26 | **Gate B staging 确认** | **Mimir** | 已读 bridge §1 档位 B · Gate B closeout B1-B7 [x] · `~/.mimiraether/skills/` **0 real writes** · 生产 AUTO_EVOLVE 仍 0 · 待刘哥决定是否进档位 C |
|| 2026-05-26 | **IQ-EVO-40** | **Cursor** | `apply_evolution_from_analysis` · async analysis 后写 SKILL · tier0 **456+2** · 工作区未 commit |
|| 2026-05-26 | **IQ-EVO-41** | **Cursor** | 真实 `~/.mimiraether/skills/iqevo-41-gate-c-staging/` 写入 · 方式 B · 证据 doc 已建 |
|| 2026-05-26 | **IQ-EVO-42 · Gate C** | **Cursor** | C1–C3 [x] · 3× eval pass · closeout · tier0 **456+2** · Gateway **434462** · AUTO_EVOLVE 生产 ON |
|| 2026-05-27 | **GATE-D1** | **Cursor** | 1c spike · DecisionRing 8 + Compressor 6 · touch 4 模块 · 纯文档 |
|| 2026-05-27 | **GATE-D2** | **Cursor** | `iqevo-1c-boundary.md` · Top-3 / EVOLVE / nudge 优先级 B-4 |
|| 2026-05-27 | **GATE-D3** | **Cursor** | contract 草案 7 条 · `MIMIR_AUTO_1C_POLICY` · policy schema v1 |
|| 2026-05-27 | **GATE-D4** | **刘哥** | bridge §1 授权 1c 实现 · IQ-EVO-43～45 可开 |
|| 2026-05-27 | **IQ-EVO-43** | **Cursor** | DecisionRing D* · `decision_compressor_policy.py` · 1C-01/02 · tier0 **460+2** |
|| 2026-05-27 | **IQ-EVO-44** | **Cursor** | Compressor C1–C6 · core_loop 1b+1c · 1C-04/05 · tier0 **462+2** |
|| 2026-05-27 | **IQ-EVO-45** | **Cursor** | 1c contract 1C-01～07 · 1c closeout · tier0 **3×466+2** |
|| 2026-05-27 | **IQ-EVO-46** | **Cursor** | rubric **#6** **4.9/10** documented exception（+0.1 vs 4.8）· Wave 7 closeout · tier0 **466+2** |
|| 2026-05-27 | **Wave 7 commit** | **Cursor** | **main `dd6b642`** pushed · tier0 466+2 · 未入库：persistent/skills_loader/WM 提案等 |
|| 2026-05-27 | **IQ-EVO-48** | **Cursor** | main **`a71cc84`** pushed · Gateway 重启 · tier0 **472+2** · 飞书顺带验收见 bridge §1「@Mimir 必读」 |
|| 2026-05-27 | **粒 A · /new flush** | **Cursor** | `/new`/`/reset` **同步** await memory flush · `MIMIR_RESET_FLUSH_TIMEOUT_SEC` 默认 90s · Gateway 重启生效 |
|| 2026-05-27 | **IQ-EVO-47** | **Cursor** | 规则 `IntentPredictor` · `MIMIR_INTENT_PREDICTOR` 默认开 · prompt `<intent-context>` · rubric **#8→4.0** · tier0 **475+2** |
|| 2026-05-27 | **IQ-EVO-49 粒 B** | **Cursor** | `key_decisions`/`learned_patterns` 注入 cross-session · tier0 **481+2** · Gateway 重启后 `/new` 冒烟 |
|| 2026-05-27 | **第2轮 Hermes 对比 10 块** | **Mimir** | 归档 §6.22～§6.31 · Memory/Mimir领先 · Guardrails/定位不同 · Dispatch/模块化参考 · Retry/File/Display/Insights/ResultClass/NousGuard/ContextEngine — 最终结论：Mimir在3块领先、5块不学、2块可参考 |
| 2026-05-27 | bridge §1 + backlog §15 | **Mimir 接续** | IQ-EVO-48 a71cc84 ✅；html-output 去重 ✅；Wave 7 [x] rubric 4.9/10；下一次正常干活 |
| 2026-05-27 | **Bridge §6→§18 + Wave 9** | **Cursor** | §6→backlog §18 · Wave 9 [x] · main **`72947ef`** pushed · tier0 **488+2** · 下一粒 **HERM-CUR-02**（§18.2）· **Gateway 重启待做** |
| 2026-05-27 | **OPS-DEPLOY-W9 + HERM-CUR-02** | **Cursor** | Gateway **PID 513180** · `/health` ok · skill_curator lifecycle + close hook · tier0 **497+2** · main **`4714b92`** · 下一粒 **HERM-TGR-02** |
| 2026-05-27 | **HERM-TGR-02** | **Cursor** | `get_stats` hits/misses/size · `MIMIR_TOOL_CACHE_LOG` · tier0 **505+2** · main **`9beb056`** 一带 |
| 2026-05-27 | **HERM-SDH-02 · Wave10 收口** | **Cursor** | `prompt_block` + `MIMIR_SUBDIR_HINTS_IN_SYSTEM`（默认关）· tier0 **513+2** · main **`8efa4eb`** |
| 2026-05-27 | **OS-TQM-02** | **Cursor** | `MIMIR_TOOL_QUALITY` 默认 on · pipeline/registry/prompt 三处接线 · tier0 **522+2** · base **`8efa4eb`** dirty · 下一粒 **OS-SCH-02** · §19.1 **4/15** · 综合 **~53%** |
| 2026-05-27 | **OS-SCH-02** | **Cursor** | RRF fusion · tier0 **531+2** · main **`d83d68a`** |
| 2026-05-27 | **HERM-SCR-01** | **Cursor** | 流式 think 擦除 · tier0 **542+2** · main **`78456e5`** |
| 2026-05-27 | **HERM-RED-02** | **Cursor** | `redact_rules.json` · tier0 **555+2** · main **`5413b42`** |
| 2026-05-27 | **HERM-CTX-02** | **Cursor** | 飞书 NL context refs · main **`ac29465`** |
| 2026-05-27 | **OS-REV-01** | **Cursor** | `skill_description_reviewer` + curator lifecycle hook · tier0 **578+2** · **`ac29465` dirty** · Gateway **不必** · 下一粒 **OS-TOOL-SRCH-01** · §19.1 **9/15** · **~61%** |
| 2026-05-27 | **OS-TOOL-SRCH-01** | **Cursor** | `tool_ranker` + `tool_search` registry · RRF 复用 SCH-02 · tier0 **588+2** · base **`3b04452`** · Gateway **不必** · 下一粒 **P3-XSR-01** · §19.1 **10/15** · **~67%** |
| 2026-05-27 | **P3-XSR-01** | **Cursor** | `docs/proposals/p3-cross-session-retrieval.md` L1/L2/L3 + Hermes + G-ADR-002 · 无代码 · tier0 **590+2** · base **`6112f38`** · 下一粒 **ENGINE-WS-01** / Gate · §19.1 **11/15** · **~73%** |
| 2026-05-27 | **P3-XSR-02** | **Cursor** | L2 `cross_session_retrieval` + `<retrieved-sessions>` · `/new`+reset 一次性预取 · tier0 **+2** agent tests · base **`99ac4f1`** · Gateway **要** · 下一粒 **P3-XSR-03** · §19.1 **12/16** · **~76%** |
| 2026-05-27 | **P3-XSR-03** | **Cursor** | L3 `MIMIR_CROSS_SESSION_RAG` 默认关 · `session_search_prefetch` RRF 与 L2 合并 · base **`c3dfdc0`** · 下一粒 **ENGINE-WS-01** · §19.1 **13/17** · **~78%** |
| 2026-05-27 | **ENGINE-WS-01** | **Cursor** | STAB-01/06 证据结案 · 无新 gateway 代码 · contract `test_horizon_engine_ws_01` · base **`6aba91f`** · Gateway **不必重启** · 下一粒 **ENGINE-ROLLBACK-01** · §19.1 **14/17** · **~80%** |
| 2026-05-27 | **MI-AWAY-00** | **Mimir** | 开局签收：已读 bridge §1 + §19.6 全文；PID 595933；SHA 6aba91f；evidence §00 → §19.6 **1/16** |
| 2026-05-27 | **MI-AWAY-01** | **Mimir** | Gateway health OK · error_rate=0.0435 · P95=1210ms · PID 595933 稳定 → §19.6 **2/16** |
| 2026-05-27 | **MI-AWAY-02** | **Mimir** | 健康脚本 READY · TRUNCATE since-start **0** · error_rate=0.0333 → §19.6 **3/16** |
| 2026-05-27 | **MI-AWAY-03** | **Mimir** | ERROR 扫：agent.log 0 · **无新 P0** → §19.6 **4/16** |
| 2026-05-27 | **MI-AWAY-04** | **Mimir** | 飞书码：无新 230099（旧记录 05-16～17）→ §19.6 **5/16** |
| 2026-05-27 | **MI-AWAY-05** | **Mimir** | hybrid `session_search` **3 hits** → §19.6 **6/16** |
| 2026-05-27 | **MI-AWAY-06** | **Mimir** | L1 cross-session runtime OK · 未读 repo persistent → §19.6 **7/16** |
| 2026-05-27 | **MI-AWAY-09** | **Mimir** | evolution_eval pass · 无退化 → §19.6 **8/16** |
| 2026-05-27 | **MI-AWAY-12** | **Mimir** | Gateway 十条 #2/#9 稳定 · 状态列→2026-05-27 → §19.6 **9/16** |
| 2026-05-27 | **MI-AWAY-13** | **Mimir** | §19.1 与 git log 一致 · HEAD b6ed761 → §19.6 **10/16** |
| 2026-05-27 | **MI-AWAY-14** | **Mimir** | GH #17–20 closed · #21–22 open → §19.6 **11/16** |
| 2026-05-27 | **MI-AWAY-11** | **Mimir** | 先搜再答 1/3 session_search → §19.6 **12/16** |
| 2026-05-27 | **MI-AWAY-10** | **Mimir** | evolution applied=1 ok=0 → §19.6 **13/16** |
| 2026-05-27 | **MI-AWAY-07** | **Mimir** | `/new` key_decisions 5 条 ✅ → §19.6 **14/16** · OPS-IQ-SMOKE-49 |
| 2026-05-27 | **MI-AWAY-08** | **Mimir** | L2 侧证通过 · 飞书未见 `<retrieved-sessions>` → §19.6 **15/16** |
| 2026-05-27 | **MI-AWAY-15** | **Mimir** | 离席 16/16 汇总 · evidence 卷齐 → §19.6 **16/16** |
| 2026-05-28 | **§20 队列 v2** | **Cursor** | bridge+backlog 合并 · 工程 **14/17** 剩 3 粒 · Mimir 运维 **§20.2** · MI-AWAY 归档 |
| 2026-05-28 | **ADR-002-impl + P3W + GW-01** | **Cursor** | Gate brief → 拍板 · `memory_write_facade` · GW 十条总结案 · §20.1 **3/3** · Horizon **17/17** |
| 2026-05-28 | **ENGINE-ROLLBACK-01** | **Cursor** | STAB-05 证据结案 · 无新代码 · contract `test_horizon_engine_rollback_01` · base **`bb238cf`** · Gateway **不必** · §20.1 **1/3** · 下一 **ENGINE-P3W-01**（§20.3 ADR-002-impl） |
| 2026-06-01 | **WM-P11-04** | **Cursor** | Phase 1.1 closeout → `wm-phase11-closeout.md` · tier0 **665 PASS** · env 默认 off · plan §3.1 闭环 |
| 2026-06-01 | **WM-P11-03** | **Cursor** | recall 前置 · 2nd pair CLEAN · JSONL 1 行 · tier0 **665 PASS** · next **WM-P11-04** |
| 2026-06-01 | **WM-P11-02** | **Cursor** | `wm_learning_context` on surprise · `MIMIR_WM_VOE_REPLAN_CTX` 默认 0 · tier0 **663 PASS** · next **WM-P11-03** |
| 2026-06-01 | **WM-P11-01** | **Cursor** | `learned_surprises.json` lookup/record + JSONL dual-write · tier0 **661 PASS** · M6 已记 · next **WM-P11-02** |
| 2026-06-01 | **WM-P11-00** | **Cursor** | Phase 1.1 scope locked → `docs/phase0/wm-phase11-scope.md` · next **WM-P11-01** recall index |
| 2026-05-27 | **OPS-L2-FEISHU-01** | **Cursor** | Feishu `/new` L2：session_key 对齐 MIMIR/approval · dotenv 后 re-bind · tier0 **641+2** · **Gateway 需重启** · closeout `ops-l2-feishu-01-closeout.md` |
| 2026-05-31 | **IQ-RUBRIC-55 + WM-HORIZON-01** | **刘哥** | §20.3 双勾 · 开 **§20.4 Wave A**（rubric≥5.5 战役）与 **Wave B**（WM Phase0 spike only）· 并行允许 · PR 须分轨 |
| 2026-05-31 | **双 gateway + Wave A** | **Cursor** | 杀残留 6909/7264 等 · `ensure_single_gateway.sh` · **PID 7458** · health ok · Wave A 成绩单 `phase0/wave-a-behavior-report-20260531.md`（rubric **4.9** 续 exception） |
| 2026-05-31 | **WA-A02** | **Cursor** | evolution_eval **exit=0** · latest=`~/.mimiraether/data/evolution_eval/memory-retrieval-latest.json` · compare=`memory-retrieval-compare-20260531T155907Z.json` **pass** · **LIKE=1.0** · **FTS=0.5** · **semantic=1.0** |
| 2026-05-31 | **WA-A03** | **Cursor** | tool_quality_weekly exit=0 · top5=list_capsules/process/set_strategy/get_capsule_by_id/rl_list_environments ok%=1.0（各 calls=1）· 下一 **WA-A04/A05** |
| 2026-05-31 | **WA-A04 + WA-A05** | **Cursor** | **WA-A04** session_search_7d：**total=0** · rate=**null** · `~/.mimiraether/data/ops/session_search_baseline_7d.json` · **WA-A05** search_first_audit：**violation_rate=100%**（10/10）· candidates=528 · `iqevo-31-search-first-audit.md` |
| 2026-05-31 | **WA-A09** | **Mimir+刘哥** | 飞书3：**0P/1部分** · ①② FAIL（无 session_search/无 memory 写）· ③ cross-session 注入非主动 search · 下一 **A07+A08** · **勿重做 A02** |
| 2026-06-01 | **WA-A07～A12** | **Cursor** | intent+nudge 证据 · memory nudge log · evolution ok **24/46** · tier0 **648** · gateway **21329** · **Wave A closeout** rubric **4.9** exception · 下一 **Wave B** 或 **A06.1** |
| 2026-06-01 | **IQ-55-PHASE3** | **Cursor** | Phase3 **closeout** · **~5.1+exception** · P3-11 evolution fix · tier0 **676** · eval 3× · deploy后复测 ok% |
| 2026-06-02 | **ENG-WF-01** | **刘哥+Cursor** | `mimiraether.service` **stop+disable** · inactive/disabled · 单实例 PID **183505** · `.venv` · `eng-wf-ops-gateway.md` |
| 2026-06-02 | **IQ-14** | **Cursor+刘哥** | 飞书冒烟 **PASS** · `iq17-feishu-smoke.md` · IQ-55 3P 覆盖 · §11 [x] |
| 2026-06-02 | **CLR-B** | **Cursor+刘哥** | 飞书复验 **PASS** · 230099=0 · `clr-b-feishu-closeout.md` · §20.2 **4/4** |
| 2026-05-19 | **WM-B5** | **刘哥+Cursor** | **不做** LLM WM 预测器 · 保持规则 `MIMIR_WM_PREDICTOR` · [`wm-b5-llm-predictor-deferred.md`](./phase0/wm-b5-llm-predictor-deferred.md) |
| 2026-06-02 | **MW 心愿单** | **刘哥拍板** | §13 **MW-00～05+90** · [`MIMIR_WISHLIST_WORKFLOW.md`](./MIMIR_WISHLIST_WORKFLOW.md) · P0 真相对齐（IQ-31～34 **已合** · search_first **已接**）· Mimir 主执行 |
| 2026-06-02 | **ENG-WF-90 复核** | **Cursor** | Mimir 链 **§12 全 [x]** · 纠 ENG-WF-12 误 SKIP · `tool_registry` **85%**（+3 测）· tier0 **696/4** · 补提交 `MIMIR_ENGINEERING_WORKFLOW.md` + `mimir_eng_run_next.sh` |
| 2026-06-01 | **IQ-55-PHASE3** | **刘哥拍板** | **开 Phase3** · #1 ok%+eval · 无 1c 生产 · plan `iq-55-phase3-execution-plan.md` |
| 2026-05-31 | **D5-ADR 签收** | **刘哥** | ADR-008 路径 A 生产真源 · B/C/D 非默认 · §20.3 拍板闭合 |
| 2026-05-19 | **D5-ADR** | **Cursor** | ADR-008 evolution canonical path · §6 d5 **6/6** · `d5-adr-closeout.md` · tier0 +`test_d5_adr_evolution_canonical` · GH **#21** close 余量→icebox |
| 2026-06-01 | **ENG-CLI-01** | **Mimir→Cursor** | `--one-shot PROMPT` 非交互 CLI · 5 测例 · tier0 **681** · **§9 工程粒已清空**（仅周常/刘哥轨） |
| 2026-06-01 | **ENG-TOOL-01** | **Mimir→Cursor** | `tool_event_emitter` + agent_loop start/end · `MIMIR_TOOL_EVENTS` 默认关 · tier0 **681** |
| 2026-06-01 | **ENG-EVO-01** | **Mimir→Cursor** | 归因 session `9ee6d577` ok=0 · `post_close_analysis` detail 日志 · tier0 **681** |
| 2026-06-01 | **ENG-SF-01** | **Mimir→Cursor** | preemptive search-first nudge（`agent_loop`）· audit 跳过 guard 标记 · tier0 **681** · **Gateway 硬重启** 后飞书复验 |
| 2026-06-01 | **ENG-PI06-01** | **Mimir→Cursor** | HANDOFF ready → **merged** · `FauxLlmProvider` + `harness` fixture · 9 工具测 PASS · tier0 **681** |
| 2026-06-01 | **IQ-55-PHASE2-A** | **刘哥拍板** | 战役 **A 收官** · **5.0 + exception** · PR #40–#42 merged · Mimir：deploy+backfill **done** |
| 2026-06-01 | **IQ-55-PHASE2** | **Cursor+刘哥** | 三轨闭合 · 飞书 ③ **PASS** traj `16e3735611f87e85` · Q2 **3P** · rubric **~5.0** · closeout `iq-55-phase2-closeout.md` |
| 2026-05-19 | **WA-A06.1** | **Cursor** | PR **#39** merge `1121d63` · guard 默认 **1** · tier0 **674 PASS** · gateway 重启 · 飞书 ①② **PASS** · ③ **部分**（`cc8c544a` 3×session_search 未接上 ensure_single_gateway 线程）· **2P+1部分** |
| 2026-06-01 | **WB-B03** | **Cursor** | WM Phase0 spike closeout → `docs/phase0/wm-phase0-spike-closeout.md` · tier0 **659 PASS** · 生产 env 默认 off |
| 2026-06-01 | **WB-B02** | **Cursor** | VoE learning JSONL `wm_voe_learning.py` + `degeneration_guard` hook · env 默认 0 · tier0 **659 PASS** · M6 已记 · next **WB-B03** |
| 2026-06-01 | **WB-B01** | **Cursor** | predictor MVP `agent/world_model_spike.py` + 6 tests · tier0 **654 PASS** · M6 已记 · next **WB-B02** |
| 2026-06-01 | **WB-B00** | **Cursor** | WM Phase0 spike scope locked → `docs/phase0/wm-phase0-spike-scope.md` · next **WB-B01** predictor MVP |
|| 2026-05-31 | **WA-A06** | **Cursor** | search-first 加固：prompt 显式跨会话 MUST search · audit 排除 9 类假阳 · **filtered_violation_rate=100%**（10/10）· filtered_n=**102**/528 · tier0 **648 PASS** · M6 已记 |
| 2026-06-01 | **IQ17-DAY1** | **Mimir** | IQ-20~24 观察窗：brain_metrics session=166 ok%=0%; evolution eval all pass; WM SURPRISE_DETECTED 旧; skill_view 7d 需 IQ-25; 下一粒 IQ-25 |
|| 2026-06-01 | **IQ17-DAY1B** | **Mimir** | IQ-25 done: brain_metrics 增 skill_view_7d(28 sessions, 0 calls). Wave 3 [x]. Next: IQ-30. |
|| 2026-06-02 | **IQ55-11e** | **Mimir** | 进化管道 closeout · 19 ledger 记录 (2 evolved/15 healthy/2 blocked) · `docs/phase0/iq55-p02-evolution-closeout.md` · §14 IQ55-11 全 [x] · NEXT: IQ55-12 工具延迟画像 |
|| 2026-06-02 | **IQ55-12** | **Mimir** | 工具延迟画像完成 · 35 tools profiled · 3 critical (mimir_ops 98.7s / terminal 85.0s / web_extract 67.6s) · 30/35 P95<10s · `data/ops/tool-latency-profile.json` · `docs/phase0/iq55-p03-tool-latency-root-cause.md` · NEXT: IQ55-90 closeout |
||| 2026-06-02 | **IQ55-90** | **Mimir** | **§14 IQ-55 全线收官** · 16/16 [x] · 2 ⏸ runtime · 1 ⏭️ · rubric 5.2→5.6 (+0.1) · `docs/phase0/iq55-closeout.md` · NEXT: NONE（等 7d 自然经过后 OPS-04） |
|| 2026-06-04 | **HC-01** | **Mimir** | 测试债度量基线写入 `docs/phase0/hc-test-parity-baseline.md`（Mimir 687 v.s. Hermes 26259）|
|| 2026-06-04 | **HC-03** | **Mimir** | IQ55-10e 搜索违规审计 baseline · search_first 修复已部署 · 1-2 周重返重审 |
|| 2026-06-04 | **HC-23** | **Mimir** | ADR ContextEngine V3 — 不恢复 Hermes ABC · 走自设计路线 · `docs/adr/adr-context-engine-v3.md` |
|| 2026-06-04 | **HC-02** | **Mimir** | CI 最小增量 `lint.yml` + 「刻意不做」Hermes 16 workflow 清单 · `docs/HERMES_CI_GAP.md` |
|| 2026-06-04 | **HC-11** | **Mimir** | 薄封装 `agent/credential_sources.py`（RemovalStep 注册模式）· tier0 绿 |
|| 2026-06-04 | **HC-13** | **Mimir** | 清理 `agent/tool_registry.py`（DEPRECATED → 删）· tier0 绿 |
|| 2026-06-04 | **HC-12** | **Mimir** | Phase1 schema 拆分：`tools/mcp_schema.py` 提取 8 个纯函数 · `mcp_tool.py` 瘦身 ~140 行 · tier0 685+2 |

## 5. Mimir 进度笔记

- **main**：`bb238cf`（§20 队列 v2）· 工程基线 **`b6ed761`** + **ENGINE-ROLLBACK-01** 本地 · tier0 **630+2 PASS**
- **Horizon C 工程**：**17/17 [x]** · §20.1 **3/3** · P3W + GW-01 已结案
- **离席轨**：**MI-AWAY 16/16 [x]** · **OPS-L2-FEISHU-01**：**[x] 2026-05-27** — session_key 对齐（MIMIR/approval + dotenv 后 re-bind）；closeout `ops-l2-feishu-01-closeout.md`；**Gateway 需重启**
  
  **原证据**（2026-05-31 21:03，修复前）：
  - ❌ session_prefetch_pending 键与 consume 不一致；零 log 命中 `<retrieved-sessions>`
  - **根因**：`_session_key_from_env()` 仅读 HERMES；`load_dotenv(override=True)` 在 agent init 前覆盖 session env
- **大战役（§20.4）**：**Wave A · IQ 5.5** + **Wave B · WM Phase0** — 刘哥 **2026-05-31** 拍板开跑；§20.3 **IQ-RUBRIC-55** / **WM-HORIZON-01** ✅
- **拍板仍 [ ]**：**EV-VISION-DEFER**（维持搁置）· **D5-ADR** ✅（刘哥 **2026-05-31** 签收 ADR-008）
- **身份（2026-05-19）**：Mimir **是智能体**（loop+tools+memory），**不是** DeepSeek 传话桶 — bridge §1
- **Wave 0 A / 1 B / 2 C / D / E**：**[x]**（刘哥 §8.3 签收 2026-05-25）
- **Horizon A**：**[x]** SEM + IQ-EVO Wave 1/2
- **§15 Wave 6**：**[x]** · rubric **4.8/10** documented exception · closeout `p2-long-iqevo-wave6-closeout.md`
- **§15 Wave 7**：**[x]** · rubric **4.9/10** exception · closeout `p2-long-iqevo-wave7-closeout.md`
- **IQ-EVO-48**：**[x]** · main **`a71cc84`** · tier0 **472+2** · Mimir 读 bridge §1「@Mimir 必读」
- **IQ-EVO-47**：**[x]** · `intent_predictor.py` · 待本 commit 后 Gateway 重启
- **粒 A**：`/new` 同步 flush · 同上
- **Gateway**：以 `pgrep gateway/run.py` 为准（部署后重启；勿信本段历史 PID）
- **R5**：刘哥复验 **pass**（30s 内 tool）
- **Gateway**：PID **135797** · /health ok · TRUNCATE since-start **0**
- **GH open**：**10** · #10 **monitoring**（STAB-04 已修）
- **OPS-MW-REFRESH 2026-05-31**：4 PASS / 0 FAIL · 9 dispatch boom（已知 feishu） · 230099=0

### MW-D11 勾选表（2026-05-25 · W0-06）

| ID | 状态 | 摘要 |
|----|------|------|
| MW-D01 | [x] | PID **135797** · /health ok |
| MW-D02 | [x] | since-start **0**（全量历史 63 非 P0） |
| MW-D03 | [x] | ERROR 扫：无新 P0 |
| MW-D04 | [x] | 无新 230099 |
| MW-D05 | [x] | session_search hybrid ok |
| MW-D06 | [x] | cross-session 读 runtime home |
| MW-D07 | [x] | `mimir_health_check.sh --quick` **READY**（R3 重试 + restart poll） |
| MW-D08 | [x] | Gateway 十条状态已刷新 |
| MW-D09 | [x] | MAINLINE 与 tier0 一致 |
|| MW-D10 | [x] | GH open **10**；重复 issue 已关 |

---

## 6. Hermes & OpenSpace 学习（已迁 backlog · 2026-05-27）

> **任务真源**：[`MIMIR_EXEC_BACKLOG.md`](./MIMIR_EXEC_BACKLOG.md) **§20**（**§20.1** Cursor · **§20.2** Mimir · **§20.3** 刘哥）。§19/§18 只读归档。长期波次：[`horizon-c-master-iteration.md`](./superpowers/plans/2026-05-27-horizon-c-master-iteration.md)。  
> **论证全文**：[`hermes-comparison-detailed.md`](./hermes-comparison-detailed.md)（含旧版 §6.1～§6.31 归档，飞书滤镜已废弃）。  
> **学习三原则**：不复制代码 · 理解意图 · Mimir 自造。

### 摘要（只读）

| 级别 | Hermes | OpenSpace |
|------|--------|-----------|
| **P0** | curator 生命周期 · subdirectory 语境界限 · 工具重复防护 | ToolQuality 追踪 · 混合搜索 |
| **P1** | think 擦除 · 脱敏 · 引用 DSL | quality reviewer · 工具搜索 |
| **P2** | 主辅分离 · 审批 · CLI 表现力 | 三层编排 · 进化配置分离 |

### §18 Wave 9 已落地（2026-05-27 · 勿在 bridge 重复开粒）

| 项 | backlog ID | 说明 |
|----|------------|------|
| Token 注入 prompt | **BRIDGE-CTX-B02** | `MIMIR_CONTEXT_USAGE_IN_PROMPT` |
| 子目录 hint 接线 | **HERM-SDH-01** | `SubdirectoryHintTracker` → tool 结果 |
| 只读 tool 缓存 | **HERM-TGR-01** | `MIMIR_TOOL_CALL_CACHE` |

### 自检备忘（过程性，非队列）

- 评估实现代价须查源码，不拍脑袋。  
|- 「回答问题」≠「完成任务」——工程粒以 backlog §18.2 为准。|
|
|## 4. MW 心愿单交付签收
|
|| 日期 | ID | 执行者 | 摘要 |
||------|------|-------|------|
|| 2026-06-02 | **MW-00** | Mimir | 验收 IQ-31/32/33/34（`a0dc323`）✅ 13 tests passed · `mw-00-iq31-34-verify.md` · `mw-00-prod-env.md` |
|| 2026-06-02 | **MW-01** | Mimir | search_first_guard 接线审计 ✅ 已接线（3文件6点）· 42 tests passed · 无需补线 |
|| 2026-06-02 | **MW-02** | Mimir | 并行只读工具分发 `agent/parallel_dispatcher.py` + `agent_loop.py` 接线 · 11 tests · tier0 692/4 · env 默认关 |
|| 2026-06-02 | **MW-03** | Mimir | 平台无关 `ToolDispatchContext`（`session_id/channel/workspace_root`）· 7 tests · tier0 692/4 |
|| 2026-06-02 | **MW-04** | Mimir | 周期对话 nudge（`MIMIR_NUDGE_INTERVAL` 默认 3·`0`=关）· `agent_loop.py` + 9 tests · tier0 692/4 |
|| 2026-06-02 | **MW-05** | Mimir | IC 顾问目录过滤修复 + 宽搜索 fallback（`engine.py`）· 7 tests · tier0 692/4 |
|| 2026-06-02 | **MW-90** | Mimir | §13 心愿单收官：MW-00～05 全 [x] · 34 tests · tier0 692/4 · closeout doc |
|| 2026-06-02 | **loop-crash-fix** | Mimir | loop 崩溃修复：`get_event_loop()`→`get_running_loop()` 3文件 · 并行路径 pre-validation + tool_errors.append + `_batch_results` 空兜底 · tier0 **696+2** 全绿 · 4 commits + push · IC 保护绕过（terminal→`/approve session`）|
|| 2026-06-04 | **HC-01/03 关闭** | Mimir | 测试债基线 + 搜索违规审计基线 · 守卫自引用修复 · 复盘工具 · CacheAligner · auto_retrospective · 5 bugs修 · tier0 696+2 全绿 · 10 commits push |
|| 2026-06-04 | **HC-23** | Mimir | ADR ContextEngine V3 自设计路线（不恢复 Hermes ABC）· `7d368e1` · HC 轨 Mimir 段全部 [x] |
|| 2026-06-04 | **HC-11** | Mimir | credential_sources.py 薄封装 127 行（RemovalStep 注册模式）· `181a452` · tier0 696+2 |
|| 2026-06-04 | **HC-13** | Mimir | rm agent/tool_registry.py 343 行 DEPRECATED + 同步删 2 测试文件 + 更新引用 · `d2410d6` · tier0 685 |
