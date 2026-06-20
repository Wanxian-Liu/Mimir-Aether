# MimirAether 执行待办（统一 backlog）

> **最近更新**：2026-06-04（**HC-01/03 关闭** · 守卫修复 · 复盘工具 · CacheAligner · 关闭退场）  
> **离线沟通**：`docs/MIMIR_LIU_CURSOR_BRIDGE.md` §4/§5  
> **规则**：**§20.7 HC 轨**（ISSUES #4 工程整改 · 按角色取第一条 `[ ]`）· **TASK_QUEUE §14**（IQ-55 行为轨 · 与 **HC-03** 同目标）· **§20.1/§20.2 已收口**。历史 §19 只读归档。  
> **Mimir 主执行**（2026-06-01）：[`MIMIR_PRIMARY_EXECUTOR.md`](./MIMIR_PRIMARY_EXECUTOR.md) · 任务 [`MIMIR_TASK_QUEUE.md`](./MIMIR_TASK_QUEUE.md) **§9** · Cursor 只复核 HANDOFF。  
> **卡住**：记 `docs/ISSUES.md` 或 `docs/MIMIR_ISSUES.md`，停手等刘哥。  
> **勿提交**：`data/persistent.json`（runtime 镜像）。

**Wiki 审计原文**（只读、勿改 HTML）：`~/.openclaw/wiki/main/iterations/d{1..7}-audit-report.html`  
**Wiki 评注（经验层）**：`docs/MIMIR_D17_WIKI_AUDIT_COMMENTARY.md` — 对照真源逐阶段评价，2026-05-20

---

## 1. 角色分工（避免 d4 / D4心跳 混淆）

| 角色 | 做什么 | 不做什么 |
|------|--------|----------|
| **Mimir** | 冒烟、复现、飞书端到端、grep 日志、更新 ISSUES / 本表状态、**§19.6 MI-AWAY-*** 离线粒、证据卷 | 改 `agent/`/`gateway/`/`mimir_cli/` 架构；删 `role=tool` 伪修复；填进化 19 存根 |
| **Cursor / 工程** | d1–d7 **代码**、拆分、合 `main`、tier0、evolution_log | 代刘哥配密钥、代发飞书 |
| **刘哥** | `OPENROUTER_API_KEY`、飞书复验、授权 `git push` | — |

**身份（2026-05-19 刘哥定调）**：**Mimir = 智能体**（gateway · 工具 · 记忆 · 进化链），**≠** DeepSeek API 传话桶。`MIMIR_IQ_EVOLUTION_DIRECTION.md` 的分数是 **相对 Hermes 的行为 rubric**，不是否定已交付工程（CLEARANCE 8/8 · SEM 波 · tier0 **368+2**）。

**刘哥离线习惯**：Cursor 更新 **`docs/MIMIR_D17_AUDIT_AND_TASKS.md`**（d1–d7 审计分 + **T-01～T-11** 任务/方案/提示词）→ Mimir 新窗用 §5 总提示词执行 → 自证后改本表 §4 与 `MIMIR_ISSUES.md`。

**历史事实（刘哥口径）**：**d1–d3** 阶段 Mimir 已承担大部分 **验证与收口**（飞书收图/token、上下文链、Gateway P0 冒烟、十条里多项）；**代码合入**在 `main`（如 `341c1fd`、`2b414d3`、`393214e`、P2 PR）。**d4 起**以 Cursor 工程为主，Mimir 只做 §2 中 **M-*** 项。

---

## 2. 统一执行队列（Phase 1.5 已完成 · 只读归档）

> **Phase 1.5（E-001～E-012 + intent-action guard）已全部 `[x]`** — 新窗勿从此表取「下一条工程项」；执行源见 **§9 续跑（2026-05-24）** 与 Prompt 2 将建的 Phase 0 队列。  
> 状态：`[ ]` 待做 · `[~]` 部分/阻塞 · `[x]` 完成  
> **基线**：tier0 **237+2**；IR + E-001～E-012 已合 main

| ID | 负责 | 任务 | 成功标准 | 状态 |
|----|------|------|----------|------|
| **E-001** | Cursor | **Gateway WIP 常驻** — mixin 拆分遗漏 `@property` | `pgrep` 稳定；`wait_for_shutdown` 正常 | [x] 见下「E-001 结案」 |
| **E-002** | Cursor | **D3-SPLIT 收尾** — 6 mixin + `home_paths.py` + commit | tier0 绿；gateway 硬重启后 PID 常驻 | [x] 2026-05-20 |
| **E-003** | Cursor | **D4-P0-4** — agent 四 mixin（同 commit） | tier0 绿 | [x] 2026-05-20 |
| **E-IR** | Cursor | **IR-20260520** — recovery 禁 TRUNCATE on 代码错误；exec_mixin import；gateway 冒烟测 | tier0 **181+2**；TRUNCATE 基线 **19** 冻结；飞书 tool Go | [x] 2026-05-20 |
| **M-002** | Mimir+刘哥 | **M2 飞书发图**（识图 **搁置**） | `Image downloaded`；**不要求**描述图 | [x] deferred — 识图 **EV-VISION-DEFER**；发图路径已验（EV-M01） |
| **M-003** | Mimir+刘哥 | **M3 空表头表** | 列名 `—`；无 230099 | [x] deferred — 代码已合；刘哥暂不飞书复验（CLOSE-3） |
| **M-005** | 刘哥 | **M5 OPENROUTER** | — | [x] **N/A** — 刘哥 **仅用 DeepSeek**，不配 OpenRouter |
| **M-007** | Mimir | **M7 Gateway 十条** | `GATEWAY_STABILITY_BACKLOG.md` 逐条标状态 | [x] 2026-05-20 状态列已更新 |
| **E-004** | Cursor | **D7-0a** `CLI_CONFIG` 默认值 | clarify/approval 不 ImportError | [x] 2026-05-23 WIN-1 · tier0 181+2 |
| **E-005** | Cursor | **D7-0b + D7-1** chat 解耦 + 单入口文档 | `cmd_chat` 不 `import cli.main` | [x] 2026-05-23 WIN-4 · chat_runner + MIMIR_ACTIVATE D7-1 |
| **E-006** | Cursor | **D6-0a–0d** 可观测 Day-1 | insights SQL + monitor 阈值 + health 接线 | [x] 2026-05-23 |
| **E-007** | Cursor | **D5-0 / 0b** 进化安全基线 | recorder 隔离 + skill 路径白名单 | [x] 2026-05-23 |
| **E-008** | Cursor | **D7-2 / D7-3** 删旧 cli + CLI 冒烟测 | grep 无悬挂引用 + 少量 pytest | [x] |
| **E-009** | Cursor | **D5-2** 单通路 FIX 真写 SKILL | 一条 e2e + tier0 | [x] 2026-05-23 |
| **E-010** | Cursor | **ISSUES #9** gateway NameError 止血 | `_shared` 模块级绑定 + 烟测 | [x] 2026-05-23 |
| **E-011** | Cursor | **Phase 1.5 运行时加固** — 011a import/日志；011b Duration P50/P95/P99；011c MemoryFencer 用户入站 | tier0 **225+2**；`/health` 含 `agent_tool_p95_ms` | [x] 2026-05-23 |
| **E-012** | Cursor | ISSUES #7 JEPA `run_cycle` 接 agent loop（env 门控，默认 analyze/plan/record） | tier0 **231+2**；mock 集成测 | [x] 2026-05-24 |
| **M-008** | 刘哥 | **M8 push** | 授权后 `git push origin main` | [x] 2026-05-20 → `599ecb3` |

**E-001 结案（2026-05-20）**  
- **根因**：`gateway/health_mixin.py` 拆分时 `should_exit_cleanly` 未成 `@property`，`start_gateway()` 里 `if runner.should_exit_cleanly:` 恒真 → 跳过 `wait_for_shutdown()`，约 2–3s exit 0（非 aiohttp 主因）。  
- **修复**：`health_mixin` 补 `@property`；`session_mixin` 补 `display_hermes_home` 导入。  
- **验证**：tier0 PASS；PID **155486** 常驻；日志 Cron ticker + Lark wss；硬重启后无即退。`Unclosed client session` 为即退连带，稳定后不再现。

**并行允许**：E-004（D7-0a）单独 PR；**禁止** mixin commit + D6 + 删 `cli.py` 同 PR。

**下一条（默认）**：**勿用本 §2** — 见 **§9 续跑（2026-05-24）**；工程 backlog 由 Prompt 2 建 Phase 0。

---

## 2d. 关账队列（Prompt 1 · 2026-05-24 · 文档收口）

| ID | 任务 | 状态 |
|----|------|------|
| **CLOSE-1** | ISSUES 归档 Active≤3 | [x] |
| **CLOSE-2** | 替换 §9 过时续跑 | [x] |
| **CLOSE-3** | M-003 空表头 → deferred（刘哥暂不飞书复验） | [x] |
| **CLOSE-4** | M-002 识图 → EV-VISION-DEFER | [x] |
| **CLOSE-5** | EV-M12 可选 → skipped | [x] |

---

## 2j-2. 琬弦工程第二期 · 测试轨（EP-C* · Cursor）

> 每 PR **3 条** pytest；目录 **`tests/agent/`**；mock LLM、无网。仍禁改 `core_loop` / gateway mixin。

| ID | 任务 | 成功标准 | 状态 |
|----|------|----------|------|
| **EP-C01** | agent_loop 集成测 ×3 | `tests/agent/test_agent_loop_integration.py` + tier0 | [x] 2026-05-23 |
| **EP-C02** | agent_loop 边界 ×3 | JSON/多工具/max_turns · `test_agent_loop_edge.py` | [x] 2026-05-23 |
| **EP-C03** | skill_evolution 烟测 ×3 | gate/FIX/DERIVED · `test_skill_evolution_smoke.py` | [x] 2026-05-23 |
| **EP-C04** | self_evolution 烟测 ×3 | IC/analyze/memory · `test_self_evolution_smoke.py` | [x] 2026-05-23 |

---

**交接文档**：`docs/MIMIR_HANDOFF_20260520.md` · **微信简报**：OpenClaw skill `mimir-handoff-weixin`（`~/.openclaw/workspace/skills/`）

---

## 2b. Mimir 离线进化微迭代（EV-M* · 小颗粒 · 可跨多轮）

> **刘哥 2026-05-20**：识图麻烦 → **暂时搁置**（`EV-VISION-DEFER`）。主模型 **DeepSeek-only**，不配置 `OPENROUTER_API_KEY`。  
> **执行法**：每轮只做 **一个** EV-M 粒度；做完勾 `[x]`、改 §4 一行、飞书回报 3～5 行；**禁止**改 `agent/`/`gateway/`/`mimir_cli/`；**禁止**提交 `persistent.json` / `git push`。  
> **映射**：与 `MIMIR_D17` 的 T-02～T-12 对齐，但验收盘点按本表。

| ID | 颗粒 | 做什么（仅文档/日志/grep） | 验证 / 完成标准 | 状态 |
|----|------|---------------------------|-----------------|------|
| **EV-M01** | T-02 -lite | 飞书发图或查历史 log：`Image downloaded` | `grep Image downloaded agent.log` 有命中；识图 **不测** | [x] 2026-05-20 agent.log 命中；vision blocked (deepseek 无 image_url) |
| **EV-M02** | T-03 | 飞书要一张 **空列表头** 表或复现 #9 | 无 `230099`；列名 `—`；更新 M-003 | [x] deferred — 代码已合；CLOSE-3 暂不飞书复验 |
| **EV-M03** | T-05 | 记 `OPENROUTER:absent` + DeepSeek-only 策略一行 | `MIMIR_ISSUES.md` 或 §4 注明 N/A，不索要 key | [x] OPENROUTER:absent 确认；DeepSeek-only |
| **EV-M04** | T-06 | API/路由清单：只读 `docs/` + `gateway/platforms/` 文件名列表 | 回报 ≤15 行清单，无改码 | [x] 清单完成：loopback/无api_server段/符合SECURITY |
| **EV-M05** | T-07 | reaction/表情路径：grep `gateway` + 最近 `gateway.log` | 1 条 pass/fail + log 行号 | [x] 未复现 — gateway.log 无 reaction 记录 |
| **EV-M06** | T-08 | agent 栈：grep `Provider`/`deepseek`/`model` 配置线索（不打印 key） | 回报主 provider=deepseek 证据 1～3 行 | [x] provider=deepseek 确认；21 次 Agent error；TRUNCATE=19 |
| **EV-M07** | T-09 | d5 只读：`evolution_log.md` 末 5 行 + `grep simulated` agent/ | 列 1 条「空壳/真进化」观察，**不填** 19 存根 | [x] evolution_log 活跃(5条 May19-20)；self_evolution 仅 SKILL.md |
| **EV-M08** | T-10 | d6 只读：`insights`/`monitor`/`health` 文件存在性 + 1 缺口 | 1 条缺口写入 ISSUES（供 E-006） | [x] ~15 ERROR；top: is_truthy_value(7)/_load_gateway_config(3)/_dequeue_pending_event(3) |
| **EV-M09** | T-11 | d7 只读：复现 `CLI_CONFIG` ImportError 线索（grep/python -c） | ISSUES 一条指向 **E-004**，Mimir 不修 | [x] ImportError 复现：cannot import CLI_CONFIG |
| **EV-M10** | 稳定性 | `GATEWAY_STABILITY_BACKLOG.md` #2 #9 对今日 log 再 grep | 两条状态 [x]/[~] 有 log 行 | [x] #9 历史230099已记录；#2 token正常 |
| **EV-M11** | IR 看守 | `grep -c 'Level 3 TRUNCATE' agent.log` 必须 **≤19** | 若 >19：ISSUES P0 + 停手 | [x] TRUNCATE=19 基线保持 |
| **EV-M12** | T-12 可选 | `MIMIR_D17_WIKI_AUDIT_COMMENTARY.md` 任选一节 vs 仓库一句 | 1 条一致/漂移 | [x] skipped — CLOSE-5 可选颗粒不阻塞 |
| **EV-M13** | 汇总 | 飞书发 **刘哥离线包**（见下模板） | 含 EV-M01～12 勾选表 + 需刘哥 3 条以内 | [x] 本回报即为汇总 |
| **EV-VISION-DEFER** | 搁置 | 自动识图 / OPENROUTER / `vision_analyze` 端到端 | 刘哥明确「恢复识图」前 **不做** | [~] 搁置 |

**刘哥离线 · Mimir 飞书回报模板（EV-M13）**

```text
[Mimir 离线进化包] 2026-__-__
Gateway PID: ___ | TRUNCATE: ___ (须≤19)
EV-M01..12: (列表勾选)
识图: 搁置 EV-VISION-DEFER
需刘哥: (≤3条，如 T-03 代发图 / E-004 授权 / 无)
建议 Cursor: E-004 单独 PR
```

