# Mimir 零技术债主计划（清空 → 独立 → 工业级自进化）

> **生成**：2026-05-24 · Cursor  
> **读者**：刘哥 / Mimir（运维）/ Cursor（工程）  
> **地位**：在 **全部 backlog / issues 收口完成前**，本文件取代 §11/§12/§8/§6 的并行取任务；每波只跑 **一条长任务 + 顺序子项**。  
> **北星**：[`DEVELOPMENT_NORTH_STAR.md`](./DEVELOPMENT_NORTH_STAR.md) · **Parity 可证 + Evolution 可测 + Gate3 安全**

---

## 0. 清空完成定义（Done）

满足 **全部** 下列条件时，宣告「技术债/bug/未完成项」清空，可进入 **整体规划 Phase 2+**：

| # | 判据 | 验证 |
|---|------|------|
| D1 | **GitHub open ≤ 6**，且均为 **icebox / Phase 2 规划** 标签，无重复母 issue | `gh issue list --state open` |
| D2 | **`MIMIR_ISSUES.md` Active ≤ 3**，且均为 **deferred + ADR/EV-* 链接**，无 P0 未指派 | 人工读表 |
| D3 | **`GATEWAY_STABILITY_BACKLOG` 十条** 每条 = 已验证 / 已移交并结案 / 已记 ISSUES | 状态列无「待复现」悬空 |
| D4 | **`MIMIR_EXEC_BACKLOG` §13** 当前波 **无 `[ ]` 子项** | 单执行源 |
| D5 | **tier0** `./run_ralph_tier0.sh` **245+2 PASS**（或当时基线） | 命令 |
| D6 | **飞书 T-03/T-04** 刘哥复验 **[x]** 或明确 **wontfix + ADR** | `mimir_prod_smoke.md` |
| D7 | **Hermes 路径**：运行树 **无新增** `hermes_cli` import；`MIMIR_AETHER_HOME` 为唯一推荐 env；`HERMES_HOME` 仅文档 **legacy alias** | grep + path-contract |
| D8 | **工业进化 MVP**：D5-1（禁 `simulated` 存根）+ D6-1 ADR + **一条** 可复现 eval 脚本入 tier0 或 weekly job | §4 Wave 3 |

---

## 1. 现状真值盘点（2026-05-24）

### 1.1 已绿（勿重开）

| 域 | 状态 | 证据 |
|----|------|------|
| Ralph M0–M6 | 绿 | `MAINLINE_STATUS.md` |
| Phase 0 审计 | 14/14 | `MIMIR_PHASE0_QUEUE.md` |
| Phase 1.5 E-001～E-012 | 绿 | tier0 **245+2** |
| P1-LONG-MEM | 结案 | main `7f4b53d`；GH #17/#18 closed |
| P1-LONG-GOD | 结案 | #16→main；`router_mixin` ~38 行 |
| A2 `.openclaw` 母审计 | 结案 | `MIMIR_OPENCLAW_BOUNDARY.md` §7 |
| A1 Gateway 硬重启 | 进程 ok | PID **691521**；GH #19 closed |
| `.openclaw` advisory | **6/60** | 非阻断 |

### 1.2 仍 open（Horizon · 不阻塞清空）

> **2026-05-25**：**P0-LONG-CLEARANCE** 已宣告完成 — 见 [`phase0/p0-long-clearance-done.md`](./phase0/p0-long-clearance-done.md)。下列 **3** 个 GH open 均为 icebox / phase-2。

### 1.2a 历史盘点（Wave 0 前 · 已收口）

#### GitHub（14 open — **含重复/漂移**）

| GH | 标题 | 真状态 | 处置 |
|----|------|--------|------|
| **#2** | .openclaw 母 issue | **已结案**（§7） | **Wave 0 关** + comment 链 #10/#12/#13 |
| **#12** | tools .openclaw | PR #24 已合 | **Wave 0 关** |
| **#13** | mimicore .openclaw | PR #23 已合 | **Wave 0 关** |
| **#31** | P1-LONG-GOD | **已结案** | **Wave 0 关** |
| **#27–30** | Gateway #1/#4/#8/#10 | 工程债 | → **Wave 2** 子项 |
| **#25–26** | WS 心跳 / 回滚护栏 | icebox P0 | → **Wave 2** 子项 |
| **#20–22** | P3-0 / D5 / D6 | icebox | → **Wave 2–3** |
| **#32** | P2-LONG-SEM | 规划项 | **重标签** `phase-2`；**非 Active** |

