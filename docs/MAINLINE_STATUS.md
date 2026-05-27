# 主线进度快照

> **单一更新入口**：用户问「进度 / 主线 / 完成度」时，协作者应先 **Read 本文件**，再根据当前仓库事实与可选命令输出 **更新下列表格与日期**，必要时补一行「本轮变更摘要」。  
> 权威依据：`docs/DEVELOPMENT_NORTH_STAR.md`、`docs/ralph_roadmap_milestones.md`、`成长路线图.md`、`docs/ralph_parity_testmap.md`、`docs/ralph_tier0_case_matrix.md`。

| 字段 | 值 |
|------|-----|
| **最近更新** | 2026-05-27 |
| **更新人** | Cursor（§19 主队列 + Horizon C 主迭代计划） |
| **仓库根（真源）** | `~/src/MimirAether` |
| **可选校验** | `./run_ralph_tier0.sh`（门禁 **466+2**）；`MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh`（周常） |
| **本轮摘要** | **Wave 10 [x]**（CUR/TGR/SDH）· §19.1 **3/15** · tier0 **513+2** · 综合 WM **~51%** · main **`9beb056`** · SDH dirty 待 commit · 下一粒 **OS-TQM-02**（Wave 11）。 |

---

## 1. 工程里程碑（Ralph / Parity）

| ID | 名称 | 状态 | 说明 |
|----|------|------|------|
| M0 | 基线可回归 | **绿** | `run_ralph_tier0.sh` 日常可通过。Gate2 **382**、Gate3 **2**。 |
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

0. **Horizon C 主迭代（2026-05-27）**：唯一取任务 **`MIMIR_EXEC_BACKLOG.md` §19.1**；波次计划 **`docs/superpowers/plans/2026-05-27-horizon-c-master-iteration.md`**（W0 部署 → Wave 10～15+）。
1. **IR-20260520 结案（2026-05-20）**：工程已合入本地 main；Mimir **T-02～T-11**；Cursor **E-004**；见 `MIMIR_HANDOFF_20260520.md`。
2. **稳定性冲刺（2026-05-19）**：Mimir 按 `MIMIR_EXEC_BACKLOG` M1–M8 冒烟；工程项见 `GATEWAY_STABILITY_BACKLOG.md`。
3. **真源树**：提交与推送在 `~/src/MimirAether`；勿与 `MIMIR_AETHER_HOME` 混淆。
4. **维持 M6 绿**：受保护路径合入不长期漏记。
5. **维持 B/C/∞ 绿**：各阶段 checklist §执行记录续更。

---

## 6. 距终极目的多远？（2026-05-19 · 刘哥问）

**终极目的**（[`成长路线图.md`](../成长路线图.md)）：**织界者养成系统** — 能自主学习、自主进化，不是 Hermes 复制品。

| 层 | 完成度 | 证据 | 还差什么 |
|----|:------:|------|----------|
| **A. 能跑、能回归、能运维** | **~85%** | M0–M6 绿 · CLEARANCE **8/8** · tier0 **382+2** · Gateway 飞书真对话 | TRUNCATE 历史噪声 monitoring；#32 close；Gateway Chroma 增量 |
| **B. 默认「想起来」**（阶段1） | **~65%** | hybrid **生产默认** · Chroma **增量** · search-first prompt · SEM 全栈 | ADR-002 注入策略 · 飞书「上次在做什么」稳定复现 · rubric #8 仍 3.0 |
| **C. 默认「会话后会进化」**（阶段2） | **~65%** | Gate C：`AUTO_EVOLVE=1` + 真实 SKILL · IQ-EVO-40 时序 · 1c policy（默认关） | 生产默认进化肌肉 · IntentPredictor · rubric #1 仍 3.5 |
| **D. 织界者伙伴**（阶段3–4 终局） | **~25%** | 文档 ∞ 绿裁定 · 宪章草案 | 长期画像 · 集体技能网 · 刘哥角色从「验收者」→「同行者」**可感知** |