**Mimir 新窗一句（刘哥已发 §5 时可只贴此句）**

```text
按 docs/MIMIR_EXEC_BACKLOG.md §2b 从第一条 [ ] 的 EV-M 开始，每次只做一颗粒；识图搁置；DeepSeek-only；勿改代码勿 push。
```

---

## 2c. Mimir 工业级自学习轨（EV-L* · 防再发 · 积累经验）

> **目的**：对标工业级框架（CI 门禁、就绪探针、fail-closed、postmortem、契约测试、SRE runbook），让 Mimir 在**只写文档**的迭代里沉淀可复习经验，降低「再拆 mixin → NameError → TRUNCATE」类事故。  
> **沉淀真源**：`docs/MIMIR_EV_L_INDUSTRIAL_LEARNING.md`（每颗粒填对应 §，用文内模板）。  
> **与 §2b 关系**：§2b **冒烟验真**；§2c **总结、门禁、runbook**。可并行：**每完成 2 个 EV-M → 做 1 个 EV-L**；§2b 已基本完成时 **直接从 EV-L01 连续做**。

| ID | 对标 | 做什么 | 完成标准 | 状态 |
|----|------|--------|----------|------|
|| **EV-L01** | 三道门 | 读 `DEVELOPMENT_NORTH_STAR.md` §2–§5 | Playbook **§1** 有 5 条守门员自检 | [x] 2026-05-20 |
|| **EV-L02** | Postmortem | 读 `MIMIR_INCIDENT_IR-20260520.md` | Playbook **§2** 教训+防再发各 ≥2 条 | [x] 2026-05-20 |
|| **EV-L03** | CI 门禁 | tier0 / Ralph 3 连跑策略 | Playbook **§3** 写清触发条件 | [x] 2026-05-20 |
|| **EV-L04** | 契约烟测 | mixin import 测试与 Gate1 | Playbook **§4** 列 3 个测试名+何时跑 | [x] 2026-05-20 |
|| **EV-L05** | Fail-closed | `recovery_mixin` 护栏 | Playbook **§5** 区分代码错误 vs 溢出 | [x] 2026-05-20 |
|| **EV-L06** | 告警信号 | IR 日志签名 | Playbook **§6** ≥3 条红警 `grep -E` | [x] 2026-05-20 |
|| **EV-L07** | Parity | `ralph_parity_contract_v1` 摘 3 面 | Playbook **§7** 行为句+验证方式 | [x] 2026-05-20 |
|| **EV-L08** | 单写者 ADR | `adr/001-persistent-single-writer` | Playbook **§8** Mimir 禁提交 persistent 理由 | [x] 2026-05-20 |
|| **EV-L09** | Runbook | `OPERATIONS_GATEWAY` + 硬重启脚本 | Playbook **§9** 五步 SOP 卡片 | [x] 2026-05-20 |
|| **EV-L10** | Readiness | 对标 K8s 就绪探针 | Playbook **§10** ≥8 条重构后 checkbox | [x] 2026-05-20 |
|| **EV-L11** | 升级矩阵 | Mimir vs Cursor 分工 | Playbook **§11** 表格 ≥5 行 | [x] 2026-05-20 |
|| **EV-L12** | 真进化 | evolution / simulated | Playbook **§12** 真/伪进化各 1 例 | [x] 2026-05-20 |
|| **EV-L13** | 可观测债 | 结合 EV-M08 | Playbook **§13** + ISSUES ≤1 条（E-006） | [x] 2026-05-20 |
|| **EV-L14** | 索引 | 汇总 §1–§13 | Playbook **§14** 目录+复习节奏；飞书 **学习轨完成包** | [x] 2026-05-20 |

**执行约束**

- 每轮 **只做一个 EV-L**；只编辑 `MIMIR_EV_L_INDUSTRIAL_LEARNING.md` 对应节 + 本表勾 `[x]`。  
- **禁止**：为「学习」去改 agent/gateway；禁止填 d5 假进化存根。  
- **鼓励**：引用本次 EV-M01～11 的 grep 数字（TRUNCATE=19、deepseek、CLI_CONFIG 等）写入 Playbook，形成**你自己的**证据库。

**Mimir 每轮必读**：`docs/MIMIR_LIU_CURSOR_BRIDGE.md` + 本表 §2b/§2c（飞书直接读仓库，不经 OpenClaw）

**Mimir 切换一句（§2b 收尾后）**

```text
先 Read docs/MIMIR_LIU_CURSOR_BRIDGE.md，在 §4 签收表追加一行。
§2c 从 EV-L01 起，每次一颗粒写入 docs/MIMIR_EV_L_INDUSTRIAL_LEARNING.md；识图搁置；勿改代码勿 push。
```

---

## 3. gstack 审计阶段总览（d1–d7）

| 阶段 | 范围 | 报告分 | 债务类型 | Mimir 历史 | 工程状态 |
|------|------|--------|----------|------------|----------|
| **d1** | 飞书适配器 | ~6/10 | 通道/token | ✅ 验证+ISSUES；P2-1/1b 已合 | P0 在 `341c1fd`/`2b414d3` |
| **d2** | 上下文/C1/压缩 | ~6/10 | 上下文链 | ✅ 压缩链 cd6b71d；孤儿 tool PR#4 | Agent P0 `2b414d3` |
| **d3** | Gateway 框架 | ~5–6/10 | GOD class | ✅ 十条多项验证 | P0 ✅；**E-002/E-003 committed** |
| **d4** | Agent 核心循环 | 6/10 | 质量债 | 仅冒烟 M4；**不写代码** | P0-0~3 ✅；**E-003 committed** |
| **d5** | 自修/进化 | 4.5/10 | 空壳债 | 只读 | 未启动 |
| **d6** | 可观测性 | 5.5/10 | 集成债 | 只读 | 未启动 |
| **d7** | CLI 双轨 | 4/10 | 双轨债 | 只读 | 未启动；**d7 窗进行中** |

---

## 4. Mimir 可执行（轨道 A — 与统一队列 M-* 对齐）

> 计划：`docs/plans/2026-05-19_stability_sprint.md` · 十条：`docs/GATEWAY_STABILITY_BACKLOG.md`

| # | 统一 ID | 任务 | 状态（2026-05-20） |
|---|---------|------|-------------------|
| M1 | — | 重启 gateway | [x] IR Phase 3：硬重启 + pgrep + 飞书 tool；Mimir 续跑从 T-02 |
| M2 | M-002 | 飞书发图（识图搁置） | [x] deferred — EV-VISION-DEFER |
| M3 | M-003 | 空表头表 | [x] deferred — CLOSE-3 |
| M4 | — | 触发 tool | [x] |
| M5 | M-005 | OPENROUTER | [x] N/A DeepSeek-only |
| M6 | — | ISSUES #1/#2 | [x] |
| M7 | M-007 | Gateway 十条文档 | [x] |
| M8 | M-008 | push | [x] 2026-05-20 |

### Mimir 回报模板

```text
Mimir 冒烟回报
- gateway PID / 启动时间:
- M2 发图: 通过/失败 + grep 最后 5 行
- M3 表头: 通过/失败
- M4 tool: 通过/失败
- M5 OPENROUTER: N/A（DeepSeek-only）或 有/无
- 未完成项:
```

---

## 5. 外部检测（刘哥跑脚本 · Mimir 更新状态）

| 模块 | 检测项 | 状态 |
|------|--------|------|
| A Gateway | 进程/WS/Token | [x] IR 后硬重启 + tier0；Mimir T-02 可再签字 |
| B 飞书 | 心跳/收图/卡片/tool | ✅ 23:00 后多次 send success |
| C Agent | 崩溃/孤儿/错误率 | ✅ |
| D 数据 | persistent/日志/胶囊 | ✅（index 已补 P4-1） |

脚本目录：`scripts/detection/`（待建则记 ISSUES）

---

## 6. 工程明细（Cursor — 按审计阶段）

> **首行约定**：§6 内 **d5 / d6 未勾项**（如 D5-1、D5-3、D6-1～3）= **Phase 2 候选**，非 Phase 1.5 Active；勿与新窗 §2 混读。

### d1 — 飞书 · [x] P0 合 main

- 报告：`d1-audit-report.html`
- 代码：`341c1fd`、`2b414d3`、P2-1 / P2-1b（`43cbd3a` 等）

### d2 — 上下文 · [x] P0 合 main

- 报告：`d2-audit-report.html`
- 代码：Context 压缩 `cd6b71d`；孤儿 tool PR#4；`2b414d3`

### d3 — Gateway

- 报告：`d3-audit-report.html`
- P0 Sprint1–2：**[x]**（`393214e` 等）
- **D3-SPLIT**：E-001 ✅；**E-002** ✅ committed

### d4 — Agent 核心循环

- 报告：`d4-audit-report.html`
- P0-0~3：**[x]** `1bb652b`
- **P0-4 mixin**：**[x]** → **E-003** committed
- P1/P2：见 wiki，未排进统一队列（按需单独立项）

### d5 — 自修/进化 · 已收口

| ID | 任务 | 状态 |
|----|------|------|
| D5-0 | Recorder 按 session 隔离 | [x] E-007 |
| D5-0b | skill 路径白名单 | [x] E-007 |
| D5-1 | `simulated: true` | [x] 2026-05-25 · IEVO-01 |
| D5-2 | 单通路 FIX 写 SKILL | [x] E-009 |
| D5-3 | 测试 | [x] 2026-05-25 · IEVO-02 |
| D5-ADR | 双架构决策（仅 ADR） | [x] 2026-05-31 · 刘哥签收 · [`adr/008-evolution-canonical-path.md`](./adr/008-evolution-canonical-path.md) |

### d6 — 可观测性 · 未启动

| ID | 任务 | 状态 |
|----|------|------|
| D6-0a | insights SQL `TOOL_CALL` | [x] session_tracker.tool_calls + pipeline |
| D6-0b | monitor 阈值 + status | [x] agent/monitor.py + monitor_alerts.json |
| D6-0c | health.register | [x] `/health` 含 agent + agent_error_rate |
| D6-0d | RateLimitTracker Lock | [x] E-006 batch |
| D6-1 | trajectory/recorder SoT ADR | [x] 2026-05-25 · IEVO-03 · ADR-005 |
| D6-2 | ObservabilityBus（可选） | [x] 2026-05-26 · ADR-007 defer（OBS-B1-01） |
| D6-3 | 测试 | [x] 2026-05-25 · IEVO-05 |

### d7 — CLI 双轨 · d7 窗进行中

| ID | 任务 | 状态 |
|----|------|------|
| D7-0a | `CLI_CONFIG` | [x] E-004 2026-05-23 |
| D7-0b | chat 解耦 | [x] E-005 2026-05-23 |
| D7-1 | 单入口文档 | [x] E-005 2026-05-23 |
| D7-2 | 删 cli.py 等 | [x] E-008：cli.py 薄 shim + 删 cli_part*/cli_cron |
| D7-3 | gateway/config/chat 测试 | [x] E-008：`tests/test_mimir_cli_smoke.py` 等 |

**核实摘要**：`CLI_CONFIG` ImportError 已复现；`cmd_chat`→`cli.main`（~763 行）；mimir_cli 零 pytest — **可信**。

---

## 7. 主线历史待办（#1–#8，已基本收口）

1. [x] memory 工具冒烟 — 2026-05-17  
2. [x] persistent.json 截断 — Session 73 + skill_curator 防护  
3. [x] 胶囊迁移 120 .md→.html — 2026-05-19  
4. [x] Context 压缩链 — cd6b71d  
5. [x] P2-1 飞书收图 token — 2026-05-19  
6. [x] P2-2 空表头 `—` — PR#5  
7. [x] P3-0 persistent ADR — `docs/adr/001-persistent-single-writer.md`  
8. [x] P4-1 memory index + wiki symlink — 2026-05-20  

---

## 8. 工程 backlog（非 d 序号 · 勿交给 Mimir）

| 项 | 说明 |
|----|------|
| WebSocket 推理阻塞心跳 | gstack P0 |
| 自修回滚护栏 | gstack P0 |
| P3-0 单写者 **实现** | ADR 已有，代码未做 |
| Gateway #1/#4/#5/#10 等 | `GATEWAY_STABILITY_BACKLOG.md` |
| **P3-CROSS-SESSION-RETRIEVAL** | 🔮 跨会话知识检索方案调研。背景：persistent.json（~12KB）全量注入 vs sessions.db（8MB+）只按需查询 → 缺少「自动按需检索相关历史」的机制。方向：调研 Hermes/OpenClaw 原版注入策略、OpenSpaces/chromadb 语义检索（关联 #32 P2-LONG-SEM）、分层注入（核心全量 + 相关 Top-N + RAG）。等 P0-LONG-CLEARANCE 全部清完后启动。 |

---

## 9. 续跑（2026-05-25）