#### 文档 issues

| 源 | 项 | 处置 |
|----|-----|------|
| `ISSUES.md` #1 | 识图 blocked | **EV-VISION-DEFER**；Wave 1 记 wontfix 直至 OPENROUTER |
| `ISSUES.md` #2 | 空表头 | resolved；Wave 1 **T-03 复验** |
| `ISSUES.md` #3 | 双按钮 | fixed-pending-smoke；Wave 1 **T-04 复验** |
| `MIMIR_ISSUES` #3 | 记忆三入口 | **ADR-002 deferred** — 不进 Wave 2 |
| `MIMIR_ISSUES` #10 | vision/TRUNCATE | deferred；TRUNCATE≤19 则保持 |

#### Backlog 散落

| 桶 | 条数 | 并入 |
|----|------|------|
| §12.1 MW-D01–D11 | 11 | **Wave 0**（Mimir） |
| §8 工程 icebox | 4 | **Wave 2** |
| §6 D5-1/3/ADR D6-1/2/3 | 6 | **Wave 3** |
| §11 P2-LONG-SEM | 1 | **Horizon**（清空后） |

### 1.3 根因：为何「越来越多」

1. **多层真源**（BACKLOG / Gateway / Unified / GH / ISSUES）未 **单队列** 合并。  
2. **Phase 0 审计** 每粒衍生 Phase 1/2 项 — 已用 **长任务 + 子项** 止血；本计划 **§13 单执行源** 继续。  
3. **GH 与 docs 漂移**（#2/#12/#13 重开）— Wave 0 对账 + 只从 docs 开 issue。

---

## 2. 四波执行（唯一顺序）

```
Wave 0  hygiene     1–2 天   Mimir 为主     → D1/D2 部分
Wave 1  smoke       1 次     刘哥 + Mimir     → D6
Wave 2  stability   2–3 周   Cursor           → D3 + Gateway 工程
Wave 3  indep+iev   3–5 周   Cursor           → D7 + D8
Horizon            清空后    刘哥拍板         → P2-LONG-SEM / 智商 Phase 3
```

---

## 3. Wave 0 — 卫生与对账（**现在**）

**长任务 ID**：`W0-LONG-HYGIENE`  
**Owner**：Mimir（D01–D10）+ Cursor（GH 批量关 + §13 文档）

| ID | 任务 | Owner | 成功标准 |
|----|------|-------|----------|
| W0-01 | 跑 **MW-D01–D10**（§12.1，跳过 D11 汇总） | Mimir | 每行 `[x]` + bridge §4 |
| W0-02 | **GH 关重复**：#2 #12 #13 #31 + comment 真源链 | Cursor | `gh issue list` 无上述 open |
| W0-03 | **GH 重标签**：#20–22 #25–26 → `icebox`；#27–30 → `wave-2-stability`；#32 → `phase-2` | Cursor | 标签一致 |
| W0-04 | 更新 **§9.1 / §10 / MAINLINE** → 指向 **§13** | Cursor | 无「§11 Active」矛盾 |
| W0-05 | **`MIMIR_ISSUES.md`**：#2 保持 resolved；Active 仍 ≤3 | Mimir | — |
| W0-06 | **MW-D11** 汇总飞书（刘哥在则发；不在则写 bridge §4） | Mimir | 勾选表 + TRUNCATE + PID |

**禁止**：Wave 0 不开 P2-LONG-SEM、不改 agent/gateway/tools（除 GH/ docs）。

---

## 4. Wave 1 — 飞书端到端（人工门）

**长任务 ID**：`W1-LONG-SMOKE`  
**Owner**：刘哥（T-03/T-04）+ Mimir（记录）

