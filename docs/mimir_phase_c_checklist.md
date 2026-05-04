# 阶段 3 / 里程碑 C — 独立学习期勾选清单

**用途**：在 **自主对照 Hermes / Parity 真源** 下勾选 **成长路线图 · 阶段 3 · 里程碑 C** 的五条标准（[`成长路线图.md`](../成长路线图.md) §阶段3）。与 **`./run_ralph_tier0.sh`** **互补**：门禁证明 **契约回归**；本清单证明 **能自选学习主题、产出架构/差距报告、可选迁移、有可复查归档**。

**不替代**：[`docs/mimir_phase_b_checklist.md`](mimir_phase_b_checklist.md)（里程碑 **B**）；[`docs/mimir_prod_smoke.md`](mimir_prod_smoke.md)（里程碑 **A**）。

**前置**：里程碑 **B** 已在 [`docs/MAINLINE_STATUS.md`](MAINLINE_STATUS.md) 标 **绿**（或等价工程证据已齐）。

| 字段 | 填写 |
|------|------|
| 日期 | **2026-05-04**（阶段 3：C 黄 → C 绿同批） |
| 执行人 | 协作者 / 代理（真源维护） |
| 仓库根 | 默认 `~/.openclaw/projects/MimirAether`（见 [`docs/path-contract.md`](path-contract.md)） |
| **当前学习目标（已闭合 3 主题）** | 见 **`docs/phase_c_studies/README.md`**：`20260504_agent_loop_tool_chain.md`、`20260504_gateway_session_transcript.md`、`20260504_parity_matrix_workflow.md`。 |
| 备注 | 勿在仓库提交 token；可选 Hermes 上游路径仅写本机说明（**不**提交密钥）。上游锚点见行为矩阵 §0 **HERMES_REF**。 |

---

## 什么时候需要跑本清单

| 情况 | 建议 |
|------|------|
| **建议跑** | 准备宣称 **里程碑 C** 有进展或拟将 MAINLINE 中 **C** 标 **黄/绿**；完成一轮「自选主题 → 报告 → 可选迁移」后更新 §执行记录。 |
| **可以晚点跑** | 仅伙伴期任务（继续用 B 清单）；未进入独立学习验收。 |
| **迭代方式** | 每完成一个 **独立学习主题** 补 §执行记录一行；阻塞项写明 **缺什么** 与 **下次补跑条件**。 |

**和门禁的关系**：`run_ralph_tier0.sh` **绿 ≠ 本清单全绿**。

---

## 与 M6（进化可审计）的关系

若任务改动触及 **agent / gateway / tools / 契约测试**（`agent/test_*.py` 等），合并前请按 [`docs/M6_EVOLUTION.md`](M6_EVOLUTION.md) 追加 **`docs/evolution_log.md`** 一行，优先：

```bash
./scripts/record_m6_evolution.sh "摘要；metrics 或 metrics: n/a"
```

纯文档/豁免情形见 M6 文档 §豁免。标 **C 绿** 的裁定批次建议 **`record_m6_evolution.sh`** 记一行（与 B 绿批次一致）。

---

## 建议的 C「绿」门槛（MAINLINE）

在 **`docs/MAINLINE_STATUS.md`** 将里程碑 **C** 标 **绿** 前，建议同时满足：

1. **≥ 3** 次 **不同主题** 的独立学习闭环（每次：报告路径 + 对照矩阵/契约引用 + §执行记录一行）。
2. 本节 **C1–C5** 均有 **可审计** 证据（见 §汇总与 §C 绿裁定记录），或已书面降级并更新成长路线图/MAINLINE 说明。
3. **C4（迁移）**：至少 **1** 次将学习成果写回仓库的可见动作（小 PR、索引文档、`behavior_matrix` 行更新等均可；纯外链不算）。

（门槛为仓库内**工程化约定**；路线图「自动归档记忆殿堂」若未实现，启动期允许 **仓库内复盘文档** 等价，见 §C5。）

---

## C 绿裁定记录（工程侧，2026-05-04）

本仓库将 **里程碑 C** 在 **MAINLINE** 标 **绿** 时，依据下列 **可审计** 材料（满足 §建议的 C「绿」门槛：**≥3** 次不同主题闭环 + C4 至少一次写回）。