- **Phase 1.5** ✅：E-001～E-012 + intent-action guard；**tier0 245+2**；识图 **EV-VISION-DEFER**。
- **真源**：`~/src/MimirAether` · `MIMIR_AETHER_HOME=~/.mimiraether` · 必读 `MAINLINE_STATUS.md` / `MIMIR_ISSUES.md`（Active≤3）/ `AGENTS.md`。
- **§2 工程队列**：只读，勿再取「E-004 / T-02 / 181+2」。
- **Phase 0**：**14/14** [x]（2026-05-24）— 真源 [`MIMIR_PHASE0_QUEUE.md`](./MIMIR_PHASE0_QUEUE.md)。
- **智商/进化方向真源**：[`MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md) · Mimir 队列 **§15** · ISSUES **#12**（锚点，非 P0）。
- **当前执行源**：**§19 主队列** — 工程 **§19.1** 第一条 `[ ]`（与 §18.2 同序）；长期波次见 superpowers 主计划。§15 Wave 8 [x] · §18.1 Wave 9 [x]。
- **勿**：提交 `data/persistent.json`；重做 E-001～E-012。

### 9.1 未完成项盘点（2026-05-27）

| 桶 | 数量 | 说明 |
|----|------|------|
| **§13.1 母任务** | **0** Active | `P0-LONG-CLEARANCE` **全子阶段 [x]** |
| **§11 长任务** | **0** Active | **`P2-LONG-SEM`** [x] · **Wave 7 IQ-EVO** [x] |
| **§15 下一粒** | **0** Active | Wave 8 [x] |
| **§19 工程轨** | **见 §19.1** | **唯一取任务入口**（§18.2 为明细真源） |
| **§19 拍板轨** | **4** | ADR-002 / 世界模型 / rubric 5.5 / D5-ADR |
| **§19 运维轨** | **1+** | CLR-B-FEISHU + Gateway 十条余债 |
| **§6 Phase 2 候选** | **0** | D5-ADR → [x] ADR-008 |
| **§8 工程 icebox** | **4** 条 | 已迁入 **§19.4** |
| **Gateway 十条** | **~1** 运维 | #9 代码 [x]；**CLR-B** 飞书复验 deferred |
| **GitHub open** | **2** | **#21 #22** icebox（2026-05-27 已 refresh comment；**#32 #34 #35 closed**） |
| **Active P0 GH** | **0** | — |
| **搁置** | **1** | EV-VISION-DEFER（识图） |

**对策**：智商/进化认 **§15 + bridge**；GH 只跟踪 bug/icebox/里程碑。**勿**为 IQ-EVO 粒重复开 issue。

---

## 10. WIP 快照（2026-05-25 · 双轨）

- **Phase 1.5** ✅ E-001～E-012 + intent-action guard；tier0 **245+2**  
- **Phase 0** ✅ 14/14  
- **母任务** → **§13.1 `P0-LONG-CLEARANCE`**（~6–8 周）；当前子阶段 **A** [~]  
- **写入 Active** → A 尾 W0-06；**B** 刘哥 T-03/T-04  
- **TRUNCATE** **P0**（全量 63 / 24日 33）→ **CLR-C STAB-04** 优先  
- **Gateway** PID **90544** · /health ok  

---

## 11. Phase 1 长任务队列（2026-05-24）

> **一条长任务**：`P1-LONG-MEM` — **Memory 检索可生产化**（EV-A03 审计 → 可运行、可测、可接线）。  
> **执行法**：每次只勾 **一条**子项；子项全部 `[x]` 后，长任务结案，再开下一条长任务（见表末）。  
> **真源**：[`phase0/memory-retrieval-baseline.md`](./phase0/memory-retrieval-baseline.md) · 基准 JSON [`phase0/memory-retrieval-benchmark-20260524.json`](./phase0/memory-retrieval-benchmark-20260524.json)

### P1-LONG-MEM — Memory 检索可生产化 **[x] 结案 2026-05-24**

> M01～M06 全部 `[x]`；main **`7f4b53d`** 起可生产化 `session_search`（回填、Gateway 增量、FTS/hybrid、persistent 对齐）。基准见 phase0 §4。

| ID | 任务 | 成功标准 | 状态 |
|----|------|----------|------|
| **P1-M01** | **回填 + 20-query 基准** — indexer、`backfill_sessions_search.py`、`run_memory_retrieval_benchmark.py`；LIKE 多词 AND | 本机 `sessions≥30`、`messages≥3000`；基准 JSON 存在；LIKE hit rate ≥50%（回填后实测 **60%**） | [x] 2026-05-24 · `6650327` |
| **P1-M02** | **合入 + M6** — commit 上述 tools/scripts/tests/docs；`record_m6_evolution.sh`；tier0 绿 | `./run_ralph_tier0.sh` PASS；`evolution_log.md` 一行 | [x] 2026-05-24 |
| **P1-M03** | **Gateway 增量索引** — `append_to_transcript` 同步写 `sessions_search.db`（+ 可选 FTS） | 新会话消息无需手工 backfill 即可被 `session_search` 命中；单测或 smoke | [x] 2026-05-24 · `027eaaf` |
| **P1-M04** | **FTS5 生产接线** — 修 hyphen token（`IR-20260520`）；`SESSION_SEARCH_BACKEND=fts5` 或 hybrid | 基准中 hyphen query 无 SQL 错；FTS hit rate ≥ LIKE 或文档说明取舍 | [x] 2026-05-24 |
| **P1-M05** | **persistent 路径一致** — `prompt_builder` cross_session 与 runtime home 对齐（EV-A03 分叉项） | grep/烟测：不再默认读 `{repo}/data/persistent.json` 当真源 | [x] 2026-05-24 |
| **P1-M06** | **长任务结案** — 更新 `MAINLINE_STATUS` + baseline §4；标记 `P1-LONG-MEM` [x] | 飞书/会话 3～5 行摘要 + 基准数字 | [x] 2026-05-24 |

**Cursor 新窗一句**

```text
Read docs/MIMIR_EXEC_BACKLOG.md §11；P1-LONG-MEM 已结案。工程下一条：P2-LONG-SEM（刘哥点名）或 §12 MW-D01（运维）；每次一颗粒；触达 agent/gateway/tools 后 tier0。
```

### 并行长任务（**非**默认取任务源 — 刘哥点名才开）

| ID | 主题 | 来源 | 状态 |
|----|------|------|------|
| **P1-LONG-GOD** | GOD 拆分 + 测试轨续建 | Phase 0 EV-P04、§9 原「GOD 拆分」 | [x] 2026-05-24 · #16→main；`router_mixin` ~38 行；见 `plans/P1-GOD-split-plan.md` |
| ~~**P1-LONG-OBS**~~ | — | — | → 升格 **§16 Horizon B1**（见下） |
| **P1-LONG-EVO** | d5 余债 D5-1/3、真进化 | §6、Unified Plan | [ ] Phase 2 候选 |
| **P2-LONG-SEM** | Memory **语义化**（chromadb + 检索策略） | Unified Plan Phase 2 | [x] **结案** 2026-05-19 · [`p2-long-sem-closeout.md`](./phase0/p2-long-sem-closeout.md) · GH **#32** |
| **P2-LONG-IQEVO** | 智商/进化 Wave 1–3 | [`MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md) | Wave 1–3 **[x]**（§15 · IQ-EVO-14 = 4.3 documented exception） |
| **Horizon B1** | **`P1-LONG-OBS`** · d6 可观测 | **§16** | **[x] 2026-05-26** OBS-B1-01～03 |

**Semantic 检索**：**P2-LONG-SEM** 已结案（SEM-01～07）；生产默认 **`hybrid`**（IQ-EVO-11）；可选 **`semantic_hybrid`** + `MIMIR_EMBED_MODEL` 见 ADR-006 · [`MIMIR_OPS_PANEL.md`](./ops/MIMIR_OPS_PANEL.md) §7。

---

## 12. Mimir ISSUES 写入轨道（MW-* · 运维长任务）

> **真源**：[`docs/MIMIR_ISSUES_WRITE_PLAN.md`](./MIMIR_ISSUES_WRITE_PLAN.md)（安全边界 + **§6A 提示词**）。  
> **刘哥出门**：只认 **§12.1** 第一条 `[ ]`；**禁止** push / 改代码。

### 12.0 回填（已完成）

| ID | 颗粒 | 状态 |
|----|------|------|
| MW-001～007 | bridge / backlog / D17 / GH #19 / ISSUES | [x] 2026-05-24 |

---

### 12.1 刘哥出门 · Mimir 顺序队列（2026-05-24）

> **每轮一条**。做完：`[x]` + 日期 + bridge §4 一行 + 飞书 3 行（可选）。卡住 → `MIMIR_ISSUES.md` 一条 + **停手**。

| ID | 做什么 | 命令 / 动作 | 成功标准 | 状态 |
|----|--------|-------------|----------|------|
| **MW-D01** | **Gateway 健康** | `curl -s http://127.0.0.1:18999/health \| head -c200`；`pgrep -af 'gateway/run.py'` | status/gateway/agent ok；有 PID | [x] 2026-05-25 · PID **135797** · /health ok |
| **MW-D02** | **TRUNCATE 基线** | `grep -c 'Level 3 TRUNCATE' <since Gateway running>` via `mimir_health_check.sh --quick` R4 | **≤10 since start**；全量历史非 P0 | **[!]** 全量 63 历史；**since start=0**（2026-05-25 重启后） |
| **MW-D03** | **ERROR 扫** | `grep ERROR ~/.mimiraether/logs/agent.log \| tail -20` | 列 top3 主题；无新 P0 则 §4 记「无新 P0」 | [x] 2026-05-25 · recovery 测例 ImportError/AttributeError；Feishu Not connected |
| **MW-D04** | **飞书卡片 log** | `grep -E '230099\|200907' ~/.mimiraether/logs/agent.log ~/.mimiraether/logs/gateway.log 2>/dev/null \| tail -10` | 有/无新 230099；更新 `GATEWAY_STABILITY_BACKLOG` #9 一句 | [x] 2026-05-25 · 末条 **2026-05-17**；无新 230099 |
| **MW-D05** | **session_search 烟测** | `cd ~/src/MimirAether && MIMIR_AETHER_HOME=~/.mimiraether SESSION_SEARCH_BACKEND=hybrid python3 -c "from tools.session_search_tool import session_search; print(session_search('IR-20260520', limit=3))"` | 无异常；有 hit 或空结果均可；**无 SQL 错** | [x] 2026-05-25 · hybrid 3 hits |
| **MW-D06** | **persistent 路径** | `MIMIR_AETHER_HOME=~/.mimiraether python3 -c "from agent.prompt_builder import _build_cross_session_context; print(_build_cross_session_context()[:200])"` | 输出含 cross-session 或空；**不**读 `{repo}/data/persistent.json` | [x] 2026-05-25 · cross-session 来自 runtime home |
| **MW-D07** | **health_check 脚本** | `~/src/MimirAether/scripts/mimir_health_check.sh --quick` | exit 0 或记录失败行 | [x] 2026-05-25 · **READY**；R3 重试 + restart health poll |
| **MW-D08** | **Gateway 十条刷新** | Read `GATEWAY_STABILITY_BACKLOG.md`；#2 #9 各 grep 今日 log 一行 | 状态列日期 → 今天；无改码 | [x] 2026-05-25 |
| **MW-D09** | **MAINLINE 轻刷新** | Read `MAINLINE_STATUS.md`；确认 P1-LONG-MEM 结案与 tier0 **245+2** | 最近更新=今天；无矛盾 | [x] 2026-05-25 |
| **MW-D10** | **GH 只读对账** | `gh issue list --state open --limit 10` | #17/#18/#19 应 closed；#20–22 icebox → bridge §4「对账 ok」 | [x] 2026-05-25 · open **10**；#2/#12/#13/#31 已关 |
| **MW-D11** | **出门汇总** | 飞书发 **MW-D01～D10 勾选表** + TRUNCATE 数 + Gateway PID | 刘哥一眼能看；勾 `[x]` MW-D11 | [x] 2026-05-25 · bridge §5 勾选表 |

**人工门（刘哥回来再做，Mimir 只提醒）**

| ID | 内容 | 状态 |
|----|------|------|
| **MW-H01** | 飞书 T-03 空表头 | [x] 2026-05-25 刘哥复验 pass |
| **MW-H02** | 飞书 T-04 双按钮 | [x] 2026-05-25 刘哥复验 pass |
| **MW-H03** | 恢复识图 / OpenRouter | [~] EV-VISION-DEFER |

**Mimir 新窗一句（出门版）**

```text
Read docs/MIMIR_ZERO_DEBT_MASTERPLAN.md §3 + MIMIR_EXEC_BACKLOG.md §13（优先）或 §12.1 MW-D*。
MIMIR_AETHER_HOME=~/.mimiraether。只做 §13 或 §12.1 第一条 [ ] 一颗粒。
更新 bridge §4 一行。禁止 push；禁止改 agent/gateway/tools/mimir_cli。
回报：ID + 结果 + 下一粒。
```

---

## 13. 零技术债执行源（2026-05-25 · **取代 §11 取任务**）

> **真源**：[`docs/MIMIR_ZERO_DEBT_MASTERPLAN.md`](./MIMIR_ZERO_DEBT_MASTERPLAN.md)（盘点 + 四波 + **§0 Done 八条**）。  
> **规则**：清空完成前 **只认 §13.1 第一条 `[ ]` 子阶段**；子阶段内只认 **该段第一条 `[ ]` 子项**。§11/§12/§8/§6 **只读归档**。

---

### 13.1 母任务 — **`P0-LONG-CLEARANCE`**（清空主线 · ~6–8 周）

> **完成定义**：masterplan **§0 D1–D8 全绿** → 宣告清空，再开 Horizon（`P2-LONG-SEM` / Phase 3 智商）。  
> **禁止**：与母任务 **并行** 开 §11 `P2-LONG-SEM` 或 Unified Plan Phase 3 代码。

| 子阶段 | 长任务 ID | Owner | 结案判据（摘要） | 状态 |
|--------|-----------|-------|------------------|------|
| **A** | **W0-LONG-HYGIENE** | Mimir + Cursor | W0-01～06 全 `[x]`；GH 无重复；TRUNCATE **登记** → C | **[x] 2026-05-25** |
| **B** | **W1-LONG-SMOKE** | 刘哥 + Mimir | T-03/T-04；Gateway #9 **已验证**；**D6** | **[x] 2026-05-25** |
| **C** | **P2-LONG-STAB** | Cursor | STAB-01～07；Gateway 十条无「移交工程」；**#10 TRUNCATE 回落**；GH #25–30 关 | **[x] 2026-05-25** |
| **D** | **P2-LONG-INDEP** | Cursor | IND-01～06；**D7**；GH #20 关 | **[x] 2026-05-25**（刘哥 §8.3 签收） |
| **E** | **P2-LONG-IEVO** | Cursor | IEVO-01～06；**D8**；GH #21/#22 部分关 | **[x] 2026-05-25** |
| **✓** | **CLEARANCE-DONE** | 刘哥 sign-off | §0 **8/8**；MAINLINE 刷新；Horizon 二选一 | **[x] 2026-05-25** · [`p0-long-clearance-done.md`](./phase0/p0-long-clearance-done.md) |

**Horizon（清空后）**：`P2-LONG-SEM` · ADR-002 · Unified Plan Phase 3/4 — **刘哥拍板**，不纳入本母任务。

#### A — W0-LONG-HYGIENE（§13.0 明细）

| ID | 任务 | Owner | 状态 |
|----|------|-------|------|
| **W0-01** | MW-D01–D10（§12.1） | Mimir | [x] 2026-05-25 · D02 since-start=0；D07 health READY |
| **W0-02** | GH 关 #2 #12 #13 #31 | Cursor | [x] 2026-05-25 |
| **W0-03** | GH 标签 #20–32 | Cursor | [x] 2026-05-25 |
| **W0-04** | §9/§10/MAINLINE → §13 | Cursor | [x] 2026-05-25 |
| **W0-05** | MIMIR_ISSUES Active 复核 | Mimir | [x] 2026-05-25 · #10 active P0 |
| **W0-06** | MW-D11 汇总 | Mimir | [x] 2026-05-25 · bridge §5 勾选表 |

**A 结案**：W0-06 `[x]` 后，子阶段 A → `[x]`（D02 不阻塞 A 结案，**移交 C/STAB-04**）。

