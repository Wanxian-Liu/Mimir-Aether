# 刘哥 ↔ Mimir ↔ Cursor（仓库内对话，与 OpenClaw 无关）

> **真源路径**：`~/src/MimirAether/docs/MIMIR_LIU_CURSOR_BRIDGE.md`  
> **队列真源**：`docs/MIMIR_EXEC_BACKLOG.md`（§2 / §2b / §2c）· 路线图：`docs/MIMIR_UNIFIED_PLAN.md`

| 谁 | 怎么做 |
|----|--------|
| **刘哥** | 飞书找 **Mimir**；战略方向 / 例外授权写 **§1、§2** |
| **Mimir** | 每轮 Read bridge + backlog + unified plan；冒烟、health_check、§4 签收 |
| **Cursor** | 工程 PR、git、rebase、tier0、CI merge（见 §2 常备授权） |

**不走**：OpenClaw cron、微信同步 backlog。

---

## 1. 刘哥 → Mimir / Cursor（你编辑）

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

### （新留言写在此下）

_示例：@Mimir 按 IQ-EVO-01。@Cursor SEM-03。_

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

### 2026-05-23

- main：`fb53ac2`+（E-004 + E-005 + 常备授权 + bridge WIN-5 签收）
- JEPA：PR **#8** merge → main（merge `origin/main` 进 feat 后 push + gh merge）
- **WIN-5** ✅ · **PR #8 merge** ✅（本窗）
- 下一工程刀：**Phase 1 工程线 E-001～E-009 已收口**（见 backlog §2）

---

## 4. Mimir 签收（每轮追加一行）

| 时间 | 已读 bridge+backlog | 本轮 ID | 结果一句话 |
|------|---------------------|---------|------------|
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

---

## 5. Mimir 进度笔记

- **main**：`b55fa98` · tier0 **368+2** · **`P0-LONG-CLEARANCE` [x]** · **`P2-LONG-SEM` [x]**
- **身份（2026-05-19）**：Mimir **是智能体**（loop+tools+memory），**不是** DeepSeek 传话桶 — bridge §1
- **Wave 0 A / 1 B / 2 C / D / E**：**[x]**（刘哥 §8.3 签收 2026-05-25）
- **Horizon A**：**P2-LONG-SEM** **[x]** · **IQ-EVO Wave 1+2 工程 [x]** → staging `MIMIR_AUTO_ANALYSIS=1` + Mimir smoke；**Chroma 增量 / hybrid 默认** 待刘哥
- **R5**：刘哥复验 **pass**（30s 内 tool）
- **Gateway**：PID **135797** · /health ok · TRUNCATE since-start **0**
- **GH open**：**10** · #10 **monitoring**（STAB-04 已修）

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
| MW-D10 | [x] | GH open **10**；重复 issue 已关 |