| # | 主题（摘要） | C1 自选目标 | C2 读码/架构报告 | C3 改进方案 | C4 迁移到 Mimir | C5 归档 |
|---|-------------|-------------|------------------|-------------|-----------------|--------|
| 1 | **Agent 主循环 + 工具链** | H04–H06、H19；`core_loop` / Tier1 E2E | [`phase_c_studies/20260504_agent_loop_tool_chain.md`](phase_c_studies/20260504_agent_loop_tool_chain.md) | 文档交叉链；真模型子集 GAP | **README 索引** + 矩阵 **§4 目标 D**（同批） | 报告 §复盘 |
| 2 | **Gateway SessionStore 双写** | `SessionStore`、M5 对齐语义 | [`phase_c_studies/20260504_gateway_session_transcript.md`](phase_c_studies/20260504_gateway_session_transcript.md) | 可观测性；API 文档指回 `session.py` | **README 索引** | 报告 §复盘 |
| 3 | **矩阵 + testmap 工作流** | HERMES_REF 流程、H15 脚本 | [`phase_c_studies/20260504_parity_matrix_workflow.md`](phase_c_studies/20260504_parity_matrix_workflow.md) | H20 CI；索引互链 | **behavior_matrix §4 目标 D** + **README** | 报告 §复盘 |

**M6**：`docs/evolution_log.md` **`20260504T150637Z_5a0211b`**（`./scripts/record_m6_evolution.sh`，tier0 **0**）。

**范围说明**：路线图 C 条文中 **「自动归档记忆殿堂」** 若管道未接好，**工程表 C 绿** 声明：以 **本仓库 `docs/phase_c_studies/` + §执行记录 + M6 日志** 为可审计归档链；全自动化记忆写入另立项。

---

## 如何委托 MimirAether 代理执行

将下面整段复制给 **MimirAether 代理**（已打开本仓库、可执行终端）。

```
请阅读 docs/mimir_phase_c_checklist.md。在 git 根 ~/.openclaw/projects/MimirAether 协助推进「里程碑 C」：

- C1：当前学习目标是什么（Hermes 域 / Mimir 模块边界）？对照 behavior_matrix 哪几行？
- C2：报告路径（docs/phase_c_studies/…）是否包含：范围与非目标、代码路径、矩阵/契约引用、架构要点、差距与改进（≥2 条）？
- C3：改进建议是否可执行、是否区分短期/长期？
- C4：是否有写回仓库的迁移（PR、矩阵更新、索引）？若无，标明计划轮次。
- C5：复盘/归档引用（报告 §复盘 或 memory-palace 路径说明，勿打印 secret）。

输出：按 C1–C5 分节；[x]/[ ]；附 `./run_ralph_tier0.sh` 若本轮有代码改动。
```

---

## C1 — 自选学习目标（Hermes X 模块）

**路线图原文**：能自己选定学习目标（Hermes X 模块）。

**可观察信号**

- 清单 **元数据表** 或 §执行记录 中有 **明确模块名 / 边界 / 非目标**。
- 对照 **HERMES_REF** 或本仓库 **behavior_matrix** 行号/ID。

| 勾选 | 项 |
|------|-----|
| [x] | 目标模块/边界：见 §C 绿裁定记录 **#1–#3**（Agent 循环 / Gateway 会话 / 矩阵工作流） |
| [x] | 对照矩阵 ID 或契约段落：**H04–H06、H19**；**SessionStore**；**§0 HERMES_REF** |

**证据**：[`phase_c_studies/README.md`](phase_c_studies/README.md)  

**阻塞**：无  

---

## C2 — 读取代码、分析架构、输出报告

**路线图原文**：能读取代码、分析架构、输出报告。

**可观察信号**

- `docs/phase_c_studies/<YYYYMMDD>_<slug>.md`（或团队约定路径）含 **架构与数据流**、**关键文件路径**。

| 勾选 | 项 |
|------|-----|
| [x] | 报告路径：`docs/phase_c_studies/20260504_*.md`（三份） |
| [x] | 核心入口/调用链已标明：`core_loop.run_conversation`；`SessionStore.append_to_transcript`；矩阵 §3–§4 |