#### B — W1-LONG-SMOKE

| ID | 任务 | 成功标准 | 状态 |
|----|------|----------|------|
| **W1-01** | 飞书 **T-03** 空表头 | 无 `230099` · `mimir_prod_smoke.md` | [x] 2026-05-25 刘哥 |
| **W1-02** | 飞书 **T-04** 双按钮 | 两按钮可见 | [x] 2026-05-25 刘哥 |
| **W1-03** | Gateway **#9** → 已验证 | `GATEWAY_STABILITY_BACKLOG` 状态列 | [x] 2026-05-25 |
| **W1-04** | MW-H01/H02 关或 wontfix | §12.1 人工门表 | [x] 2026-05-25 |

#### C — P2-LONG-STAB（**执行顺序：STAB-04 优先**）

| ID | 任务 | GH | 成功标准 | 状态 |
|----|------|-----|----------|------|
| **STAB-04** | **TRUNCATE P0** + Agent 栈（`recovery` / `run.py`） | #30 | 无双截断；since-start TRUNCATE 可控；gateway drain 不 Executor 崩溃；tier0 + M6 | [x] 2026-05-25 · tier0 **246+2** |
| **STAB-01** | Watchdog 超时 / 长推理 / WS 同源 | #27 #25 | 7 日无超时或降级策略 documented | [x] 2026-05-25 · WS 非阻塞 + activity 心跳 |
| **STAB-02** | Event loop closed | #28 | 单测或 gateway 回归 | [x] 2026-05-25 · run_async + shutdown cleanup |
| **STAB-03** | ToolGuard 相对路径 | #29 | path 单测；tier0 | [x] 2026-05-25 · resolve_path_for_guard + 7 tests |
| **STAB-05** | 自修回滚护栏 | #26 | 回滚路径 + 测试 | [x] 2026-05-25 · evolution_rollback + 5 tests |
| **STAB-06** | WebSocket 推理阻塞心跳 | #25 | 与 STAB-01 同 PR 或子 PR | [x] 2026-05-25 · 同 STAB-01 |
| **STAB-07** | **STAB 结案** | #25–30 | Gateway 十条无「移交工程」 | [x] 2026-05-25 · backlog 刷新 + GH #25–30 closed |

#### D — P2-LONG-INDEP

| ID | 任务 | 成功标准 | 状态 |
|----|------|----------|------|
| **IND-01** | ADR-003 legacy env 别名表 | `docs/adr/003-runtime-env-aliases.md` | [x] 2026-05-25 |
| **IND-02** | 新代码仅 `get_mimir_home()`；grep 门禁 | tier0 + advisory | [x] 2026-05-25 |
| **IND-03** | `MIMIR_SESSION_DB`（保留旧名读） | 单测 + path-contract | [x] 2026-05-25 |
| **IND-04** | mimicore 子模块 `.openclaw` 边界 ADR | 不再复发 | [x] 2026-05-25 |
| **IND-05** | P3-0 单写者实现 | GH #20 close | [x] 2026-05-25 |
| **IND-06** | OPENCLAW_BOUNDARY §8 + MAINLINE | 刘哥 sign-off | [x] 2026-05-25 · 刘哥 §8.3 签收 |

#### E — P2-LONG-IEVO

| ID | 任务 | 成功标准 | 状态 |
|----|------|----------|------|
| **IEVO-01** | D5-1 禁 `simulated` 生产路径 | grep + 单测；GH #21 部分关 | [x] 2026-05-25 |
| **IEVO-02** | D5-3 evolution pytest | tier0 或 wide 绿 | [x] 2026-05-25 · tier0 **306+2** |
| **IEVO-03** | D6-1 Observability SoT ADR | GH #22 部分关 | [x] 2026-05-25 · ADR-005 |
| **IEVO-04** | `scripts/run_evolution_eval.sh` | 一次绿 run + 基线 JSON | [x] 2026-05-25 |
| **IEVO-05** | D6-3 monitor/insights 回归测 | 单测 ≥3 | [x] 2026-05-25 |
| **IEVO-06** | IEVO 结案 + Phase ∞ 续勾 | MAINLINE 绿 | [x] 2026-05-25 · `p2-long-iev0-closeout.md` |

---

### 13.0 进度与 Done 对照（2026-05-25）

| masterplan §0 | 进度 |
|---------------|------|
| D1 GH ≤6 | ✅ **2 open**（#21 #22 icebox · #32/#34/#35 closed 2026-05-27） |
| D2 Active 无 P0 | ✅ Active **2**（#3 deferred · #10 monitoring） |
| D3 Gateway 十条 | ✅ **STAB-07**（2026-05-25） |
| D4 §13 无 `[ ]` | ✅ **P0-LONG-CLEARANCE** 全子阶段 `[x]` |
| D5 tier0 | ✅ **326+2** |
| D6 飞书 smoke | ✅ T-03/T-04 + R5 tool 往返（2026-05-25 刘哥） |
| D7 路径独立 | ✅ **IND-01～06**（§8 独立宣言 · 刘哥签收 2026-05-25） |
| D8 工业进化 MVP | ✅ **CLR-E**（IEVO-01～06） |

**整体清空（D1–D8）**：✅ **8/8**（2026-05-25 · [`p0-long-clearance-done.md`](./phase0/p0-long-clearance-done.md)）

**Cursor 新窗一句**

```text
Read docs/MIMIR_ZERO_DEBT_MASTERPLAN.md §7 + docs/phase0/p2-long-sem-closeout.md。
Horizon A SEM 波已 [x]；勿默认开 ADR-002 / Phase 3 — 待刘哥拍板下一条 Horizon。
触达 agent/gateway/tools 后 ./run_ralph_tier0.sh + evolution_log。
```

**Mimir 新窗一句**

```text
Read docs/adr/006-semantic-memory-chromadb.md + backlog §14（工程 SEM-* 由 Cursor 做）。
MIMIR_AETHER_HOME=~/.mimiraether。运维：MW-D01～D11 / health / TRUNCATE since-start；禁止 push 工程分支。
更新 bridge §4 一行。回报：ID + 结果 + 下一粒。
```

---

## 14. Horizon 执行源 — **`P2-LONG-SEM`**（2026-05-25 · 刘哥 **Horizon A**）

> **真源**：[`docs/adr/006-semantic-memory-chromadb.md`](./adr/006-semantic-memory-chromadb.md) · GH **#32** · Unified Plan §4 冲突 2（AC3+AC6 合并）  
> **规则**：只认 **§14 第一条 `[ ]` 子项**；每粒 `./run_ralph_tier0.sh`；**禁止**并行 ADR-002 代码或 Phase 3 智商。  
> **基准**：[`phase0/memory-retrieval-baseline.md`](./phase0/memory-retrieval-baseline.md) · IEVO-04 eval 脚本（LIKE/FTS 门保持至 SEM-04）。

| ID | 任务 | 成功标准 | 状态 |
|----|------|----------|------|
| **SEM-01** | ADR-006 + path-contract § semantic | ADR Proposed + path 表 | [x] 2026-05-25 |
| **SEM-02** | Chroma 持久化 + backfill indexer | `$MIMIR_AETHER_HOME/data/chroma_sessions/` 可查询；脚本 idempotent | [x] 2026-05-19 |
| **SEM-03** | `SESSION_SEARCH_BACKEND=semantic\|semantic_hybrid` | `session_search_tool` + 单测 | [x] 2026-05-19 |
| **SEM-04** | 基准 + eval 扩展 semantic 腿 | benchmark JSON 含 `semantic_hit_rate`；compare 逻辑 | [x] 2026-05-19 |
| **SEM-05** | tier0 回归 ≥3 | contract + smoke | [x] 2026-05-19 |
| **SEM-06** | 结案 + MAINLINE + GH #32 | 语义 query 子集 ≥ LIKE 或 documented 例外 | [x] 2026-05-19 |
| **SEM-07** | **生产硬化**：冻结 semantic 基线 + IEVO-04 回归门 + 运维文档（IQ-EVO-11 增量已合） | Cursor | `memory-retrieval-benchmark-20260526.json`；eval 默认新基线 | [x] 2026-05-26 |

**§14 波次状态**：SEM-01～07 **全 [x]** · 结案 [`p2-long-sem-closeout.md`](./phase0/p2-long-sem-closeout.md) · GH **#32** **closed** 2026-05-27。

**Cursor 新窗一句**

```text
Read docs/phase0/p2-long-sem-closeout.md + MIMIR_EXEC_BACKLOG.md §14。
Horizon A **P2-LONG-SEM** 已结案；勿默认开下一条 Horizon（ADR-002 / Phase 3 等）。
维护 tier0 / eval 回归时 MIMIR_AETHER_HOME=~/.mimiraether。
```

---

## 15. 智商与进化方向 — **`P2-LONG-IQEVO`**（2026-05-25 · 刘哥定稿）