| ID | 任务 | 成功标准 |
|----|------|----------|
| W1-01 | **T-03** 空表头 HTML 表 → 无 `230099` | `mimir_prod_smoke.md` §2026-05-24 |
| W1-02 | **T-04** 双按钮 HTML → 两按钮可见 | 同上 |
| W1-03 | 更新 **GATEWAY #9** → **已验证** | backlog 状态列 |
| W1-04 | 关 **MW-H01/H02** 或记 wontfix | §12.1 人工门表 |

**识图 #1**：不阻塞清空；保持 **EV-VISION-DEFER**。

---

## 5. Wave 2 — 稳定性工程债（Cursor）

**长任务 ID**：`P2-LONG-STAB`  
**前置**：Wave 0 完成；tier0 绿  
**真源**：`GATEWAY_STABILITY_BACKLOG.md` + gstack P0

| ID | 任务 | GH | 成功标准 |
|----|------|-----|----------|
| STAB-01 | **Watchdog 超时** 与长推理/WS 同源分析 + 修复或降级策略 | #27 #25 | 复现脚本或 7 日无超时；tier0 |
| STAB-02 | **Event loop closed** async 生命周期 | #28 | 单测或 gateway 回归；tier0 |
| STAB-03 | **ToolGuard 相对路径** | #29 | path 单测；tier0 |
| STAB-04 | **Agent 偶发崩溃**（`run.py` 栈） | #30 | 根因 PR + TRUNCATE 仍 ≤19；M6 |
| STAB-05 | **自修回滚护栏**（D5 安全） | #26 | 回滚路径 documented + 测试；M6 |
| STAB-06 | **WebSocket 推理阻塞心跳** | #25 | 与 STAB-01 同 PR 或子 PR | tier0 |
| STAB-07 | **长任务结案** | — | 关 GH #25–30；Gateway 十条 **无「移交工程」** |

**Mimir 角色**：每 STAB-* 前导出日志；**不改码**。

---

## 6. Wave 3 — 完全独立 + 工业级自进化 MVP（Cursor）

### 6.1 完全独立（≠ 去掉 Parity 契约）

**目标**：运行时与 **路径/包名** 不再依赖 Hermes/OpenClaw 布局；**行为 Parity** 仍用 `ralph_parity_contract_v1` 测，**不**删 Hermes 作 **参考行为** 的表述。

**长任务 ID**：`P2-LONG-INDEP`

| ID | 任务 | 成功标准 |
|----|------|----------|
| IND-01 | **ADR-003**（新）：`HERMES_HOME` / `OPENCLAW_*` env **legacy alias 表** +  sunset 日期 | `docs/adr/003-runtime-env-aliases.md` |
| IND-02 | 新代码 **仅** `MIMIR_AETHER_HOME` / `get_mimir_home()`；grep 门禁 **新增** 禁止裸 `HERMES_HOME` 作默认（tools/agent/gateway） | tier0 + advisory |
| IND-03 | `OPENCLAW_SESSION_DB` → **`MIMIR_SESSION_DB`**（保留旧名读） | 单测 + path-contract 更新 |
| IND-04 | `mimicore` 子模块边界：`.openclaw` 字面量 **子模块内** 或 **fork 策略** ADR | GH #13 类问题不再复发 |
| IND-05 | **P3-0 单写者** 实现（ADR-001 落地） | GH #20 close；persistent 竞争测试 |
| IND-06 | **结案**：`MIMIR_OPENCLAW_BOUNDARY.md` §8 独立宣言 + MAINLINE 刷新 | 刘哥 sign-off |

### 6.2 工业级自进化 MVP

**定义**（对齐 `MIMIR_EV_L_INDUSTRIAL_LEARNING.md` + 北星 §2.2）：

1. **禁伪进化**：无 `simulated: true` 写入生产 evolution 路径（**D5-1**）。  
2. **可审计**：每次 agent/gateway/tools 变更 → `evolution_log.md` + tier0（已有 M6）。  
3. **可测收益**：至少 **一条** 自动化 eval（如 20-query memory benchmark 或 tool 成功率）→ CI weekly 或 tier0 optional。  
4. **可回滚**：Wave 2 STAB-05 护栏。  
5. **ADR 真源**：trajectory/recorder SoT（**D6-1**）。