**证据**：同上  

**阻塞**：无  

---

## C3 — 发现改进点并提出方案

**路线图原文**：能发现 Hermes 的改进点并提出方案。

**可观察信号**

- 报告中 **差距与改进建议 ≥ 2 条**（可含「Mimir 侧 / 对齐 Hermes / 永久 DIFF」）。

| 勾选 | 项 |
|------|-----|
| [x] | 改进摘要：各报告 **§差距与改进建议**（每份 ≥2 条） |

**证据**：[`20260504_agent_loop_tool_chain.md`](phase_c_studies/20260504_agent_loop_tool_chain.md) §4 等  

**阻塞**：无  

---

## C4 — 把学到的模式迁移到 MimirAether

**路线图原文**：能把学到的模式迁移到 MimirAether。

**可观察信号**

- 合并或待合并的 **diff**、**behavior_matrix** 行更新、**索引文档** 等（见 §建议的 C「绿」门槛）。

| 勾选 | 项 |
|------|-----|
| [x] | 迁移说明：新增 **`docs/phase_c_studies/README.md`**；**[`hermes_mimir_behavior_matrix.md`](hermes_mimir_behavior_matrix.md) §4 目标 D** |

**证据**：git diff 同批；**MAINLINE** §5  

**阻塞**：无  

---

## C5 — 学习成果归档

**路线图原文**：学习成果能自动归档到记忆殿堂。

**本仓库启动约定**：优先 **仓库内复盘**（报告末尾 **§复盘**）；`memory-palace/...` 为可选；**自动**管道未实现不阻塞 **C 黄**，但 **C 绿** 前须有可复查链（见 §范围说明）。

| 勾选 | 项 |
|------|-----|
| [x] | 归档引用（路径）：三份报告 **§复盘** + 本清单 §执行记录 |
| [x] | 含：学到什么、下一步、风险（每报告 §6 或 §复盘） |

**证据**：同上  

**阻塞**：无  

---

## 汇总

| 里程碑 C 条款 | 对应章节 | 完成（本轮） |
|---------------|----------|--------------|
| 自选学习目标 | §C1 | [x] 见 §C 绿裁定记录 |
| 读码与报告 | §C2 | [x] 三份 `phase_c_studies` 报告 |
| 改进方案 | §C3 | [x] 各报告 §4 |
| 迁移到 Mimir | §C4 | [x] README + 矩阵 §4 目标 D |
| 归档 | §C5 | [x] 报告 §复盘 + 本清单 |

---

## 执行记录（倒序）

| 日期 | 主题摘要 | C1–C5 要点 | 备注 |
|------|----------|------------|------|
| 2026-05-04 | **里程碑 C 绿**：三主题报告 + 矩阵 §4 + README | 闭环齐；MAINLINE **C**→**绿** | 见 §C 绿裁定记录；**M6** `record_m6` |
| 2026-05-04 | Parity 矩阵维护工作流 | 报告 `20260504_parity_matrix_workflow` | 主题 3/3 |
| 2026-05-04 | Gateway SessionStore transcript | 报告 `20260504_gateway_session_transcript` | 主题 2/3 |
| 2026-05-04 | Agent 主循环 + 工具链 | 报告 `20260504_agent_loop_tool_chain` | 主题 1/3 |
| 2026-05-04 | 阶段 3 工程入口 | 新增本清单；MAINLINE **C** 标 **黄** | 866a020 批次 |

---

## 相关文档

- [`成长路线图.md`](../成长路线图.md) — 阶段 3 原文  
- [`docs/hermes_mimir_behavior_matrix.md`](hermes_mimir_behavior_matrix.md) — Hermes ↔ Mimir 行为对照  
- [`docs/ralph_parity_testmap.md`](ralph_parity_testmap.md) — pytest 映射  
- [`docs/MAINLINE_STATUS.md`](MAINLINE_STATUS.md) — 主线表  
- [`docs/mimir_phase_b_checklist.md`](mimir_phase_b_checklist.md) — 里程碑 B  
- [`docs/M6_EVOLUTION.md`](M6_EVOLUTION.md) — 进化审计  