> **真源**：[`MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md)（自知 + 协作 + 四阶段）  
> **规则**：**Mimir** 只认 **§15 第一条 `[ ]`**；回报用方向文档 **§3.3 模板**；**禁止**无 §3.2 证据宣称「进化/变聪明」。  
> **与 §14 关系**：§14 做 **SEM 工程**（Cursor）；§15 做 **方向签收、提案、冒烟证据**（Mimir）。同一阶段可并行，但 **Mimir 不得抢改 SEM 代码**（除非 bridge §1 授权自研）。

| ID | 任务 | Owner | 成功标准 | 状态 |
|----|------|-------|----------|------|
| **IQ-EVO-00** | **Read 方向真源** + bridge §4 签收一行 | Mimir | 已读 §0～§4；§4 含「已读方向文档」 | [x] 2026-05-25 |
| **IQ-EVO-01** | **阶段1·回忆**：复跑 20-query 基准并记录 JSON 路径 | Mimir | 贴 `memory-retrieval-benchmark-*.json` 或 hit rate 三行；DB 非空 smoke | [x] 2026-05-25 |
| **IQ-EVO-02** | **阶段1·回忆**：飞书 1 条「需查历史」场景 + log 证明调用了 `session_search` | Mimir+刘哥 | log 有 tool 名；或 ISSUES 记 fail | [x] 2026-05-25 |
| **IQ-EVO-03** | **阶段2·进化**：提案 — staging 开 `MIMIR_AUTO_ANALYSIS` 风险与步骤 | Mimir → 刘哥 | `docs/proposals/iq-evo-auto-analysis.md` 或 bridge 提案轨 | [x] 2026-05-25 |
| **IQ-EVO-04** | **阶段2·进化**：跑 `run_evolution_eval.sh` 贴摘要 | Mimir | 命令 exit 0 + 输出路径；非 simulated | [x] 2026-05-25 |
| **IQ-EVO-05** | **阶段3·衔接**：SEM-04 后复填 iq-scoring 表（只读对比） | Mimir | 更新方向文档 §1.1 表或 phase0 rubric 备注 | [x] 2026-05-25 |
| **IQ-EVO-06** | **长任务结案** — §15 全 `[x]` + MAINLINE 一行 | Cursor | IQ≥5.5 或 documented 例外 + 进化 eval 周常约定 | [x] 2026-05-19 |

**§15 Wave 1 状态**：IQ-EVO-00～06 **全 [x]** · 结案 [`p2-long-iqevo-closeout.md`](./phase0/p2-long-iqevo-closeout.md) · IQ **3.9/10**（documented 例外；5.5 → Wave 2）。

### §15 Wave 2 — Horizon IQ-EVO（2026-05-19 · 刘哥「继续 Wave 2」）

| ID | 任务 | Owner | 成功标准 | 状态 |
|----|------|-------|----------|------|
| **IQ-EVO-07** | **`MIMIR_AUTO_ANALYSIS=1` 接入** `_close_pipeline`（fire-and-forget LLM + artifact） | Cursor | `agent/post_close_analysis.py` + tier0；staging `.env` 可选开 | [x] 2026-05-19 |
| **IQ-EVO-08** | **memory/skill nudge**（`MIMIR_*_NUDGE_INTERVAL` 默认 10） | Cursor | `conversation_nudges.py` + agent_loop 注入 | [x] 2026-05-19 |
| **IQ-EVO-09** | **ADR-002 注入切片** — 跨会话核心字段 + `MIMIR_CROSS_SESSION_MAX_CHARS` | Cursor | `prompt_builder._build_cross_session_context` 有 cap + objective | [x] 2026-05-19 |

**Wave 2 未纳入本波（待刘哥）**：Gateway Chroma **增量** upsert · 生产 `SESSION_SEARCH_BACKEND=hybrid` 默认 · `MIMIR_AUTO_EVOLVE=1` 自动改技能。

**Mimir 新窗一句（Wave 2 验收 · 刘哥 @ 时用）**

```text
Read docs/MIMIR_LIU_CURSOR_BRIDGE.md §1「IQ-EVO Wave 2 验收」+ p2-long-iqevo-closeout.md §Wave 2。
staging：MIMIR_AUTO_ANALYSIS=1，重启 Gateway；跑 analysis_artifacts 冒烟 + nudge log + run_evolution_eval。
回报 §3.3 + bridge §4；勿改 agent/gateway 代码。
```

**Cursor 新窗一句（Wave 1 结案后）**

```text
Read docs/phase0/p2-long-iqevo-closeout.md。
IQ-EVO Wave 1 [x]；勿默认开 AUTO_ANALYSIS/nudge/ADR-002 — 待刘哥拍板 Wave 2。
```

### §15 Wave 3 — 智商默认化（2026-05-26 · 刘哥拍板 · **先于 Horizon B1**）

> **Horizon B**：**B1 可观测** = 本表 **§16 `P1-LONG-OBS`**；**Wave 3 工程未绿前不开 B1**。

| ID | 任务 | Owner | 成功标准 | 状态 |
|----|------|-------|----------|------|
| **IQ-EVO-10** | **rubric 诚实复评**（Wave 2 后；**不**强行 ≥5.5） | Mimir | 更新 [`iq-scoring-rubric.md`](./phase0/iq-scoring-rubric.md)；写明距 5.5 差距；bridge §4 | [x] 2026-05-26 · 4.1/10（#3 +1.0 #10 +1.0）；距 5.5 差 1.4 |
| **IQ-EVO-11** | **`SESSION_SEARCH_BACKEND=hybrid` 生产默认** + Gateway **Chroma 增量** upsert | Cursor | tier0 + eval JSON；path-contract | [x] 2026-05-26 · hybrid 默认；`MIMIR_CHROMA_INCREMENTAL` 写路径 upsert；tier0 382+2 |
| **IQ-EVO-12** | prompt **先 `session_search` 再答**（硬约束/指引） | Cursor | 飞书 1 条 log 有 `session_search`；tier0 若触达 prompt | [x] 2026-05-26 · `SESSION_SEARCH_GUIDANCE` search-first MUST；contract wave3 |
| **IQ-EVO-13** | 生产 **`MIMIR_AUTO_ANALYSIS=1` 门闩**（文档化 rollout；仍 **不开** `AUTO_EVOLVE`） | Cursor | `.env` 契约 + ops 注记；7d artifact 样本路径 | [x] 2026-05-26 · `docs/ops/MIMIR_AUTO_ANALYSIS_ROLLOUT.md` + `list_analysis_artifacts.sh` |
| **IQ-EVO-14** | rubric **复评 #2**；是否关 ISSUES **#12** | Mimir | ≥5.5 或 **documented exception** 续期；bridge §4 | [x] 2026-05-26 · **4.3/10** documented exception（距 5.5 差 1.2）；#12 续期见 closeout |

**Mimir 新窗一句（Wave 3）**

```text
Read backlog §15 Wave 3 + bridge §1「刘哥拍板」。
本轮只做 IQ-EVO-10（诚实 rubric）；回报 §3.3 + bridge §4。勿开 Horizon B1。
```

**Cursor 新窗一句（Wave 3 工程）**

```text
Read backlog §15 Wave 3。刘哥序：先 Wave 3 再 Horizon B1。
在 IQ-EVO-10 Mimir 签收后做 IQ-EVO-11～13；tier0 + evolution_log；Horizon B1 勿并行。
```

### §15 Wave 4 — 学习闭环 · 只记录（2026-05-26 · 刘哥「开 IQ Wave 4」）

> **真源**：[`p2-long-iqevo-wave4.md`](./phase0/p2-long-iqevo-wave4.md) · Unified Plan 冲突 3 · **1a**（FeedbackCollector 只记录，**不改阈值**）  
> **规则**：每粒 `./run_ralph_tier0.sh`；**禁止** `MIMIR_AUTO_EVOLVE=1`；Wave 4 只记录（1a）。  
> **前置**：§17 AUTONOMY **[x]** · Wave 3 **[x]** · rubric **4.3/10**。

| ID | 任务 | Owner | 成功标准 | 状态 |
|----|------|-------|----------|------|
| **IQ-EVO-15** | Wave 4 **立案** + plan doc + bridge 拍板 | Cursor | `p2-long-iqevo-wave4.md` + 本表 | [x] 2026-05-26 |
| **IQ-EVO-16** | **FeedbackCollector** — `feedback_events.jsonl`（`MIMIR_FEEDBACK_COLLECTOR=1`） | Cursor | tool_failure + pipeline_close 事件；单测 | [x] 2026-05-26 |
| **IQ-EVO-17** | **tool_quality 只读注入** prompt（degraded 摘要） | Cursor | `build_tool_quality_guidance` + tier0 | [x] 2026-05-26 |
| **IQ-EVO-18** | **analysis artifact** → feedback 事件 | Cursor | `post_close_analysis` 接线 | [x] 2026-05-26 |
| **IQ-EVO-19** | rubric **复评 #3** + Wave 4 closeout | Mimir+刘哥 | ≥5.5 或 documented exception；bridge §4 | [x] 2026-05-26 · **4.5/10** exception |

**§15 Wave 4 状态**：**[x] 结案** · 生产 `MIMIR_FEEDBACK_COLLECTOR=1` · Gateway **PID 356976** · closeout [`p2-long-iqevo-wave4-closeout.md`](./phase0/p2-long-iqevo-wave4-closeout.md)

**Mimir 新窗一句（Wave 4 验收）**

```text
Read docs/phase0/p2-long-iqevo-wave4.md §Mimir smoke。
staging：MIMIR_FEEDBACK_COLLECTOR=1，重启 Gateway；触发 tool 失败 + 可选 AUTO_ANALYSIS 任务；
贴 feedback_events.jsonl 末行 + prompt 是否含 Tool quality signals。
回报 §3.3 + bridge §4「Wave 4 验收」。勿开 AUTO_EVOLVE。
```

**Cursor 新窗一句（Wave 4 工程）**

```text
Read backlog §15 Wave 4。实现 IQ-EVO-16～18；tier0 + evolution_log。
勿开 AUTO_EVOLVE / 勿改硬编码阈值。
```

### §15 Wave 5 — 有界自调参 · 1b（2026-05-26 · 刘哥「开 Wave 5」）

> **真源**：[`p2-long-iqevo-wave5.md`](./phase0/p2-long-iqevo-wave5.md) · Unified Plan 冲突 3 · **1b**  
> **规则**：每粒 `./run_ralph_tier0.sh`；**禁止** `MIMIR_AUTO_EVOLVE=1`；**禁止** 1c（DecisionRing/Compressor 全量学习）。  
> **前置**：Wave 4 **[x]** · `MIMIR_FEEDBACK_COLLECTOR=1` 生产。

| ID | 任务 | Owner | 成功标准 | 状态 |
|----|------|-------|----------|------|
| **IQ-EVO-20** | Wave 5 **立案** + plan + bridge | Cursor | `p2-long-iqevo-wave5.md` + 本表 | [x] 2026-05-26 |
| **IQ-EVO-21** | **ExperienceBuffer** — 汇总 `feedback_events.jsonl` | Cursor | `experience_buffer.py` + 单测 | [x] 2026-05-26 |
| **IQ-EVO-22** | **tuned_thresholds** 有界注册表 + JSON 持久化 | Cursor | Top-3 键 + clamp | [x] 2026-05-26 |
| **IQ-EVO-23** | **AutoTuner** — `MIMIR_AUTO_TUNER=1` + `tune_audit.jsonl` | Cursor | pipeline close 接线 | [x] 2026-05-26 |
| **IQ-EVO-24** | **消费方接线** — compressor / guard / tool_quality | Cursor | 三处读 override | [x] 2026-05-26 |
| **IQ-EVO-25** | tier0 + contract wave5 | Cursor | `test_horizon_iqevo_wave5.py` | [x] 2026-05-26 |
| **IQ-EVO-26** | rubric **复评 #4** + Wave 5 closeout | Cursor+Mimir | ≥5.5 或 documented exception | [x] 2026-05-26 · **4.7/10** |

**§15 Wave 5 状态**：**[x] 结案** · closeout [`p2-long-iqevo-wave5-closeout.md`](./phase0/p2-long-iqevo-wave5-closeout.md)

**Mimir 新窗一句（Wave 5 验收）**

```text
Read docs/phase0/p2-long-iqevo-wave5.md §Mimir smoke。
staging：MIMIR_AUTO_TUNER=1（保持 FEEDBACK_COLLECTOR=1）· 重启 Gateway；
制造 tool 失败 / degraded close → 检查 tuned_thresholds.json + tune_audit.jsonl。
回报 §3.3 + bridge §4。勿开 AUTO_EVOLVE。
```

**Cursor 新窗一句（Wave 5 工程）**

```text
Read backlog §15 Wave 5。IQ-EVO-21～25；tier0 + evolution_log。
有界 Top-3 only；勿开 AUTO_EVOLVE / 勿做 1c。
```

### §15 Wave 6 — 合格智能体（2026-05-26 · 颗粒方案 · bridge §1 已立案）

> **真源**：[`p2-long-iqevo-wave6-qualified-agent.md`](./phase0/p2-long-iqevo-wave6-qualified-agent.md)  
> **ISSUES**：仅 **#12** direction 锚点 — **勿**把下表拆进 Active（≤3 规则）  
> **前置**：Wave 5 IQ-EVO-20～26 **全 [x]**  
> **目标**：rubric **≥5.5** + §3.2 行为证据（非「能转发」）

| ID | 任务 | Owner | 成功标准 | 状态 |
|----|------|-------|----------|------|
| **IQ-EVO-27** | Wave 6 **立案** + plan + bridge 拍板行 | Cursor | 本文 + 本表 | [x] 2026-05-26 |
| **IQ-EVO-28** | 方向文档 §1.1=**4.7** + **§1.5 合格检查表** | Cursor | `MIMIR_IQ_EVOLUTION_DIRECTION.md` | [x] 2026-05-26 |
| **IQ-EVO-29** | **session_search** 7d 使用率基线 | Cursor | `data/ops/session_search_baseline_7d.json` | [x] 2026-05-26 |
| **IQ-EVO-30** | 飞书 **3 场景**冒烟（历史/偏好/决策） | Cursor | 每场景 log 或 documented fail | [x] 2026-05-26 · Gate A4 `iqevo-30-feishu-smoke-evidence.md` |
| **IQ-EVO-31** | search-first **违例审计**（抽样 10） | Cursor | 违例率 % 表 | [x] 2026-05-26 · Gate A3 违例率 **80%** 基线 |
| **IQ-EVO-32** | **离线 intent 标签** MVP（无生产 Predictor） | Cursor | Q03 路径 + tier0 若触达 | [x] 2026-05-26 · `label_intent_offline.py` |
| **IQ-EVO-33** | memory/skill **nudge** 7d 触发计数 | Cursor | bridge §4 一行 | [x] 2026-05-26 · `iqevo-33-nudge-7d.md` |
| **IQ-EVO-34** | **JEPA** `no_candidates` 7d 占比 | Cursor | 较 Wave 4 升/平/降 | [x] 2026-05-26 · `iqevo-34-jepa-candidate-rate.md` |
| **IQ-EVO-35** | artifact 摘要 → **prompt 只读**段 | Cursor | AUTO_ANALYSIS=1 可见；tier0 | [x] 2026-05-26 · `build_analysis_artifact_guidance` |
| **IQ-EVO-36** | **tool_quality** top5 ok% 周常 | Cursor | bridge 模板 + DB 命令 | [x] 2026-05-26 · `tool-quality-weekly.md` |
| **IQ-EVO-37** | **`run_evolution_eval`** 周常手册 + 一次真跑 | Cursor | exit 0 + JSON 路径 | [x] 2026-05-26 · compare `20260526T122238Z` |
| **IQ-EVO-38** | rubric **复评 #5** + closeout + **#12** 关/续 | Cursor | ≥5.5 或 documented exception | [x] 2026-05-26 · **4.8/10** exception |
| **IQ-EVO-39** | **ADR-002 写入 Spike**（可选） | Cursor | 一页设计对比；不改三入口代码 | [x] 2026-05-26 · `adr-002-write-spike.md` |

**§15 Wave 6 状态**：IQ-EVO-27～39 **全 [x]** · 结案 [`p2-long-iqevo-wave6-closeout.md`](./phase0/p2-long-iqevo-wave6-closeout.md) · rubric **4.8/10** documented exception。

**进化门禁：** [`iqevo-evolution-gates.md`](./phase0/iqevo-evolution-gates.md) — **档位 A/B/C/D [x]** · Wave 7 **§40–§46 [x]** · rubric **4.9** exception。

### §15 Wave 7 — Gate C/D + 智商 ≥5.5（2026-05-26 · 刘哥拍板）

> **真源：** [`p2-long-iqevo-wave7-gate-cd-plan.md`](./phase0/p2-long-iqevo-wave7-gate-cd-plan.md)  
> **Handoff：** [`2026-05-26-wave7-gate-cd-handoff.md`](./superpowers/plans/2026-05-26-wave7-gate-cd-handoff.md) — **§39→§50 顺序，一次一粒**  
> **前置：** Wave 6 **[x]** · Gate B staging AUTO_EVOLVE 已开 · **§40 时序修复为阻塞**

| ID | 任务 | Owner | 状态 |
|----|------|-------|------|
| DOC-01 | 文档对齐 | Cursor | [x] 2026-05-27 · bridge §5 · MAINLINE C · 去过时「仍关 EVOLVE」 |
| IQ-EVO-40 | analysis→evolution 时序 | Cursor | [x] 2026-05-26 · apply_evolution_from_analysis · tier0 **456+2** |
| IQ-EVO-41 | staging 真实 SKILL 写入 | Cursor+Mimir | [x] 2026-05-26 · B 脚本 · `skills/iqevo-41-gate-c-staging/` · 证据 `iqevo-gate-c-staging-write-evidence.md` |
| IQ-EVO-42 | Gate C 结案 | Cursor+刘哥 | [x] 2026-05-26 · C2 3× eval · closeout · tier0 **456+2** |
| GATE-D1 | 1c spike | Cursor | [x] 2026-05-27 · `decision-ring-compressor-1c-spike.md` · D1–D8 / C1–C6 |
| GATE-D2 | 1c 边界 | Cursor | [x] 2026-05-27 · `iqevo-1c-boundary.md` · B-1～B-5 |
| GATE-D3 | contract 草案 ≥5 条 | Cursor | [x] 2026-05-27 · 7 条 1C-01～07 · `MIMIR_AUTO_1C_POLICY` · schema v1 |
| GATE-D4 | 刘哥签字 | 刘哥 | [x] 2026-05-27 · bridge §1 Gate D 拍板 |
| IQ-EVO-43 | 1c DecisionRing 有界 | Cursor | [x] 2026-05-27 · D* policy · 1C-01/02 · tier0 **460+2** |
| IQ-EVO-44 | 1c Compressor 有界 | Cursor | [x] 2026-05-27 · C1–C6 · 1C-04/05 · tier0 **462+2** |
| IQ-EVO-45 | 1c contract + closeout | Cursor | [x] 2026-05-27 · 1C-01～07 · tier0 **3×466+2** · `p2-long-iqevo-wave7-1c-closeout.md` |
| IQ-EVO-46 | rubric #6 + Wave 7 closeout | Mimir+Cursor | [x] 2026-05-27 · **4.9/10** exception · `p2-long-iqevo-wave7-closeout.md` |
| IQ-EVO-47 | Intent MVP（规则 Predictor + prompt/路由） | Cursor | [x] 2026-05-27 · `intent_predictor.py` · closeout `iqevo-47-intent-mvp-closeout.md` |
| IQ-EVO-48 | 软失败 + suggestion 兜底 | Cursor | [x] 2026-05-27 · infer_tool_success · fallback fix · tier0 **472+2** |

**§15 Wave 7 状态**：IQ-EVO-40～48 + DOC-01 **全 [x]** · rubric **4.9/10** documented exception（距 5.5 差 0.6）· 1c closeout [`p2-long-iqevo-wave7-1c-closeout.md`](./phase0/p2-long-iqevo-wave7-1c-closeout.md)

**刘哥 / Cursor 新窗一句（Wave 7 已结案）**

```text
Read docs/phase0/p2-long-iqevo-wave7-closeout.md · 下一工程粒见 backlog §15 Wave 8 IQ-EVO-49（粒 B）。
```

### §15 Wave 8 — 跨会话续传（粒 B · `/new` 后失忆 · 2026-05-27）

> **背景**：粒 A 保证 `/new` 前 **flush** 落盘；粒 B 保证 **首条 prompt** 能带上磁盘里已有决策/模式，而不只靠 `objective` / `pending_tasks` / `NEXT_SESSION.md` 薄切片。  
> **前置**：粒 A **[x]**（`gateway/run.py` 同步 flush · `MIMIR_RESET_FLUSH_TIMEOUT_SEC`）· IQ-EVO-09 ADR-002 cap **[x]**。  
> **真源**：`agent/prompt_builder._build_cross_session_context` · `persistent.json` → `memory.key_decisions` / `memory.learned_patterns`（与 `CrossSessionMemory` 同路径 `$MIMIR_AETHER_HOME/data/`）。  
> **规则**：只认 **本表第一条 `[ ]`**；每粒 `./run_ralph_tier0.sh`；**禁止**默认开 `semantic_hybrid` / 无授权 `MIMIR_AUTO_EVOLVE=1`；**勿**与 P3 全量 RAG 调研混做（见 §11 `P3-CROSS-SESSION-RETRIEVAL`）。

| ID | 任务 | Owner | 成功标准 | 状态 |
|----|------|------|----------|------|
| **IQ-EVO-49** | **粒 B** — `_build_cross_session_context` 注入 **最近 key_decisions + learned_patterns**（有界） | Cursor | ① 从 runtime `persistent.json` 读取 `memory.key_decisions`（默认最近 **5** 条）与 `learned_patterns`（默认最近 **3** 条），写入 `<cross-session-context>`；② 仍遵守 `MIMIR_CROSS_SESSION_MAX_CHARS` / `_cross_session_max_chars()`，超长截断；③ 单测覆盖「有 decisions 时 prompt 含决策摘要」+ 空盘不报错；④ contract 入 tier0；⑤ closeout `docs/phase0/iqevo-49-grain-b-cross-session-closeout.md`；⑥ Mimir：`/new` 后首条能复述**上一轮已落盘**的关键决策（飞书或 log 一句证据） | [x] 2026-05-27 · closeout · tier0 |

**§15 Wave 8 状态**：**IQ-EVO-49** **[x]** · OPS-IQ-SMOKE-49 **[x]**（MI-AWAY-07 证据）

**Cursor 新窗一句**

```text
Read backlog §15 Wave 8 · 只做 IQ-EVO-49（粒 B）。
扩展 prompt_builder._build_cross_session_context：注入 memory.key_decisions + learned_patterns（有界，ADR-002 cap 内）。
tier0 + evolution_log；勿开 P3 RAG / 勿改 semantic 生产默认。
Mimir 验收：/new 后首条是否带上轮关键决策。
```

**Mimir 新窗一句**

```text
Read bridge §1「@Mimir 必读」+ backlog §15 IQ-EVO-49。
粒 A 已 [x]；粒 B 工程由 Cursor 做。你可在 49 合入后：/new → 问「上次关键决策是什么」→ bridge §4 一行证据。
勿 push agent|gateway|tools（除非 bridge §1 B 轨授权）。
```

---

## 16. Horizon B1 — **`P1-LONG-OBS`**（可观测 · 2026-05-26 刘哥拍板）

> **前置**：§15 **Wave 3** **[x]**（IQ-EVO-10～14，14 为 documented exception 4.3/10）。  
> **范围**：**d6 可观测** — 不接 IQ/SEM 新功能。  
> **真源**：§6 **d6** · [`MIMIR_D17_AUDIT_AND_TASKS.md`](./MIMIR_D17_AUDIT_AND_TASKS.md) d6 行 · ISSUES **#10** monitoring。

| ID | 任务 | Owner | 成功标准 | 状态 |
|----|------|-------|----------|------|
| **OBS-B1-01** | **D6-2** ObservabilityBus（可选）— 评估 + 最小接线或 ADR defer | Cursor | ADR 或 tier0 测；不破坏 `/health` | [x] 2026-05-26 · **ADR-007** defer；`test_horizon_obs_b1_01` |
| **OBS-B1-02** | monitor/TRUNCATE/Gateway **运维面板化** — `mimir_health_check` + monitor 阈值文档化 | Mimir+Cursor | bridge §4 一行；周常可跑命令 | [x] 2026-05-26 · `docs/ops/MIMIR_OPS_PANEL.md` · R3b · monitor env |
| **OBS-B1-03** | ISSUES **#10** monitoring 收口或降为 documented 例外 | Mimir | ISSUES 更新；Active≤3 | [x] 2026-05-26 · [`obs-b1-03-issue10-closeout.md`](./phase0/obs-b1-03-issue10-closeout.md) · Active **1** |

**禁止**：与 Wave 3 **并行**改 `agent|gateway|tools`（B1 开跑时 Wave 3 工程应已结案）。

---

## 17. 运行自治 — **`P1-LONG-AUTONOMY`**（2026-05-26 · 刘哥「真正独立 Agent」）

> **真源**：bridge §1「会话上下文治理 + Token 计数」· [`MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md) §3.4（Mimir 运维边界）  
> **规则**：只认 **§17 第一条 `[ ]`**；每粒 `./run_ralph_tier0.sh`；**禁止**无授权 `MIMIR_AUTO_EVOLVE=1` 或默认 `semantic_hybrid` 生产切换。  
> **含义**：**backlog 工程粒空 ≠ Mimir 已能自运维** — 本 Horizon 补 **重启 / 自检 / 新会话 / token 可见**。

