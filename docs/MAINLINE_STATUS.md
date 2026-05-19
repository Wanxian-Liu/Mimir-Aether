# 主线进度快照

> **单一更新入口**：用户问「进度 / 主线 / 完成度」时，协作者应先 **Read 本文件**，再根据当前仓库事实与可选命令输出 **更新下列表格与日期**，必要时补一行「本轮变更摘要」。  
> 权威依据：`docs/DEVELOPMENT_NORTH_STAR.md`、`docs/ralph_roadmap_milestones.md`、`成长路线图.md`、`docs/ralph_parity_testmap.md`、`docs/ralph_tier0_case_matrix.md`。

| 字段 | 值 |
|------|-----|
| **最近更新** | 2026-05-19 |
| **更新人** | MimirAether Session 72 |
| **仓库根（真源）** | 以当前用于 `git push` 的 clone 为准（例如 `~/src/MimirAether`）；勿写死 `~/.openclaw/projects/...` |
| **可选校验** | `./run_ralph_tier0.sh`（门禁）；[`scripts/smoke_mimir_home.sh`](../scripts/smoke_mimir_home.sh)（独立 home smoke）；宽 pytest 见 [`.github/workflows/pytest-wide.yml`](../.github/workflows/pytest-wide.yml)；里程碑 A 项需真环境手动/清单 |
| **本轮摘要** | Hermes 8模块 + OpenSpace 8模块 双战役完成。新交付: agent_loop DI, ContextEngine ABC, DeepSeek指导, 身份解耦, 执行录制/质量追踪/分析器/进化引擎(5文件972行)。独有能力: TaskLoop/Capsules/CausalAR/Beliefs/M0-M6。Tier0 7/7 ✅。 |

---

## 1. 工程里程碑（Ralph / Parity）

| ID | 名称 | 状态 | 说明 |
|----|------|------|------|
| M0 | 基线可回归 | **绿** | `run_ralph_tier0.sh` 日常可通过。**稳定性（2026-05-10，真源）**：Gate2 **160**、Gate3 **2**（以脚本输出为准）。发版/大合并前建议复跑：`for n in 1 2 3; do ./run_ralph_tier0.sh || exit 1; done` |
| M1 | 契约可执行 | **绿** | `docs/ralph_parity_testmap.md` 已映射；扩展项见 ext / 另增 |
| M2 | Tier-0 矩阵闭合 | **绿** | `ralph_tier0_case_matrix.md`：当前无阻塞 P0；契约变更后需复核 |
| M3 | 垂直切片 | **绿** | **两条**：CLI（`docs/m3_cli_quick_task_slice.md`）+ **API** `POST /v1/chat/completions`（`docs/m3_api_chat_slice.md`，`agent/test_m3_api_chat_slice.py`） |
| M4 | Tier-2 HTTP（可选） | **绿** | 路线图 M4 判据对齐：无网无 key；**`fixtures/m4_http/`**（`error_shapes.json` + README）+ **`scripts/refresh_m4_http_fixtures.sh`**；401 / 429 / 计费 429 / 超时 / 连接类形态经 **`agent/test_m4_auxiliary_http_slice.py`**（含 JSON 驱动用例）。详见 **`docs/m4_auxiliary_http_slice.md`**；VCR / 常驻 mock 为增强项 |
| M5 | 内核可替换 | **绿** | 产出物与 **`docs/ralph_roadmap_milestones.md`** M5 判据已对齐：多端口 seams（LLM / tool / session restore / checkpoint）、`SessionDbClientFactory`、`AgentKernelOverrides`、CLI/API 注入、`GatewayRunner(session_db_factory=)` 与 `SessionStore` JSONL↔SQLite（含 `rewrite_transcript`）；清单与验收见 **`docs/m5_kernel_replaceability_slice.md`**。可替换 = 边界可注入 + 各切片验证 + 默认路径 **`./run_ralph_tier0.sh`** 全绿；**全栈第二套生产实现同时替换**若需要则另立项 |
| M6 | 进化可审计 | **绿** | 产出物与 **`docs/ralph_roadmap_milestones.md`** M6 判据对齐：**`docs/M6_EVOLUTION.md`**、**`docs/evolution_log.md`**、**`scripts/record_m6_evolution.sh`**、**`.github/pull_request_template.md`**；**`core.hooksPath=.githooks`** 时 pre-push 在 tier0 通过后对「受保护路径变更但未含 `evolution_log`」打印软提醒（见 **`docs/M6_EVOLUTION.md`**）。合入仍须带门禁证据；受保护变更用 `record_m6` 或 PR 模板 **Recorded**；豁免见 M6 文档。**维持**：勿长期跳过记录 |

