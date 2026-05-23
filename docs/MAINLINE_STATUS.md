# 主线进度快照

> **单一更新入口**：用户问「进度 / 主线 / 完成度」时，协作者应先 **Read 本文件**，再根据当前仓库事实与可选命令输出 **更新下列表格与日期**，必要时补一行「本轮变更摘要」。  
> 权威依据：`docs/DEVELOPMENT_NORTH_STAR.md`、`docs/ralph_roadmap_milestones.md`、`成长路线图.md`、`docs/ralph_parity_testmap.md`、`docs/ralph_tier0_case_matrix.md`。

| 字段 | 值 |
|------|-----|
| **最近更新** | 2026-05-24 |
| **更新人** | Cursor（Prompt 6 — EV-P05 Compressor 审计） |
| **仓库根（真源）** | `~/src/MimirAether` |
| **可选校验** | `./run_ralph_tier0.sh`（门禁 **237+2**）；[`scripts/smoke_mimir_home.sh`](../scripts/smoke_mimir_home.sh)（独立 home smoke）；宽 pytest 见 [`.github/workflows/pytest-wide.yml`](../.github/workflows/pytest-wide.yml） |
| **本轮摘要** | **EV-P05** [x]（Compressor 重叠 → `docs/phase0/compressor-overlap-audit.md`）。执行源：**`MIMIR_PHASE0_QUEUE.md`**，下一条 **EV-A01**。Phase 1.5 已结案；tier0 **237+2**。 |

---

## 1. 工程里程碑（Ralph / Parity）

| ID | 名称 | 状态 | 说明 |
|----|------|------|------|
| M0 | 基线可回归 | **绿** | `run_ralph_tier0.sh` 日常可通过。Gate2 **237**、Gate3 **2**（含 E-010/E-011/E-012/intent-action guard 回归测）。发版前建议复跑：`for n in 1 2 3; do ./run_ralph_tier0.sh || exit 1; done` |
| M1 | 契约可执行 | **绿** | `docs/ralph_parity_testmap.md` 已映射 |
| M2 | Tier-0 矩阵闭合 | **绿** | `ralph_tier0_case_matrix.md`：无阻塞 P0 |
| M3 | 垂直切片 | **绿** | CLI + API `POST /v1/chat/completions` |
| M4 | Tier-2 HTTP（可选） | **绿** | `fixtures/m4_http/` + `test_m4_auxiliary_http_slice.py` |
| M5 | 内核可替换 | **绿** | 多端口 seams + DI 注入 + `AgentKernelOverrides` |
| M6 | 进化可审计 | **绿** | `evolution_log.md` + `record_m6_evolution.sh` + pre-push 提醒 |

状态图例：**绿** = 满足文档完成判据或等价；**黄** = 部分/待复核；**未** = 未达成。

---

## 2. 产品阶段（成长路线图）

| 阶段 | 里程碑 | 状态 | 说明 |
|------|--------|------|------|
| 1 Hermes 影子期 | **A** | **绿** | CLI + gateway + 工具链 + 飞书真实消息 |
| 2 专项伙伴期 | **B** | **绿** | `mimir_phase_b_checklist.md` §B 绿裁定记录 |
| 3 独立学习期 | **C** | **绿** | `mimir_phase_c_checklist.md` ≥3 主题报告 |
| 4 自主进化期 | ∞ | **绿** | `mimir_phase_infinity_checklist.md` §∞ 绿裁定 #1 |

---

## 3. 两条主线健康度

| 主线 | 健康度 | 备注 |
|------|--------|------|
| **Parity** | 强 | 契约 + Gate1–3 + 测试映射可追踪 |
| **Evolution** | 强 | M6 绿 + Hermes/OpenSpace 双战役学习闭合 + 独有能力（TaskLoop/Capsules/Causal AR/Belief） |

---

## 4. 近期焦点（可改）

0. **IR-20260520 结案（2026-05-20）**：工程已合入本地 main；Mimir **T-02～T-11**；Cursor **E-004**；见 `MIMIR_HANDOFF_20260520.md`。
1. **稳定性冲刺（2026-05-19）**：Mimir 按 `MIMIR_EXEC_BACKLOG` M1–M8 冒烟；工程项见 `GATEWAY_STABILITY_BACKLOG.md`。
2. **真源树**：提交与推送在 `~/src/MimirAether`；勿与 `MIMIR_AETHER_HOME` 混淆。
3. **维持 M6 绿**：受保护路径合入不长期漏记。
4. **维持 B/C/∞ 绿**：各阶段 checklist §执行记录续更。

---

## 5. 更新日志（倒序）

| 日期 | 摘要 |
|------|------|
| 2026-05-24 | **EV-P05** [x]：Compressor 重叠审计（~30%，前缀已分叉）→ `docs/phase0/compressor-overlap-audit.md`。下一条 **EV-A01**。 |
| 2026-05-24 | **EV-P04** [x]：GOD 清单刷新（24×≥1500，`cli.py` 退出）→ `docs/phase0/god-file-inventory.md`。下一条 **EV-P05**。 |
| 2026-05-24 | **EV-P03** [x]：废弃代码审计 → `docs/phase0/dead-code-audit.md`；`GOD_FILE_INVENTORY.md` 链 phase0 真源。下一条 **EV-P04**。 |
| 2026-05-24 | **EV-P02** [x]：测试命名审计 → `docs/phase0/test-naming-convention.md`；`TEST_NAMING_CONVENTION.md` 补双轨/E-012/intent-action 示例。下一条 **EV-P03**。 |
| 2026-05-24 | **Phase 0 启动**：新建 `MIMIR_PHASE0_QUEUE.md`（14 粒）；**EV-P01** fixtures 审计完成；BACKLOG §9 指向 Phase 0 队列。 |
| 2026-05-24 | **Prompt 1**：ISSUES Active≤3、Backlog §2d 关账、§9 续跑、ADR-002 stub。 |
| 2026-05-23 | **E-011 Phase 1.5**：Duration P50/P95/P99 → `/health`；MemoryFencer 用户入站保留 Markdown 表格；import/hygiene 回归测；tier0 **225+2** 绿。ISSUES #11 resolved。 |
| 2026-05-20 | **IR-20260520 工程结案**：recovery/exec/gateway 修复；tier0 181+2；TRUNCATE 基线 19；`MIMIR_HANDOFF_20260520.md` + backlog/D17 §5 更新；OpenClaw skill `mimir-handoff-weixin`。 |
| 2026-05-19 | **收尾**：G5 API Server loopback 确认安全；Git 工作区清理；MAINLINE 刷新；Gateway #2 Token 日志无异常。#1 孤儿 tool 已合 #4 / #9 空表头已合 #5。session_count: 341。 |
| 2026-05-19 | **双战役闭合**：Hermes 8模块(agent_loop/ContextEngine/Platform/Model/Tool/Cron/Session/Cache) + OpenSpace 8模块(recording/quality/analysis/grounding/host/skill/analyzer/base) 学习完成。ContextEngine 去 Hermes 化（独立 MimirContextCompressor）；fuzzy_match 复制删除；孤儿 tool 双重防护(sanitize+clean)。上下文 25→200 条(128K→1M)。Gateway 重启 PID 69532。 |
| 2026-05-19 | **稳定性**：PR4/5 合并；P2-1b message-resource + P2-1c vision 回退；计划 `docs/plans/2026-05-19_stability_sprint.md`；Mimir 执行清单入 BACKLOG。 |
| 2026-05-18 | **状态刷新**：Session 199；TaskLoop v2.x 多轮迭代；R1–R12 参数调优；tier0 162+2 全绿。 |
| 2026-05-16 | **路径叙事（阶段 A）**：文档与根脚本对齐「clone 根 vs `MIMIR_AETHER_HOME`」；tier0 绿。 |
| 2026-05-13 | **Phase VI 物理删除**：`hermes_cli/` 60+文件(76K行)删除；`mimcore/` 删除；12个Hermes遗存技能清理。 |