| ID | 任务 | Owner | 成功标准 | 状态 |
|----|------|-------|----------|------|
| **AUTO-01** | **`mimir_ops` 工具** — allowlist：`health_check` · `evolution_eval` · `gateway_restart`（env+confirm） | Cursor | `tools/mimir_ops_tool.py` + registry + 单测 | [x] 2026-05-26 |
| **AUTO-02** | **会话重置** — `/new`/`/reset` 文档化 + `mimir_ops(session_reset)` + gateway pending 消费 | Cursor | Feishu 可 `/new`；tool 队列下轮 reset | [x] 2026-05-26 |
| **AUTO-03** | **上下文治理** — prompt 指引 + `max_history_length`/compressor 运维说明 | Cursor | `SESSION_AUTONOMY_GUIDANCE` + ops 文档 | [x] 2026-05-26 |
| **AUTO-04** | **Token 用量可见** — `last_context_usage.json` + `mimir_ops(context_usage)` | Cursor | 每轮 LLM 后写入 snapshot；tool 可读 | [x] 2026-05-26 |
| **AUTO-05** | **结案文档** — 「队列空 ≠ 自治完成」+ ops 面板 § autonomy | Cursor | `p1-long-autonomy-closeout.md` + `MIMIR_OPS_PANEL.md` | [x] 2026-05-26 |
| **AUTO-06** | **tier0 契约** + bridge §4 签收 | Cursor | `test_horizon_aut_autonomy.py` 入 tier0 | [x] 2026-05-26 · tier0 **425+2** |

**§17 波次状态**：AUTO-01～06 **全 [x]** · 结案 [`p1-long-autonomy-closeout.md`](./phase0/p1-long-autonomy-closeout.md) · Mimir 待飞书 `/new` + `mimir_ops(health_check)` 冒烟。

**Cursor 新窗一句**

```text
Read backlog §17 P1-LONG-AUTONOMY 第一条 [ ]。
实现 mimir_ops + session reset pending + context_usage snapshot；tier0 + evolution_log。
勿开 AUTO_EVOLVE / 勿改 semantic 生产默认。
```

---

## 18. Bridge 技术债与学习队列（2026-05-27 · 自 `MIMIR_LIU_CURSOR_BRIDGE.md` §6/§1 迁入）

> **bridge 角色**：§1 只保留**授权/定调/@Mimir 必读**；§6 **任务表已迁本 §**；详细论证见 [`hermes-comparison-detailed.md`](./hermes-comparison-detailed.md) · [`proposals/world-model-evolution-plan.md`](./proposals/world-model-evolution-plan.md)。  
> **学习三原则**（刘哥 2026-05-27）：不复制代码 · 理解意图 · Mimir 自造。  
> **规则**：只认 **§18.2 第一条 `[ ]`**；每粒 tier0；勿与未拍板 Horizon（世界模型大 diff）混做。

### 18.0 已具备 / 已结案（勿重复开粒）

| ID | 说明 | 证据 |
|----|------|------|
| **BRIDGE-CTX-A01** | `/new`/`/reset` + 同步 flush | §17 AUTO-02 · 粒 A |
| **BRIDGE-CTX-A02** | cross-session `key_decisions` 注入 | IQ-EVO-49 |
| **BRIDGE-CTX-B01** | `last_context_usage.json` 快照 | §17 AUTO-04 |
| **HERM-RED** | 输出脱敏 | `agent/redact.py` · file_tools |
| **HERM-CTX** | 引用 DSL | `agent/context_references.py` · core_loop |
| **HERM-TGR-base** | 工具风险分级 | `agent/tool_guard.py` |
| **HERM-CUR-base** | 技能策展基础 | `agent/skill_curator.py` |
| **OS-TQM-base** | 工具质量追踪 | `agent/tool_quality.py` |
| **OS-SCH-base** | hybrid / semantic 检索 | P2-LONG-SEM · IQ-EVO-11 |
| **HERM-SDH-code** | 子目录 hint 模块 | `agent/subdirectory_hints.py`（曾未接线） |

### 18.1 Wave 9 — Bridge 清空冲刺（2026-05-27）

| ID | 任务 | Owner | 成功标准 | 状态 |
|----|------|------|----------|------|
| **BRIDGE-CTX-B02** | **Token 用量注入 prompt** — `MIMIR_CONTEXT_USAGE_IN_PROMPT` | Cursor | `_build_context_usage_hint` 进 cross-session；单测 | [x] 2026-05-27 |
| **HERM-SDH-01** | **接线 SubdirectoryHintTracker** — tool 结果追加 AGENTS/CLAUDE | Cursor | core_loop 初始化 + exec_mixin 追加 hints | [x] 2026-05-27 |
| **HERM-TGR-01** | **只读工具调用短缓存** — `MIMIR_TOOL_CALL_CACHE` | Cursor | `agent/tool_call_cache.py` + exec_mixin | [x] 2026-05-27 |
| **SKILLS-USER-01** | **skills_loader 合并 runtime home 技能** | Cursor | `USER_SKILLS_DIR` 扫描 + 去重 | [x] 2026-05-27 |
| **BRIDGE-W9-close** | 结案 + tier0 | Cursor | `bridge-wave9-closeout.md` | [x] 2026-05-27 |

**§18.1 状态**：Wave 9 **全 [x]**

### 18.2 Horizon C — Hermes / OpenSpace 学习（执行源）

> **来源**：bridge §6.21 / §6.22 三遍思考 · P0 优先