状态图例：**绿** = 满足文档完成判据或等价；**黄** = 部分/待复核；**未** = 未达成。

---

## 2. 产品阶段（成长路线图）

| 阶段 | 里程碑 | 状态 | 说明 |
|------|--------|------|------|
| 1 Hermes 影子期 | **A**：CLI + gateway + 工具链 + 基础 RL | **绿** | Smoke：A1–A4 已验；**飞书** 应用 **mimiraether** 真实消息已通（`mimir_prod_smoke.md`） |
| 2 专项伙伴期 | B | **绿** | 证据见 **`docs/mimir_phase_b_checklist.md`**（§B 绿裁定记录、§执行记录）；依赖 **A** 已绿。**范围**：工程可审计的伙伴交付链（git + M6 日志 + MAINLINE）；路线图人际条款仍由负责人日常验收。**维持**：新任务继续往 §执行记录 追加 |
| 3 独立学习期 | C | **绿** | 证据见 **`docs/mimir_phase_c_checklist.md`**（§C 绿裁定记录、§执行记录）；**≥3** 主题报告见 **`docs/phase_c_studies/`**；对照 **`docs/hermes_mimir_behavior_matrix.md`**（§4 目标 D）。**范围**：工程可审计的独立学习链；路线图「自动记忆殿堂」未接管道时以仓库报告+清单为准。**维持**：新主题继续 §执行记录 |
| 4 自主进化期 | ∞ | **绿** | 证据见 **`docs/mimir_phase_infinity_checklist.md`**（**§∞ 绿裁定记录 #1**、§∞1 索引、§∞2 样本 **#1–#2**、§宪章对照审查 **#1–#2**）；宪章 **`docs/weave_charter.md`**（v0.1 草案）。**范围**：工程可审计的自主进化周期已满足清单 §建议的 ∞「绿」门槛（`as-of` 见清单 §∞1）；**价值观**人际验收仍由负责人承担。**维持**：新周期继续 §执行记录 + M6 + tier0 |

---

## 3. 两条主线健康度

| 主线 | 健康度 | 备注 |
|------|--------|------|
| **Parity** | 强 | 契约 + Gate1–3 + 测试映射可追踪 |
| **Evolution** | 强 | M6 标 **绿**：规则 + 日志 + 脚本 + PR 模板 + pre-push 提醒；见 `docs/evolution_log.md` |

---

## 4. 近期焦点（可改）

0. **真源树**：提交与推送在**当前用于远端的 git clone 根**（勿写死 `~/.openclaw/...`）；备份/镜像 checkout 的改动须 **reconcile** 后再推（**[`docs/path-contract.md`](path-contract.md)**、**[`AGENTS.md`](../AGENTS.md)**）。
1. **执行 M6**：合并前对「agent / gateway / tools / 契约测试」类 PR 运行 `./scripts/record_m6_evolution.sh "…"` 或等价手工行（纯文档豁免见 **`docs/M6_EVOLUTION.md`**）。
2. 保持 `run_ralph_tier0.sh` 全绿；合入用 Ralph 模式三轮（若启用严格迭代）。
3. **维持 M6 绿**：受保护路径合入不长期漏记；新 clone 记得 `git config core.hooksPath .githooks`。
4. **维持 B 绿**：伙伴期任务继续在 **`docs/mimir_phase_b_checklist.md`** §执行记录 留痕；重大偏离时复核 §B 绿裁定记录中的**范围说明**。
5. **维持 C 绿**：每轮独立学习更新 **`docs/mimir_phase_c_checklist.md`** §执行记录；重大偏离时复核 §C 绿裁定记录中的**范围说明**。
6. **维持 ∞ 绿**：每轮自主进化更新 **`docs/mimir_phase_infinity_checklist.md`** §执行记录；重大偏离时复核 **§∞ 绿裁定记录 #1** 与 **`docs/weave_charter.md`**。