**长任务 ID**：`P2-LONG-IEVO`

| ID | 任务 | 成功标准 |
|----|------|----------|
| IEVO-01 | **D5-1** 移除/拦截 `simulated` 生产路径 | grep + 单测；GH #21 部分 close |
| IEVO-02 | **D5-3** evolution 路径 pytest | tier0 或 wide pytest 绿 |
| IEVO-03 | **D6-1** Observability SoT ADR | GH #22 部分 close |
| IEVO-04 | **`scripts/run_evolution_eval.sh`**：跑 memory benchmark + 写 JSON + 对比基线 | 文档 + 一次绿 run |
| IEVO-05 | **D6-3** monitor/insights 回归测（可选 ObservabilityBus → defer） | 单测 ≥3 |
| IEVO-06 | **结案** + Phase ∞ checklist 续勾 | MAINLINE §2 产品阶段维持绿 |

---

## 7. Horizon（清空 **后** 才开）

| ID | 主题 | 前置 |
|----|------|------|
| **P2-LONG-SEM** | chromadb 语义检索 | P2-LONG-STAB 结案 + hybrid 生产 7 日 |
| **ADR-002** | 记忆三写入口统一 | 刘哥 ADR 评审 |
| **Phase 3 智商** | ExperienceBuffer / AutoTuner | Unified Plan §3 Phase 3 |
| **Phase 4 通知** | 主动推送 | Unified Plan §3 Phase 4 |

**Stash icebox**（IC advisor / Superpowers / subagent Phase C）：**不**纳入本清空；刘哥 2026-05-24 已搁置。

---

## 8. 角色分工（双轨）

| 角色 | Wave 0–1 | Wave 2–3 |
|------|----------|----------|
| **Mimir** | MW-D*、日志、bridge §4、ISSUES 登记 | 每 STAB/IEVO 前 visibility；**不改码** |
| **Cursor** | GH 对账、§13、MAINLINE | STAB + IND + IEVO 代码；tier0；M6 |
| **刘哥** | T-03/T-04；Wave 3 sign-off | 拍板 Horizon；OPENROUTER 识图 |

---

## 9. 新窗一句（清空期）

**Mimir**

```text
Read docs/MIMIR_ZERO_DEBT_MASTERPLAN.md §3 Wave 0 + MIMIR_EXEC_BACKLOG.md §13。
MIMIR_AETHER_HOME=~/.mimiraether。只做 W0-01 第一条 [ ] 或 MW-D* 对应粒。
更新 bridge §4 一行。禁止 push；禁止改 agent/gateway/tools。
回报：ID + 结果 + 下一粒。
```

**Cursor**

```text
Read docs/MIMIR_ZERO_DEBT_MASTERPLAN.md + MIMIR_EXEC_BACKLOG.md §13。
当前波：W0 或 P2-LONG-STAB 或 P2-LONG-INDEP/IEVO（看 §13 第一条 [ ]）。
每次一颗粒；触达 agent/gateway/tools 后 ./run_ralph_tier0.sh + evolution_log。
```

---

## 10. 清空后 → 整体规划入口

当 **§0 Done 八条全绿**（或 **§13.1 `CLEARANCE-DONE`** `[x]`）：

1. 召开 **30min 规划**：只读 `MIMIR_UNIFIED_PLAN.md` §3 Phase 2→4 + 本文件 §7 Horizon。  
2. **单选下一条长任务**：默认 **P2-LONG-SEM** 或 **Phase 3 智商**（刘哥二选一）。  
3. **冻结** 新 parallel backlog；衍生项只进 **当前长任务子项**（**§13.1 `P0-LONG-CLEARANCE`**）。

---

## 附录 A — Issue → 波次映射（速查）

| 键 | Wave |
|----|------|
| MW-D01–D11 | 0 |
| MW-H01–H03 / ISSUES #2 #3 | 1 |
| Gateway #1 #4 #8 #10 / GH 25–30 | 2 |
| GH 20–22 / D5 D6 / IND / IEVO | 3 |
| GH 32 / P2-LONG-SEM | Horizon |
| EV-VISION / ISSUES #1 | Defer |
| ADR-002 | Defer |
