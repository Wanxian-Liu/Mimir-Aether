# MimirAether 问题追踪

> 模板：`| # | 日期 | 来源 | 描述 | 严重度 | 状态 |`  
> **规则**：新增 issue 必须带 **Backlog ID**（如 E-012、CLOSE-3、EV-M02）；卡住时在此登记后停手等刘哥确认。  
> **真源队列**：`docs/MIMIR_EXEC_BACKLOG.md` · 主线快照：`docs/MAINLINE_STATUS.md`

---

## Active（≤3）

| # | 日期 | 来源 | 描述 | 严重度 | 状态 | Backlog |
|:--:|:----:|:----:|------|:------:|:----:|---------|
| 16 | 2026-06-01 | DIRECTION | **方向纠正：飞书只是沟通工具，进化目标是 MimirAether 自身能力** — 学 pi-agent 不是学它的 UI/平台适配，是学它的能力。禁止用\"飞书不需要\"作为不改架构的理由。 | 高 | [x] 刘哥 2026-05-19 确认 | [bridge §@Cursor方向纠正](./MIMIR_LIU_CURSOR_BRIDGE.md) |
| 17 | 2026-06-01 | IQ-RESEARCH | **IQ 提升综合计划** — Phase1 收官 4.9→5.2；**§11 执行粒闭合**（IQ-12 RECALL 仍按拍板暂缓）。下一工程链：**TASK_QUEUE §12** [`MIMIR_ENGINEERING_WORKFLOW.md`](./MIMIR_ENGINEERING_WORKFLOW.md)。 | 高 | [x] Phase1 闭合 | [`iq17-closeout.md`](./phase0/iq17-closeout.md) |

---

### #17 详细说明

#### 刘哥的意愿
> 1. Mimir 的 IQ 要往上提（当前 4.9/10，目标 5.5+）
> 2. 飞书只是沟通工具，进化目标是 Mimir 自身能力
> 3. 学 pi-agent 是学能力（并行、事件驱动、主动调度），不是学 UI/平台适配
> 4. 先调研，再评估风险，最后逐个实现

#### Mimir 的调研产出
对应调研文档：[`docs/proposals/iq-improvement-research.md`](./proposals/iq-improvement-research.md)

6 个方向按优先级排列：

| 方向 | 风险 | 代码改动 | IQ 贡献 | 拍板人 |
|:----:|:----:|:--------:|:-------:|:------:|
| **A: 先搜再答肌肉记忆** | 🟢 低 | 0 行（prompt 加规则） | +0.3 | 刘哥 |
| **B1-B2: 世界模型开门** | 🟢 低 | 0 行（env 开关） | +0.15 | 刘哥 |
| **C: AUTO_EVOLVE 默认开** | 🟡 中 | 1 行（默认值） | +0.2 | 刘哥 |
| **D: IntentPredictor** | 🔴 高 | ~210 行（新模块） | +0.5 | 刘哥批 scope |
| **E: 对话内 nudge** | 🟡 中 | ~50 行 | ? | 需设计 |
| **F: 并行工具执行** | 🟡 中 | ~100 行 | ? | 需设计 |

#### 执行分工（2026-06-01 Cursor 编排完成）
| 谁 | 做什么 |
|----|--------|
| **Mimir** | [`MIMIR_IQ17_EXECUTION_PLAN.md`](./MIMIR_IQ17_EXECUTION_PLAN.md) + **TASK_QUEUE §11** 第一条 `[ ]` → IQ-45 |
| **刘哥** | §3 拍板模板（`iq17-liu-decisions.md`）· shell 改 `.env` / 重启 gateway · 飞书冒烟 IQ-14 |
| **Cursor** | 合入 PREREQ（guard/suspended）· 复核 `docs/mimir-handoff/IQ-*` · D/F 大改 |

拍板真源：[`docs/phase0/iq17-liu-decisions.md`](./phase0/iq17-liu-decisions.md)

---

## 已关闭（归档）

| # | 日期 | 来源 | 描述 | 严重度 | 状态 | 关闭依据 |
|---|------|------|------|--------|------|----------|
| 1 | 2026-05-16 | CLARIFY_BASELINE §3.3 | `list_capsules` 返回 0 — 路径正确，`memory/capsules/` 空因未发布胶囊 | 高 | resolved | 真源路径已验 |
| 4 | 2026-05-16 | 会话实测 | `persistent.json` 截断 — 双写竞争；根因已标 architectural；缓解已到位 | 高 | root-caused | [adr/001-persistent-single-writer.md](./adr/001-persistent-single-writer.md) |
| 5 | 2026-05-16 | 会话实测 | `memory` 工具 `MemoryStore` 未实例化 — `get_memory_store()` 已合，Gateway 验证通过 | 高 | resolved | E-005 前后冒烟 |
| 6 | 2026-05-16 | BACKLOG #1 | 存量胶囊迁移 mimicore/public → `memory/capsules/*.html` | 中 | resolved | P1-6 / BACKLOG #8 |
| 7 | 2026-05-20 | T-09 (d5) | JEPA `run_cycle` 已接 pipeline close（**E-012**, `MIMIR_JEPA_CYCLE`）；skill FIX 仍走 **E-009** | 低 → 中 | resolved | **E-012** 2026-05-24 |
| 8 | 2026-05-20 | T-11 (d7) | `CLI_CONFIG` ImportError — **E-004** 默认值 + 导入路径修复 | 中 | resolved | **E-004** 2026-05-23 |
| 9 | 2026-05-20 | T-10 (d6) | 可观测 TOOL_CALL SQL + monitor + `/health`；NameError **E-010** | 中 | resolved | **E-006** / **E-010** / **E-011b** |
| 11 | 2026-05-21 | EV-L13 | RED Duration P50/P95/P99 缺失 | 低 | resolved | **E-011b** |
| 10 | 2026-05-20 | T-08 (d4) | TRUNCATE：STAB-04 已修；**since-start** 运维 KPI → **documented exception**（非 Active） | 中 | documented exception | **OBS-B1-03** · [`obs-b1-03-issue10-closeout.md`](./phase0/obs-b1-03-issue10-closeout.md) |
| 12 | 2026-05-26 | IQ-EVO-38 | **智商/进化方向** — Wave 6 全 **[x]** · rubric **4.8/10**（documented exception，距 5.5 差 0.7） | 低 | resolved | [`p2-long-iqevo-wave6-closeout.md`](./phase0/p2-long-iqevo-wave6-closeout.md) |
| 2 | 2026-05-16 | CLARIFY_BASELINE §5 | 并行树 `~/.openclaw/projects/MimirAether` — **工程真源** `~/src/MimirAether` | 中 | resolved (process) | CLEARANCE-DONE 2026-05-25 |