---

## 5. 更新日志（倒序）

| 日期 | 摘要 |
|------|------|
| 2026-05-18 | **状态刷新**：Session 199；TaskLoop v2.x 多轮迭代；R1–R12 参数调优；tier0 162+2 全绿。 |
| 2026-05-16 | **路径叙事（阶段 A）**：文档与根脚本对齐「clone 根 vs `MIMIR_AETHER_HOME`」；默认数据根 `~/.mimiraether`；tier0 绿。 |
| 2026-05-13 | **Phase VI 物理删除**：`hermes_cli/` 60+文件(76K行)删除；`mimcore/` 删除；`memory/persistent.json`删除；新增`mimir_state.py`(1019行)；12个Hermes遗存技能清理；`web_server.py` 7处mimcore引用迁移。Ralph tier0 162+2全绿。3 commits。 |
| 2026-05-11 | **Phase V 深入脱钩完成**：`hermes_constants.py` 已删除（导入→mimir_constants）；`hermes_logging.py` 已删除（导入→mimiraether_logging）；`hermes_state.py`→`mimir_state.py`（9处导入已更新）。Hermes独立路线 I-V 全线闭合。 |
| 2026-05-11 | **Skill Curator 全线完成**：闭环验证通过（6/6 milestones），end_session 自动胶囊化 + skill_view 复活链路就绪；77 技能全 fresh, 0 dormant。 |
| 2026-05-11 | **Phase B 清零**：`auxiliary_client.py` 16→0 hermes_cli 导入；新增 `agent/provider_registry.py`、`runtime_provider.py`、`model_normalize.py`；`mimcore/auth.py`/`config.py` 翻转为 Mimir 原生路径；Ralph 3 轮连续全绿 (162+2)；M0 稳定性条更新。 |
| 2026-05-05 | **里程碑 ∞ 绿（工程裁定）**：**[`mimir_phase_infinity_checklist.md`](mimir_phase_infinity_checklist.md)** §∞ 绿裁定记录 **#1** + 宪章对照 **#2**；MAINLINE **∞** **黄→绿**；**M6** 见 `evolution_log` **里程碑 ∞ 绿** 行。 |
| 2026-05-07 | **织界宪章草案**：新增 **`docs/weave_charter.md`**（v0.1）；**[`mimir_phase_infinity_checklist.md`](mimir_phase_infinity_checklist.md)** §宪章对照审查记录 **#1**；**∞** 仍为 **黄**（∞1/∞2 门槛未齐）。 |
| 2026-05-06 | **真源习惯 + ∞ 推进**：**[`docs/path-contract.md`](path-contract.md)** 增加 §协作习惯（Git 真源）；**[`docs/mimir_phase_infinity_checklist.md`](mimir_phase_infinity_checklist.md)** 增加 §当前推进与执行记录（∞ 仍为 **黄**）。 |
| 2026-05-05 | **阶段 4 启动**：新增 **`docs/mimir_phase_infinity_checklist.md`**；MAINLINE 里程碑 **∞** 标 **黄**（自主进化期进行中）。 |
| 2026-05-04 | **里程碑 C 绿**：**`docs/phase_c_studies/`** 三主题报告 + **`hermes_mimir_behavior_matrix.md`** §4 目标 D；**`docs/mimir_phase_c_checklist.md`** §裁定与执行记录；MAINLINE **C** 标 **绿**；**M6** 见 `evolution_log` **里程碑 C 绿** 行。 |
| 2026-05-04 | **阶段 3 启动**：新增 **`docs/mimir_phase_c_checklist.md`**；MAINLINE 里程碑 **C** 标 **黄**（独立学习期进行中）；默认首主题与 behavior_matrix 见清单。 |
| 2026-05-04 | **里程碑 B 绿**：**`docs/mimir_phase_b_checklist.md`** 补齐 §B 绿裁定记录与执行记录（≥3 交付 + 四类任务）；MAINLINE **B** 标 **绿**。 |
| 2026-05-04 | **阶段 2 启动**：新增 **`docs/mimir_phase_b_checklist.md`**；MAINLINE 里程碑 **B** 标 **黄**（伙伴期进行中）。 |
| 2026-05-04 | **M4 绿**：`fixtures/m4_http/` + `scripts/refresh_m4_http_fixtures.sh`；扩展 `test_m4_auxiliary_http_slice`；工程表 **全绿**（M0–M6 除路线图自声明可选项外已闭合）。 |
| 2026-05-04 | **M0 稳定性条**：真源连续 **3** 次 `./run_ralph_tier0.sh` 全绿；MAINLINE M0 说明已记证据与复跑命令。 |
| 2026-05-04 | **M6 绿**：MAINLINE 标 **绿**；Evolution 健康度 **强**；闭环 = M6 文档 + `evolution_log` + `record_m6` + PR 模板 + pre-push 软提醒（`.githooks/pre-push`）。 |
| 2026-05-04 | **M5 绿**：路线图 M5 判据复核通过；MAINLINE 标 **绿**；同步 **`docs/ralph_roadmap_milestones.md`** M5「最小切片」与仓库事实一致。可替换范围见 M5 表内说明（全栈第二实现非必要条件）。 |
| 2026-05-03 | **M5（续）**：CLI/API 入口注入 `llm_backend`；`agent/test_m5_entry_llm_injection_slice.py`；MAINLINE 说明更新。 |
| 2026-05-03 | **M5 黄**：`agent/llm_port.py` + `agent/test_m5_kernel_replaceability_slice.py` + `docs/m5_kernel_replaceability_slice.md`，纳入 `run_ralph_tier0.sh`；模型调用端口显式化（替换说明见文档）。 |
| 2026-05-01 | **M4 黄**：`agent/test_m4_auxiliary_http_slice.py` + `docs/m4_auxiliary_http_slice.md`，纳入 `run_ralph_tier0.sh`；分类层离线断言（401 / 429 语义 / 超时形状）。 |
| 2026-05-02 | **M6 黄**：新增 `docs/M6_EVOLUTION.md`、`docs/evolution_log.md`、`scripts/record_m6_evolution.sh`，`AGENTS.md` 合并指引；tier0 当次全绿。 |
| 2026-05-02 | M3 **第二条**：`agent/test_m3_api_chat_slice.py` + `docs/m3_api_chat_slice.md`，纳入 `run_ralph_tier0.sh`；M3 标 **绿**。 |
| 2026-05-02 | 飞书连接成功（应用 **mimiraether**）；里程碑 **A** 标 **绿**。 |
| 2026-05-01 | 里程碑 A smoke 首轮：代理回报写入 `mimir_prod_smoke.md`；A2 真实消息仍缺，阶段 1 保持黄。 |
| 2026-05-01 | 新增 `docs/mimir_prod_smoke.md`：里程碑 A（A1–A4）真环境勾选表。 |
| 2026-05-01 | M3：落地 `agent/test_m3_cli_quick_task_slice.py` + `docs/m3_cli_quick_task_slice.md`，纳入 `run_ralph_tier0.sh`。 |
| 2026-05-01 | 初版：建立本文件；工程 M0–M2 绿、M3–M6 未；阶段 1 黄；Parity 强、Evolution 弱。 |
