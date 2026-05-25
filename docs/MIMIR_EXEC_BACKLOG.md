# MimirAether 执行待办（统一 backlog）

> **最近更新**：2026-05-24（**Phase 1 长任务** — §11 Memory 检索队列 + 未完成项盘点）  
> **离线沟通**：`docs/MIMIR_LIU_CURSOR_BRIDGE.md` §4/§5；Mimir 飞书每轮 Read bridge + 本表  
> **规则**：从 **§11 Phase 1 长任务** 取**第一条** `[ ]` 子项；做完勾 `[x]` + 简短回报 + `./run_ralph_tier0.sh`（触达代码时）。§2 / Phase 0 **只读**，勿再取 E-00x。  
> **卡住**：记 `docs/ISSUES.md` 或 `docs/MIMIR_ISSUES.md`，停手等刘哥。  
> **勿提交**：`data/persistent.json`（runtime 镜像）。

**Wiki 审计原文**（只读、勿改 HTML）：`~/.openclaw/wiki/main/iterations/d{1..7}-audit-report.html`  
**Wiki 评注（经验层）**：`docs/MIMIR_D17_WIKI_AUDIT_COMMENTARY.md` — 对照真源逐阶段评价，2026-05-20

---

## 1. 角色分工（避免 d4 / D4心跳 混淆）

| 角色 | 做什么 | 不做什么 |
|------|--------|----------|
| **Mimir** | 冒烟、复现、飞书端到端、grep 日志、更新 ISSUES / 本表状态、外部检测四模块状态 | 改 `agent/`/`gateway/`/`mimir_cli/` 架构；删 `role=tool` 伪修复；填进化 19 存根 |
| **Cursor / 工程** | d1–d7 **代码**、拆分、合 `main`、tier0、evolution_log | 代刘哥配密钥、代发飞书 |
| **刘哥** | `OPENROUTER_API_KEY`、飞书复验、授权 `git push` | — |

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

### d5 — 自修/进化 · 未启动

| ID | 任务 | 状态 |
|----|------|------|
| D5-0 | Recorder 按 session 隔离 | [x] E-007 |
| D5-0b | skill 路径白名单 | [x] E-007 |
| D5-1 | `simulated: true` | [x] 2026-05-25 · IEVO-01 |
| D5-2 | 单通路 FIX 写 SKILL | [x] E-009 |
| D5-3 | 测试 | [x] 2026-05-25 · IEVO-02 |
| D5-ADR | 双架构决策（仅 ADR） | [ ] |

### d6 — 可观测性 · 未启动

| ID | 任务 | 状态 |
|----|------|------|
| D6-0a | insights SQL `TOOL_CALL` | [x] session_tracker.tool_calls + pipeline |
| D6-0b | monitor 阈值 + status | [x] agent/monitor.py + monitor_alerts.json |
| D6-0c | health.register | [x] `/health` 含 agent + agent_error_rate |
| D6-0d | RateLimitTracker Lock | [x] E-006 batch |
| D6-1 | trajectory/recorder SoT ADR | [x] 2026-05-25 · IEVO-03 · ADR-005 |
| D6-2 | ObservabilityBus（可选） | [ ] |
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
- **当前执行源**：**§13.1 `P0-LONG-CLEARANCE`**（[`MIMIR_ZERO_DEBT_MASTERPLAN.md`](./MIMIR_ZERO_DEBT_MASTERPLAN.md)）；§11/§12/§8/§6 **只读归档**。
- **勿**：提交 `data/persistent.json`；重做 E-001～E-012。

### 9.1 未完成项盘点（2026-05-25）