**一句话**：**底座和纪律已经很远**（这不是传话桶能有的）；**「日常用起来明显更聪明、会自己变好」大约还有一半到三分之二的路**，主要在 §15 **IQ-EVO-01～06** 和 Horizon 下一拍（ADR-002 / nudge / AUTO_ANALYSIS），不是再堆 tier0。

**劳动不被质疑的依据**：P0 清空 · IND 独立 · IEVO 工业进化 · SEM 语义波 · 3827 条索引 — 均为**可 diff、可复跑**的交付；rubric 低分说的是 **Hermes 对照下的行为默认项**，不是「没干活」。

---

## 5. 更新日志（倒序）

| 日期 | 摘要 |
|------|------|
| 2026-05-26 | **OBS-B1-01**：ADR-007 ObservabilityBus defer；Wave 3 **14 [x]**；tier0 **398+2**。 |
| 2026-05-26 | **进度**：执行队列 **4 粒**（14 + B1×3）；CLEARANCE **8/8**；Wave 3 Cursor **11～13 [x]**；tier0 **393+2**。 |
| 2026-05-26 | **刘哥拍板**：先 **IQ-EVO Wave 3** · 再 **Horizon B1**（`P1-LONG-OBS`/d6）；bridge §1 + backlog §15/§16。 |
| 2026-05-19 | **Horizon A / IQ-EVO Wave 2** [x]：07～09 工程 + Mimir 验收；tier0 **382+2**。 |
| 2026-05-19 | **Horizon A / P2-LONG-IQEVO Wave 1** [x]：IQ-EVO-06 结案 · rubric **3.9/10** documented 例外 · eval 周常 · closeout [`p2-long-iqevo-closeout.md`](./phase0/p2-long-iqevo-closeout.md)。 |
| 2026-05-19 | **刘哥定调**：Mimir = 智能体 ≠ 传话桶；MAINLINE §6 距终局快照；bridge/backlog/issues/方向文档 §0.1 同步。 |
| 2026-05-19 | **Horizon A / P2-LONG-SEM** [x]：SEM-06 结案 + closeout doc；tier0 **368+2**；GH **#32** 待刘哥 close。 |
| 2026-05-19 | **Horizon A / SEM-05** [x]：tier0 manifest + smoke；**363+2**；下一条 **SEM-06**。 |
| 2026-05-19 | **Horizon A / SEM-04** [x]：benchmark `semantic_hit_rate` + eval compare；tier0 **358+2**；下一条 **SEM-05**。 |
| 2026-05-19 | **Horizon A / SEM-03** [x]：`semantic` / `semantic_hybrid` session_search backend；tier0 **349+2**；下一条 **SEM-04**。 |
| 2026-05-19 | **Horizon A / SEM-02** [x]：`chroma_session_indexer` + `backfill_chroma_sessions.py`；tier0 **342+2**；下一条 **SEM-03**。 |
| 2026-05-25 | **Horizon A / SEM-01** [x]：ADR-006 + path-contract + backlog §14；tier0 **332+2**。 |
| 2026-05-25 | **IEVO-06** [x]：Wave E 结案 doc + contract ievo06；**P2-LONG-IEVO** [x]；**D8** ✅；tier0 **326+2**。 |
| 2026-05-25 | **IEVO-05** [x]：D6-3 monitor/insights 回归（5 行为 + 3 contract）；tier0 **322+2**。 |
| 2026-05-25 | **IEVO-04** [x]：`run_evolution_eval.sh` + compare；本机 eval pass（LIKE 60% / FTS 50%）。 |
| 2026-05-25 | **IEVO-03** [x]：ADR-005 observability SoT；`execution_recorder` → `get_mimir_data_dir()`；contract IEVO-03。 |
| 2026-05-25 | **IEVO-02** [x]：`test_skill_evolution` + `test_self_evolution_jepa` 入 tier0；manifest contract；**306+2**。 |
| 2026-05-25 | **IEVO-01** [x]：`evolution_audit` + `record_m6` 禁伪进化标记；contract IEVO-01；tier0 **284+2**。 |
| 2026-05-25 | **IND-06** [x]：§8 独立宣言；**刘哥签收**（可对外承诺）；**Wave D** 全结案；**D7** ✅。 |
| 2026-05-25 | **IND-05** [x]：`persistent_store` 锁 + ADR-001 Accepted；GH #20 closed；tier0 **278+2**。 |
| 2026-05-25 | **IND-04** [x]：ADR-004 + `test_mimicore_openclaw_boundary_ind04`；tier0 纳入 contract IND-02/03/04。 |
| 2026-05-25 | **IND-01～03** [x]：Night1 PR — ADR-003、contract IND-02/03、`get_mimir_session_search_db_path()`；tier0 **267+2**；**D7** 部分绿。 |
| 2026-05-25 | **Wave 2 C [x] STAB-07**：Gateway 十条无「移交工程」；`GATEWAY_STABILITY_BACKLOG.md` 刷新；GH **#25–30** closed；下一条 **IND-01**。 |
| 2026-05-25 | **§13.1 P0-LONG-CLEARANCE** | **Cursor** | 母任务 A→E + STAB/IND/IEVO 子项表；Done 对照；§9/§10 刷新 |
| 2026-05-25 | **Wave 0 卫生** [~] | **Cursor** | masterplan + §13；GH 10 open；TRUNCATE P0；PID **90544** |
| 2026-05-24 | **P1-LONG-MEM** [x] 结案：M01～M06 文档收口；基准 LIKE **60%** / FTS **50%** / hybrid 推荐；backlog §11 Active **0**；main `7f4b53d`。 |
| 2026-05-24 | **P1-M05** [x]：`prompt_builder._build_cross_session_context` → runtime home；`agent/test_prompt_builder_cross_session_paths.py`；GH **#18**；tier0 **245+2**。 |
| 2026-05-24 | **P1-M04** [x]：`prepare_fts5_match_query` 修 hyphen/dot；`session_search` 接 `SESSION_SEARCH_BACKEND`；`tests/tools/test_fts5_prepare_query.py`；tier0 **245+2**。 |
| 2026-05-24 | **A2** [x]：`.openclaw` 母 issue **#2** 结案；`MIMIR_OPENCLAW_BOUNDARY.md` §7；tier0 **245+2** + advisory **6/60**。 |
| 2026-05-24 | **A1** [~]：`restart_gateway_hard.sh` → PID **691521**；`/health` + 飞书 WS ok；T-03/T-04 人工 smoke 待刘哥（`mimir_prod_smoke.md`）。 |
| 2026-05-24 | **P1-M03** [x]：Gateway 增量写入 `sessions_search.db`；`tests/gateway/test_session_search_incremental.py`；tier0 **245+2**（`027eaaf`）。下一条 **P1-M04**。 |
| 2026-05-24 | **P1-M02** [x]：合入 `session_search_indexer`、backfill、20-query 基准（LIKE **60%**）；M6 + tier0 **237+2**（`6650327`/`60192d3`）。 |
| 2026-05-26 | **§15 Wave 4 [x]**：FeedbackCollector 生产 · IQ **4.5/10** · §17 飞书验收签收 · tier0 **433+2** · 下一 Horizon 待拍板。 |
| 2026-05-24 | **Phase 1 排队**：`MIMIR_EXEC_BACKLOG.md` **§11** — 长任务 `P1-LONG-MEM`（6 子项）；§9.1 未完成项盘点；默认执行源从 §2 切到 §11。 |
| 2026-05-24 | **EV-A03** [x]：Memory 检索基准 → `docs/phase0/memory-retrieval-baseline.md`。**Phase 0 真相图谱 14/14 完成**。 |
| 2026-05-24 | **EV-A02/A04/A05** [x]：Mimicore 依赖刷新、架构 **6.1/10**、prompt guard 可拆点。 |
| 2026-05-24 | **EV-Q01–Q04** [x]：硬编码 23 项、ToolQuality DB 快照、IntentPredictor 仍无、IQ **~3.8/10**。下一条 **EV-A02**。 |
| 2026-05-24 | **EV-A01** [x]：Agent Core 职责映射（重叠 ~32%，core→MimirAgentLoop 委托）→ `docs/phase0/agent-core-responsibility-map.md`。下一条 **EV-A02**。 |
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