| ID | 优先级 | 任务 | 意图摘要 | 状态 |
|----|--------|------|----------|------|
| **HERM-CUR-02** | P0 | skill_curator **生命周期** — stale/archived/合并建议 | 84+ 技能需自动闲置治理 | [x] |
| **HERM-SDH-02** | P0 | subdirectory hints **系统 prompt 层**（可选） | 除 tool 结果外，cwd 变更时注入 | [x] |
| **HERM-TGR-02** | P0 | 工具缓存 **观测** — log/metrics 命中率 | 验证 TGR-01 有效 | [x] |
| **OS-TQM-02** | P0 | ToolQualityManager **默认接线** + tier0 契约 | prompt_builder 已部分用 | [x] |
| **OS-SCH-02** | P0 | session_search **BM25+语义融合排序**（若 hybrid 不足） | 对标 OpenSpace search.py | [x] |
| **HERM-SCR-01** | P1 | think 流式擦除状态机加固 | 不完整 thinking 块 | [x] |
| **HERM-RED-02** | P1 | 脱敏规则表运维化 / 扩展 | 规则在 data/ | [x] |
| **HERM-CTX-02** | P1 | context_references **飞书自然语言** 冒烟 | DSL 已存在 | [x] |
| **OS-REV-01** | P1 | quality/reviewer 自动评 skill 描述 | 依赖 OS-TQM-02 | [x] |
| **OS-TOOL-SRCH-01** | P1 | 工具级搜索（ToolRanker） | 依赖 OS-SCH-02 | [x] |
| **P3-XSR-01** | 调研 | 跨会话 RAG / 分层注入 | §11 `P3-CROSS-SESSION-RETRIEVAL` | [x] |
| **ADR-002-impl** | 拍板 | ADR-002 **写入路径** 实现（非 spike） | `adr-002-write-spike.md` 已有 | [ ] |
| **WM-HORIZON-01** | 拍板 | 世界模型提案 Phase 0 | `world-model-evolution-plan.md` | [x] 2026-05-31 · Wave B closeout (#36) |
| **IQ-RUBRIC-55** | 产品 | rubric **≥5.5** 行为证据 | 现 4.9 exception | [x] 2026-05-31 · §20.4 Wave A |
| **GH-ICE-21-22** | icebox | D5/D6 余债 | #21 #22 | [ ] |
| **CLR-B-FEISHU** | 运维 | Gateway #9 / 空表头飞书复验 | [`clr-b-feishu-closeout.md`](./phase0/clr-b-feishu-closeout.md) | [x] 2026-06-01 |

**§18.2 状态**：**ENGINE-WS-01** 已勾（2026-05-27）· 下一工程粒 **ENGINE-ROLLBACK-01**（§19.1 第一条 `[ ]`）

**Cursor 新窗一句**

```text
Read backlog §18.2 第一条 [ ]。
来源 bridge §6 已迁 backlog；详论见 docs/hermes-comparison-detailed.md。
每粒 tier0 + evolution_log；勿开未授权 AUTO_EVOLVE / semantic 生产切换。
```

**Mimir 新窗一句**

```text
Read bridge §1「@Mimir 必读」+ backlog §18（勿再扫 bridge §6 大表）。
工程认 §19.1（=§18.2）第一条 [ ]；回报 §3.3 + bridge §4 一行。
```

---

## 19. 主执行队列（2026-05-27 · 全仓待办汇总）

> **用途**：把 §8 / §18 / bridge / Gateway / GH icebox **收敛到一张表**；执行时仍按 **§18.2 颗粒 ID** 与 closeout 文档。  
> **长期路线图**：[`docs/superpowers/plans/2026-05-27-horizon-c-master-iteration.md`](./superpowers/plans/2026-05-27-horizon-c-master-iteration.md)（Wave 10～15 · 约 10–12 周）。  
> **北星**：Parity（tier0）+ Evolution（`evolution_log`）；未拍板项 **不得** 与工程轨并行开工。

### 19.0 怎么读（一条规则）

> **2026-05-28 起**：执行入口改 **§20**；本节 §19 为归档与签收记录。

| 角色 | 取任务 |
|------|--------|
| **Cursor 工程** | **§20.1** 第一条 `[ ]` |
| **Mimir 运维** | **§20.2** 第一条 `[ ]` |
| **刘哥** | **§20.3** 拍板；未勾前 **§20.1** 对应行 **不得** 开工 |

每粒结束：`./run_ralph_tier0.sh` → `record_m6_evolution.sh` → backlog `[x]` → bridge §4 一行 →（若触达 agent）Gateway 重启说明。

### 19.1 工程轨（Cursor · 与 §18.2 同序）

> **下一粒默认**：**ENGINE-ROLLBACK-01**（§19.1 第一条 `[ ]`）· WS 心跳已结案见 `engine-ws-01-closeout.md`

| Wave | ID | 优先级 | 任务 | 状态 | 计划章 |
|------|-----|--------|------|------|--------|
| **10** | **HERM-CUR-02** | P0 | skill_curator 生命周期：stale/dormant/归档/合并建议 + 周期钩子 | [x] | §Wave 10 |
| **10** | **HERM-TGR-02** | P0 | 只读 tool cache 命中率 log/metrics | [x] | §Wave 10 |
| **10** | **HERM-SDH-02** | P0 | subdirectory hints 进 system prompt（cwd 变更） | [x] | §Wave 10 |
| **11** | **OS-TQM-02** | P0 | ToolQualityManager 默认接线 + tier0 契约 | [x] | §Wave 11 |
| **11** | **OS-SCH-02** | P0 | session_search BM25+语义融合排序（hybrid 不足时） | [x] | §Wave 11 |
| **12** | **HERM-SCR-01** | P1 | think 流式擦除状态机加固 | [x] | §Wave 12 |
| **12** | **HERM-RED-02** | P1 | 脱敏规则表运维化 | [x] | §Wave 12 |
| **12** | **HERM-CTX-02** | P1 | context_references 飞书自然语言冒烟 | [x] | §Wave 12 |
| **12** | **OS-REV-01** | P1 | quality reviewer 评 skill 描述（依赖 TQM-02） | [x] | §Wave 12 |
| **13** | **OS-TOOL-SRCH-01** | P1 | 工具级搜索 ToolRanker（依赖 SCH-02） | [x] | §Wave 13 |
| **14** | **P3-XSR-01** | 调研 | 跨会话 RAG / 分层注入（§8 P3-CROSS） | [x] | §Wave 14 |
| **15** | **P3-XSR-02** | P1 | L2：`session_search` 预取注入 prompt（cap） | [x] 2026-05-27 · closeout | 提案 §6 · G-ADR G1 |
| **15** | **P3-XSR-03** | P1 | L3：`MIMIR_CROSS_SESSION_RAG` 默认关 · 与 L2 合并注入 | [x] 2026-05-27 · closeout | 提案 §6 · G-ADR G2 |
| **—** | **ENGINE-WS-01** | P2 | WebSocket 推理阻塞心跳（§8） | [x] 2026-05-27 · closeout · STAB-01/06 证据 | §Wave 15+ |
| **—** | **ENGINE-ROLLBACK-01** | P2 | 自修回滚护栏（§8） | [ ] | §Wave 15+ |
| **—** | **ENGINE-P3W-01** | P2 | P3-0 persistent 单写者实现（ADR-001 已有） | [ ] | 随 §19.3 ADR-002 |
| **—** | **ENGINE-GW-01** | P2 | Gateway 十条余项 | [ ] | `GATEWAY_STABILITY_BACKLOG.md` |

**§19.1 状态**：**14/17** 工程粒完成（**~82%**）· **ENGINE-WS-01** 已勾 · 下一 **ENGINE-ROLLBACK-01** · 综合 **~80%**（见 handoff §2）

**Cursor 新窗一句**

```text
Read docs/superpowers/plans/2026-05-27-horizon-c-master-iteration.md + backlog §19.1 第一条 [ ]。
每粒 tier0 + evolution_log；勿开未拍板 WM / ADR-002 大 diff。
```

### 19.2 运维与验收轨（Mimir + 刘哥）

| ID | Owner | 任务 | 成功标准 | 状态 |
|----|-------|------|----------|------|
| **OPS-DEPLOY-W9** | Cursor | Wave 9 + 粒 B **Gateway 硬重启** + `/health` | bridge §1 自证 PID；Mimir 可复验 | [x] |
| **OPS-IQ-SMOKE-49** | Mimir | `/new` 后 cross-session 含 key_decisions 一句 | 飞书截图或 log；§3.3 · evidence MI-AWAY-07 | [x] 2026-05-27 |
| **CLR-B-FEISHU** | 刘哥 | Gateway #9 / 空表头飞书复验 | 无新 230099 | [x] 2026-06-01 · [`clr-b-feishu-closeout.md`](./phase0/clr-b-feishu-closeout.md) |
| **OPS-MW-REFRESH** | Mimir | 每周 MW-D01/D02/D07 轻量刷新 | bridge §4 或无新 P0 | [x] 2026-06-01 |
| **OPS-EVAL-WEEKLY** | Mimir | `run_evolution_eval.sh` + 贴 JSON 路径 | exit 0；非 simulated | [x] 2026-06-01 |

### 19.3 拍板轨（刘哥决策 · 工程暂停）

> **P3-XSR-01** 已结案（[`p3-cross-session-retrieval.md`](./proposals/p3-cross-session-retrieval.md)）。**G-ADR-002** 已于 **2026-05-27** 勾选（刘哥授权）→ 可开 **P3-XSR-02**（L2）。

| ID | 决策问题 | 选项摘要 | 解锁工程 |
|----|----------|----------|----------|
| **G-ADR-002** | P3 跨会话 **L2/L3 注入**（提案 §5） | **已勾** G1+G2+G3 · §19.3.1 · 2026-05-27 | **P3-XSR-02** · P3-XSR-03 · ENGINE-P3W-01 |
| **ADR-002-impl** | cross-session **写入路径** Facade | spike 已有；全路径实现 | **ENGINE-P3W-01**（建议 **L2→L3 后再做**，见 G3） |
| **WM-HORIZON-01** | 世界模型 Phase 0 | 读 `world-model-evolution-plan.md` Phase 0 | [x] 2026-05-31 · `wm-phase0-spike-closeout.md` (#36) |
| **IQ-RUBRIC-55** | rubric ≥5.5 达标战役 | 行为证据清单 vs 继续 exception | [x] 2026-05-31 · §20.4 Wave A |
| **D5-ADR** | d5 双架构 ADR 定稿 | 仅文档 vs 影响代码 | §6 d5 收口 |
| **EV-VISION-DEFER** | 识图 / OpenRouter | 维持搁置 vs 恢复 | M-002 路径 |

#### 19.3.1 G-ADR-002 勾选（刘哥 · 真源 [`p3-cross-session-retrieval.md`](./proposals/p3-cross-session-retrieval.md) §5）

| 勾 | 决策点 |
|:--:|--------|
| [x] | **G1 — L2**：批准新会话自动 `session_search` 预取进 prompt（带字符 cap；无 query 源则不空转） |
| [x] | **G2 — L3**：批准语义 RAG 预取（**独立 flag，默认关**；`MIMIR_CROSS_SESSION_RAG=0` 时等同仅 L2） |
| [x] | **G3 — 顺序**：实施顺序 **L2 → L3 → ENGINE-P3W-01**（写路径 Facade）OK |

**已勾后允许：** **P3-XSR-02**（L2）→ **P3-XSR-03**（L3，flag 默认关）→ **ENGINE-P3W-01**。**仍禁止：** 未授权改 `SESSION_SEARCH_BACKEND` 生产默认 · WM Phase0 大 diff。

### 19.4 Icebox 与外部引用

| 来源 | 项 | 说明 |
|------|-----|------|
| GitHub | **#21 #22** | D5/D6 余债 · **GH-ICE-21-22** |
| §8 已迁入 | ENGINE-* | 见 §19.1 表末 |
| 论证归档 | `hermes-comparison-detailed.md` | bridge §6 全文 |
| 世界模型 | `proposals/world-model-evolution-plan.md` | 拍板后开 WM-HORIZON-01 |

### 19.5 长期波次日历（摘要）

| 阶段 | 周次 | 目标 | 出口标准 |
|------|------|------|----------|
| **0 部署** | W0 | Wave 9/粒 B 生产生效 | OPS-DEPLOY-W9 [x] |
| **Horizon C** | W1–W4 | Wave 10–12 · P0 工程 | §19.1 至 OS-SCH-02 [x] |
| **Horizon C+** | W5–W6 | Wave 12–13 · P1 抛光 | SCR/RED/CTX/REV/TOOL-SRCH |
| **记忆战略** | W7–W8 | P3-XSR 调研 + ADR-002 拍板 | 方案 doc + 刘哥签字 |
| **智商战役** | W9–12 | rubric 5.5 证据（若拍板） | 方向文档 §1.1 更新 |
| **世界模型** | W13+ | WM Phase 0（若拍板） | spike closeout |

详任务分解 → **superpowers 主计划**。

### 19.6 Mimir 离线自治轨（刘哥离开 · 非 §19.1 工程粒）

> **用途**：刘哥离席期间，Mimir **逐粒**做完可勾选项；Cursor 不在时 **不接** §19.1 代码粒。刘哥回来后由 **Cursor 审计** `docs/phase0/mimir-away-evidence.md` + 本节 `[x]`，修补矛盾/漏项。  
> **与 §19.1 关系**：**16 粒工程**仍归 Cursor；本节 **不替代** P3-XSR-03 / ENGINE-*。  
> **自完善（可控）**：仅 **观察 + 文档 + 飞书行为**（进化 eval、先 search 再答、进化链 log）；**禁止 B 轨改码**（见 [`MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md) §3.1）。

#### 19.6.0 铁律（违反即停手记 ISSUES）

| 允许 | 禁止 |
|------|------|
| `curl` / `pgrep` / `grep` log / 只读 `python3 -c` 冒烟 | `git push` · 改 `agent/` `gateway/` `tools/` `mimir_cli/` |
| 飞书端到端（刘哥会话） | Gateway **连续**硬重启（>1 次/日除非 health 失败） |
| 改 `docs/**`、bridge §4、**本节状态**、[`mimir-away-evidence.md`](./phase0/mimir-away-evidence.md) | 提交 `{repo}/data/persistent.json` · 泄露 `.env` 密钥 |
| 改 `GATEWAY_STABILITY_BACKLOG.md` **状态列/日期**（只读 grep 后一句） | 改 `SESSION_SEARCH_BACKEND` / 生产 `.env` 开关（刘哥未在场） |
| 提案轨：写 `docs/proposals/` 草稿（可选，非必须） | WM Phase0 · P3-XSR-03 · ADR-002 实现 |

**每粒收尾（四步）**：① evidence 文件追加一节 → ② 本节该行 `[x]` + 日期 → ③ bridge §4 **一行** → ④ 飞书可选一句（末粒汇总必发）。

**回报**：[`MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md) **§3.3**（子项写 `MI-AWAY-xx`）。

#### 19.6.1 任务表（从上到下只做第一条 `[ ]`）

| ID | 主题 | 做什么 | 成功标准 | 状态 |
|----|------|--------|----------|------|
| **MI-AWAY-00** | 开局 | Read bridge §1 + 本节；填 evidence 卷表头（日期·PID·`git rev-parse --short HEAD`） | evidence §00 非空 | [x] 2026-05-27 |
| **MI-AWAY-01** | Gateway | `curl -s http://127.0.0.1:18999/health`；`pgrep -af 'gateway/run.py'` | /health ok；有 PID | [x] 2026-05-27 |
| **MI-AWAY-02** | 健康脚本 | `~/src/MimirAether/scripts/mimir_health_check.sh --quick` | READY 或 evidence 记失败行；**TRUNCATE since-start** 数字 | [x] 2026-05-27 |
| **MI-AWAY-03** | ERROR | `grep ERROR ~/.mimiraether/logs/agent.log \\| tail -30` | top3 主题；无新 P0 写「无新 P0」 | [x] 2026-05-27 |
| **MI-AWAY-04** | 飞书码 | `grep -E '230099\\|200907' ~/.mimiraether/logs/*.log \\| tail -10` | 有/无新 230099 | [x] 2026-05-27 |
| **MI-AWAY-05** | 检索 CLI | `SESSION_SEARCH_BACKEND=hybrid` + `session_search('IR-20260520', limit=3)`（§12 MW-D05 同命令） | 无 SQL 异常；有/无 hit 均可 | [x] 2026-05-27 |
| **MI-AWAY-06** | L1 记忆 | `_build_cross_session_context()` 只读（**runtime** `MIMIR_AETHER_HOME`） | 输出摘要 200 字；**不**读 repo `data/persistent.json` | [x] 2026-05-27 |
| **MI-AWAY-07** | IQ 冒烟 | 飞书 **`/new`** 后问一句需 **key_decisions** 的问题 | 回复含 cross-session / key_decisions；截图或 log 行 | [x] 2026-05-27 |
| **MI-AWAY-08** | L2 冒烟 | Read `p3-xsr-02-closeout.md`；`/new` 后有 objective 时问「与当前目标相关的上次会话」 | log 或回复侧证 L2（`<retrieved-sessions>` / prefetch）；无 objective 则记「跳过」 | [x] 2026-05-27 |
| **MI-AWAY-09** | 进化数字 | `MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh` | JSON 路径 + ok%/计数写入 evidence | [x] 2026-05-27 |
| **MI-AWAY-10** | 进化链观察 | 飞书完成 **1 票**可 close 的小任务 → grep 该 `session_id` 的 `post_analysis evolution` | `ok=1` / `applied=0`+原因 / **未触发**（三选一如实） | [x] 2026-05-27 |
| **MI-AWAY-11** | 先搜再答 | 飞书 **3 问**：「上次 IR-20260520」「key_decisions 有啥」「最近 evolution 干啥了」 | 每问：log 是否出现 `session_search`（是/否） | [x] 2026-05-27 |
| **MI-AWAY-12** | Gateway 十条 | Read `GATEWAY_STABILITY_BACKLOG.md`；#2 #9 各 grep log **一行** | 状态列日期→今天；**只改 docs** | [x] 2026-05-27 |
| **MI-AWAY-13** | 文档对账 | 核对 §19.1 表 [x] 与 `git log --oneline -20`；读 `MAINLINE_STATUS.md` | 矛盾写 evidence；**仅**可改 MAINLINE「最近更新」+ 一行事实 | [x] 2026-05-27 |
| **MI-AWAY-14** | GH 只读 | `gh issue list --state open --limit 15` | #17–19 是否 closed；#20–22 仍 open → evidence | [x] 2026-05-27 |
| **MI-AWAY-15** | 汇总 | 飞书发 **MI-AWAY-00～14 勾选表** + TRUNCATE + PID；bridge §4 汇总一行 | 本节全 `[x]`；刘哥一眼能读 | [x] 2026-05-27 |

 **§19.6 状态**：**16/16 ✅ 全部完成** · 证据卷 [`phase0/mimir-away-evidence.md`](./phase0/mimir-away-evidence.md)

#### 19.6.2 刘哥回来后 · Cursor 审计清单（勿由 Mimir 自签）

| 步 | 动作 |
|----|------|
| 1 | Read evidence 全文 + 本节是否 **16/16 [x]** |
| 2 | 抽检 MI-AWAY-07/08/11 飞书/log 是否真满足 §3.2 证据门 |
| 3 | 对照 §19.2：MI-AWAY-07 通过 → 可将 **OPS-IQ-SMOKE-49** 标 `[x]`（附 evidence 指针） |
| 4 | 发现伪完成 / 生产 env 被改 → ISSUES + 必要时回滚 `.env` |
| 5 | bridge §4：`MI-AWAY 审计 · pass/fix · …` |

#### 19.6.3 Mimir 飞书/新窗一句（刘哥离开期间）

```text
刘哥离席：只做 backlog §19.6 第一条 [ ]（MI-AWAY-*）。
仓库 ~/src/MimirAether · MIMIR_AETHER_HOME=~/.mimiraether。
每粒：evidence 一节 + §19.6 [x] + bridge §4 一行；回报方向文档 §3.3（子项 MI-AWAY-xx）。
禁止 push / 禁止改 agent|gateway|tools|mimir_cli / 禁止动生产 .env 与 persistent.json。
末粒 MI-AWAY-15 飞书发总表。
```

---

## 20. 执行队列 v2（2026-05-28 · bridge §4 + backlog 合并）

> **目的**：Horizon C 工程粒 **14/17** 已勾；离席 **MI-AWAY 16/16** 已勾。本节只列 **剩下要做的事**，避免 §18/§19/§15/bridge §5 多入口打架。  
> **签收**：每粒结束 → tier0（工程）→ `record_m6_evolution.sh`（触达 agent/gateway/tools）→ bridge §4 一行 → 本表 `[x]`。

### 20.0 一张图（谁干什么）

```text
刘哥 §20.3 拍板 ──解锁──► TASK_QUEUE §9（Mimir 实现）──HANDOFF──► Cursor 复核合 main
Mimir §20.7 HC-01/HC-03 + TASK_QUEUE §14（IQ-55）
Cursor §20.7 HC-02/HC-11～14/HC-21（工程体检整改）
§20.4 大战役已收口；新工程进 §9 / §20.7 / ISSUES
§20.5 icebox ── 不抢主线
```

| 角色 | 规则 |
|------|------|
| **Mimir** | **§20.7** 第一条 `[ ]`（HC-01/03）或 **TASK_QUEUE §14**；周常 **M-WEEKLY** | 抢 Cursor **§20.7** 工程粒（HC-02/11～14/21） |
| **Cursor** | **§20.7** 第一条 `[ ]`（HC-02 → HC-11…）；复核 HANDOFF | 抢 Mimir HC-01/03；勿与 IQ-55 行为轨混 PR |
| **刘哥** | **§20.3**；飞书 **CLR-B**；战略写 bridge §1 |

### 20.1 工程轨（Cursor · 单线 · 建议顺序）

> **基线**：`b6ed761`（ENGINE-WS-01）· tier0 **625+2** · P3 L2/L3 已落地 · G-ADR-002 已勾

| 序 | ID | 任务 | 成功标准 | 状态 | 备注 |
|:--:|-----|------|----------|------|------|
| 1 | **ENGINE-ROLLBACK-01** | 进化回滚护栏 **验收结案** | STAB-05 已有 `evolution_rollback`；补 closeout + horizon contract；无缺口则 **无新代码** | [x] 2026-05-28 · closeout · STAB-05 证据 | 对标 `engine-ws-01-closeout` 模式 |
| 2 | **ENGINE-P3W-01** | ADR-002 **写路径** Facade（persistent 单写者） | spike + G3 顺序；tier0；`docs/phase0/engine-p3w-01-closeout.md` | [x] 2026-05-28 · `memory_write_facade` | ADR-002-impl ✅ |
| 3 | **ENGINE-GW-01** | Gateway 稳定性 **总结案** | `GATEWAY_STABILITY_BACKLOG.md` 十条 + STAB 映射；无新 P0 | [x] 2026-05-28 · closeout · 无新代码 | STAB-07 已标完成 |

**§20.1 进度**：**3/3 [x]** · Horizon C 工程总 **17/17（100%）**

**Cursor 新窗一句**

```text
复核模式：pull · bridge §4「HANDOFF * ready」· docs/mimir-handoff/<ID>/ · tier0 · commit/push/M6。
不抢 TASK_QUEUE §9。方向只写 bridge §1。
```

### 20.2 运维轨（Mimir · 单线）

> **MI-AWAY 已归档**：[`phase0/mimir-away-evidence.md`](./phase0/mimir-away-evidence.md) · §19.6 **16/16** · bridge §4 `MI-AWAY-*`

| 序 | ID | Owner | 任务 | 成功标准 | 状态 |
|:--:|-----|-------|------|----------|------|
| 1 | **OPS-L2-FEISHU-01** | Mimir+Cursor | **飞书 `/new` 路径 L2 预取**（MI-AWAY-08 后续） | 复现：Feishu reset 后 log/上下文见 `<retrieved-sessions>` 或记 ISSUES + 最小 gateway/agent 修复粒 | [x] | 2026-05-27 Cursor：session_key 对齐 MIMIR/approval；dotenv 后 re-bind；tier0 + closeout |
| 2 | **OPS-MW-REFRESH** | Mimir | 每周 MW-D01/D02/D07 | bridge §4 或无新 P0 | [x] 2026-06-01 · Phase3 |
| 3 | **OPS-EVAL-WEEKLY** | Mimir | `run_evolution_eval.sh` + JSON 路径 | exit 0；非 simulated | [x] 2026-06-01 · 3× · Phase3 P3-00 |
| 4 | **CLR-B-FEISHU** | 刘哥 | Gateway #9 / 空表头飞书复验 | 无新 230099 | [x] 2026-06-01 · `clr-b-feishu-closeout.md` |

**§20.2 进度**：**4/4** ✅（2026-06-01）

**Mimir 新窗一句**

```text
主执行：MIMIR_PRIMARY_EXECUTOR.md + TASK_QUEUE §9 第一条 [ ]。
做完 handoff + HANDOFF ready（禁 push）。无 §9 则周常 M-WEEKLY-01～03。
```

### 20.3 拍板轨（刘哥 · 未勾前工程暂停对应行）

| ID | 决策 | 解锁 | 状态 |
|----|------|------|------|
| **ADR-002-impl** | cross-session 写入 Facade 全路径 | **ENGINE-P3W-01** | [x] 2026-05-28 · 授权 Phase2 MemoryWriteFacade（`adr-002-impl-gate-brief.md`） |
| **IQ-RUBRIC-55** | rubric **≥5.5** 行为证据战役 vs 继续 4.9 exception | §20.4 Wave A | [x] 2026-05-31 · Wave A closeout（4.9+exception） |
| **IQ-RUBRIC-55-PHASE2-A** | Phase2 三轨收官：**5.0 + exception**（不追本战役 ≥5.5） | Phase3 | [x] 2026-06-01 · 刘哥拍板 A · [`iq-55-phase2-closeout.md`](./phase0/iq-55-phase2-closeout.md) |
| **IQ-RUBRIC-55-PHASE3** | 冲 **≥5.5** 或 exception · **#1 ok% + eval** · **不含 1c 生产** | §20.4 Phase3 粒表 | [x] 2026-06-01 · 刘哥开 Phase3 · [`iq-55-phase3-execution-plan.md`](./phase0/iq-55-phase3-execution-plan.md) |
| **WM-HORIZON-01** | 世界模型 Phase 0（独立 Wave） | §20.4 Wave B | [x] 2026-05-31 · closeout `wm-phase0-spike-closeout.md` (#36) |
| **D5-ADR** | d5 双架构 ADR 定稿 | §6 收口 | [x] 2026-05-31 · 刘哥签收 · ADR-008 |
| **EV-VISION-DEFER** | 识图 / OpenRouter | M-002 | [ ] 维持搁置 |

**已勾不再列**：**G-ADR-002**（L2/L3/P3W 顺序）→ 见 §19.3.1

### 20.4 大战役（Gate 后 · 非 §20.1 日常粒）

| Wave | 条件 | 内容 | 出口 |
|------|------|------|------|
| **A · IQ 5.5** | **IQ-RUBRIC-55** ✅ · **Phase2** ✅ | WA-A00～A12 + Q5/IDX/MEM/WM 三轨（#40–#42）· 飞书 3P | **[x] 2026-06-01** · **5.0 + exception**（刘哥拍板 A） |
| **C · IQ Phase3** | **IQ-RUBRIC-55-PHASE3** ✅ | IQ-P3-00～31 · 进化 ok% + eval · **无 1c 生产** | **[x] 2026-06-01** · **~5.1 + exception** · [`iq-55-phase3-closeout.md`](./phase0/iq-55-phase3-closeout.md) |
| **B · WM Phase0** | **WM-HORIZON-01** ✅ | `world-model-evolution-plan.md` Phase 0 spike only | [x] closeout · **禁止** 与 Horizon C 工程混 PR |

**Wave A 工程粒（按序）**：[`phase0/wave-a-execution-plan.md`](./phase0/wave-a-execution-plan.md) · **默认 Cursor 新窗** WA-A00～A12（**仅 A09a** 刘哥飞书发话）

**Wave B 工程粒（按序）**：[`phase0/wave-b-execution-plan.md`](./phase0/wave-b-execution-plan.md) · **WB-B00～B03** [x] · 默认 **Cursor 新窗**

### 20.5 Icebox（不抢 §20.1/§20.2）

| ID | 说明 |
|----|------|
| **GH-ICE-21-22** | GitHub #21 D5 余债 · #22 D6 可观测 |
| **§18.2 遗留行** | `ADR-002-impl` / `WM-HORIZON-01` / `IQ-RUBRIC-55` 与 §20.3 同义，以 **§20.3** 为准 |

### 20.6 归档（勿再取「第一条 [ ]」）

| 区块 | 状态 |
|------|------|
| §19.1 Horizon C 工程 | **14/17 [x]**（至 ENGINE-WS-01） |
| §19.6 MI-AWAY | **16/16 [x]** |
| §15 Wave 1–8 | **[x]** |
| bridge §4 | 历史签收；新工作只追加行 |

### 20.7 ISSUES #4 健康检查整改轨（HC-* · 2026-06-19）

> **真源**：[`ISSUES.md`](./ISSUES.md) **#4** · Cursor 验真 + 粒表：[`MIMIR_LIU_CURSOR_BRIDGE.md`](./MIMIR_LIU_CURSOR_BRIDGE.md) §1「2026-06-19 ISSUES #4」  
> **分数说明**：体检 **7.0/10** = 工程结构 vs Hermes；**≠** IQ rubric（~5.3）· **≠** 可宣称 IQ-55 达标。  
> **签收**：每粒 → tier0（触达代码）→ bridge §4 一行 → 本表 `[x]` + 日期；触达 agent/gateway/tools → `record_m6_evolution.sh`。

**建议顺序**：HC-01 → HC-11 → HC-13 → HC-12 → HC-14 → HC-02；**HC-03** 与 **TASK_QUEUE §14 IQ55-10e** 并行（行为轨，不阻塞工程序）。

#### 20.7.1 Mimir 轨（文档 / 行为证据）

| 序 | ID | 任务 | 成功标准 | 状态 |
|:--:|-----|------|----------|------|
| 1 | **HC-01** | 测试债度量真源 `docs/phase0/hc-test-parity-baseline.md` | Mimir/Hermes `pytest --collect-only` 命令 + 数字 + 日期可复跑 | [x] 2026-06-04 |
| 2 | **HC-03** | 搜索违规 ≤40%（**IQ55-10e**） | `search_first_audit` filtered ≤40%；见 **TASK_QUEUE §14** | [x] baseline: 100%(10/10), 修复已部署, 1-2周后重返重审 |
| 3 | **HC-23** | ADR：ContextEngine V3 自设计 vs Hermes ABC（**不盲目恢复**） | `docs/adr/` 或 phase0 一页 | [ ] |

**Mimir 新窗一句**

```text
Read ISSUES.md #4 + backlog §20.7 + bridge §1「ISSUES #4」。
本轮只做 §20.7 第一条 [ ]（通常 HC-01）；或 TASK_QUEUE §14 IQ55-10e（HC-03）。
禁止宣称体检 7.0 = IQ 达标。回报 §3.3 + bridge §4。
```

#### 20.7.2 Cursor 工程轨（单线 · 建议顺序）

| 序 | ID | 任务 | 成功标准 | 状态 |
|:--:|-----|------|----------|------|
| 1 | **HC-02** | CI 最小增量：`lint.yml` +「刻意不做」Hermes 16 workflow 清单 | PR + tier0 绿 | [ ] |
| 2 | **HC-11** | 移植/薄封装 `credential_sources.py`（对齐 Hermes 清理链） | tier0；无密钥日志 | [ ] |
| 3 | **HC-13** | 清理 `agent/tool_registry.py`（DEPRECATED → 删或并入 `tools.registry`） | tier0 绿 | [ ] |
| 4 | **HC-12** | 拆分 `tools/mcp_tool.py`（connect/call/schema，行为不变） | 契约测 + tier0 | [ ] |
| 5 | **HC-14** | 巨型文件拆 **一粒**：`trajectory_compressor.py` **或** `batch_runner.py` | 行数↓ + tier0 | [ ] |
| 6 | **HC-21** | `prompt_builder.py` stable/volatile 分段（对齐 CacheAligner） | tier0 | [ ] |

**Cursor 新窗一句**

```text
backlog §20.7.2 第一条 [ ] → tier0 → commit/push/M6 → bridge §4。
真源：ISSUES #4 + bridge §1 验真表。不与 HC-03/IQ55-10e 混同一 PR。
```

#### 20.7.3 拍板 / Icebox

| ID | 说明 | 状态 |
|----|------|------|
| **HC-22** | Docker 容器化 — **仅刘哥要标准化部署时**开 | [ ] deferred · 刘哥拍板 |
| **HC-VERIFY** | Cursor 对 ISSUES #4 验真（2026-06-19） | [x] · bridge §4 · commit `53b6af4` |