| 桶 | 数量 | 说明 |
|----|------|------|
| **§13.1 母任务** | **1** Active | `P0-LONG-CLEARANCE` — 子阶段 A [~] → B→C→D→E |
| **§11 长任务** | **0** Active | `P1-LONG-MEM` **[x]**；Horizon **`P2-LONG-SEM`** 清空后再开 |
| **§6 Phase 2 候选** | **6** `[ ]` | 已并入 **CLR-D / CLR-E**；勿单独开队列 |
| **§8 工程 icebox** | **4** 条 | 已并入 **CLR-C**（`P2-LONG-STAB`） |
| **Gateway 十条** | **~4** 待工程 | CLR-C 结案；#9 待 **CLR-B** 飞书复验 |
| **GitHub open** | **10** | icebox **5** + wave-2 **4** + phase-2 **1**；Done 目标 **≤6** |
| **Active P0** | **1** | `MIMIR_ISSUES` **#10 TRUNCATE** → **CLR-C STAB-04** 优先 |
| **搁置** | **1** | EV-VISION-DEFER（识图） |

**对策不变**：只认 **§13.1 第一条 `[ ]` 子阶段**；子阶段内只认该段 **第一条 `[ ]` 子项**。

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
| **P1-LONG-OBS** | d6 余债 D6-1～3 ADR/测试 | §6 | [ ] Phase 2 候选 |
| **P1-LONG-EVO** | d5 余债 D5-1/3、真进化 | §6、Unified Plan | [ ] Phase 2 候选 |
| **P2-LONG-SEM** | Memory **语义化**（chromadb + 检索策略） | Unified Plan Phase 2 | [ ] 前置已满足（P1-LONG-MEM 结案 2026-05-24） · 关联 §8 P3-CROSS-SESSION-RETRIEVAL（存储层 ok，缺注入策略） |

**Semantic 检索**：明确 **不在** `P1-LONG-MEM` 内；结案后再排 `P2-LONG-SEM`，避免与 FTS/LIKE 并行膨胀。

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
| **E** | **P2-LONG-IEVO** | Cursor | IEVO-01～06；**D8**；GH #21/#22 部分关 | [ ] |
| **✓** | **CLEARANCE-DONE** | 刘哥 sign-off | §0 **8/8**；MAINLINE 刷新；Horizon 二选一 | [ ] |

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
| **IEVO-06** | IEVO 结案 + Phase ∞ 续勾 | MAINLINE 绿 | [ ] |

---

### 13.0 进度与 Done 对照（2026-05-25）

| masterplan §0 | 进度 |
|---------------|------|
| D1 GH ≤6 | 🟡 10 open（标签已整理） |
| D2 Active 无 P0 | 🟡 #10 → **monitoring**（since-start R4） |
| D3 Gateway 十条 | ✅ **STAB-07**（2026-05-25） |
| D4 §13 无 `[ ]` | 🟡 子阶段 **E** 进行中（A/B/C/D 已结案） |
| D5 tier0 | ✅ **322+2** |
| D6 飞书 smoke | ✅ T-03/T-04 + R5 tool 往返（2026-05-25 刘哥） |
| D7 路径独立 | ✅ **IND-01～06**（§8 独立宣言 · 刘哥签收 2026-05-25） |
| D8 工业进化 MVP | ⬜ → **CLR-E** |

**整体清空（D1–D8）**：约 **48%** · **含独立+IEVO 全链路**：约 **28%**

**Cursor 新窗一句**

```text
Read docs/MIMIR_ZERO_DEBT_MASTERPLAN.md + MIMIR_EXEC_BACKLOG.md §13.1 P0-LONG-CLEARANCE。
只做母任务第一条 [ ] 子阶段内的第一条 [ ] 子项（现：**E/IEVO-06**）。
触达 agent/gateway/tools 后 ./run_ralph_tier0.sh + evolution_log。
```

**Mimir 新窗一句**

```text
Read MIMIR_ZERO_DEBT_MASTERPLAN.md + backlog §13.1 子阶段 A 或 B。
MIMIR_AETHER_HOME=~/.mimiraether。只做 W0-* / W1-* 运维粒；禁止改码/push。
更新 bridge §4 一行。回报：子项 ID + 结果 + 下一粒。
```
