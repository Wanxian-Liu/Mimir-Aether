# MimirAether 执行待办（统一 backlog）

> **最近更新**：2026-05-20 末（**IR-20260520 工程结案**；tier0 **181+2**；Mimir 从 **T-02** 续跑；交接 `docs/MIMIR_HANDOFF_20260520.md`）  
> **规则**：从下表「统一队列」取**第一条**未勾选项；做完勾 `[x]` + 简短回报 + `./run_ralph_tier0.sh`（触达代码时）。  
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

## 2. 统一执行队列（按第一条未勾选项执行）

> 状态：`[ ]` 待做 · `[~]` 部分/阻塞 · `[x]` 完成  
> **基线**：IR + E-001～003 + exec/recovery 修复已 commit（`44061e2`…`a612217`）；**push** 见 M-008 / 刘哥授权

| ID | 负责 | 任务 | 成功标准 | 状态 |
|----|------|------|----------|------|
| **E-001** | Cursor | **Gateway WIP 常驻** — mixin 拆分遗漏 `@property` | `pgrep` 稳定；`wait_for_shutdown` 正常 | [x] 见下「E-001 结案」 |
| **E-002** | Cursor | **D3-SPLIT 收尾** — 6 mixin + `home_paths.py` + commit | tier0 绿；gateway 硬重启后 PID 常驻 | [x] 2026-05-20 |
| **E-003** | Cursor | **D4-P0-4** — agent 四 mixin（同 commit） | tier0 绿 | [x] 2026-05-20 |
| **E-IR** | Cursor | **IR-20260520** — recovery 禁 TRUNCATE on 代码错误；exec_mixin import；gateway 冒烟测 | tier0 **181+2**；TRUNCATE 基线 **19** 冻结；飞书 tool Go | [x] 2026-05-20 |
| **M-002** | Mimir+刘哥 | **M2 飞书发图 + 识图** | `Image downloaded` + 能描述图 | [~] 下载 OK；识图 blocked 无 OPENROUTER |
| **M-003** | Mimir+刘哥 | **M3 空表头表** | 列名 `—`；无 230099 | [~] 代码已合；待飞书复验 |
| **M-005** | 刘哥 | **M5 OPENROUTER** | `~/.mimiraether/.env` 或 config vision | [ ] |
| **M-007** | Mimir | **M7 Gateway 十条** | `GATEWAY_STABILITY_BACKLOG.md` 逐条标状态 | [x] 2026-05-20 状态列已更新 |
| **E-004** | Cursor | **D7-0a** `CLI_CONFIG` 默认值 | clarify/approval 不 ImportError | [ ] |
| **E-005** | Cursor | **D7-0b + D7-1** chat 解耦 + 单入口文档 | `cmd_chat` 不 `import cli.main` | [ ] |
| **E-006** | Cursor | **D6-0a–0d** 可观测 Day-1 | insights SQL + monitor 阈值 + health 接线 | [ ] |
| **E-007** | Cursor | **D5-0 / 0b** 进化安全基线 | recorder 隔离 + skill 路径白名单 | [ ] |
| **E-008** | Cursor | **D7-2 / D7-3** 删旧 cli + CLI 冒烟测 | grep 无悬挂引用 + 少量 pytest | [ ] |
| **E-009** | Cursor | **D5-2** 单通路 FIX 真写 SKILL | 一条 e2e + tier0 | [ ] |
| **M-008** | 刘哥 | **M8 push** | 授权后 `git push origin main` | [x] 2026-05-20 → `599ecb3` |

**E-001 结案（2026-05-20）**  
- **根因**：`gateway/health_mixin.py` 拆分时 `should_exit_cleanly` 未成 `@property`，`start_gateway()` 里 `if runner.should_exit_cleanly:` 恒真 → 跳过 `wait_for_shutdown()`，约 2–3s exit 0（非 aiohttp 主因）。  
- **修复**：`health_mixin` 补 `@property`；`session_mixin` 补 `display_hermes_home` 导入。  
- **验证**：tier0 PASS；PID **155486** 常驻；日志 Cron ticker + Lark wss；硬重启后无即退。`Unclosed client session` 为即退连带，稳定后不再现。

**并行允许**：E-004（D7-0a）单独 PR；**禁止** mixin commit + D6 + 删 `cli.py` 同 PR。

**下一条（默认）**：**Mimir → T-02**（飞书发图+识图）；**Cursor → E-004** `CLI_CONFIG`（单独 PR）。T-01 / 工具链已在 IR Phase 3c Go，勿重做工程。

**交接文档**：`docs/MIMIR_HANDOFF_20260520.md` · **微信简报**：OpenClaw skill `mimir-handoff-weixin`（`~/.openclaw/workspace/skills/`）

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
| M2 | M-002 | 飞书发图+识图 | [~] |
| M3 | M-003 | 空表头表 | [~] |
| M4 | — | 触发 tool | [x] |
| M5 | M-005 | OPENROUTER | [ ] |
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
- M5 OPENROUTER: 有/无
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
| D5-0 | Recorder 按 session 隔离 | [ ] → E-007 |
| D5-0b | skill 路径白名单 | [ ] → E-007 |
| D5-1 | `simulated: true` | [ ] |
| D5-2 | 单通路 FIX 写 SKILL | [ ] → E-009 |
| D5-3 | 测试 | [ ] |
| D5-ADR | 双架构决策（仅 ADR） | [ ] |

### d6 — 可观测性 · 未启动

| ID | 任务 | 状态 |
|----|------|------|
| D6-0a | insights SQL `TOOL_CALL` | [ ] → E-006 |
| D6-0b | monitor 阈值 + status | [ ] → E-006 |
| D6-0c | health.register | [ ] → E-006 |
| D6-0d | RateLimitTracker Lock | [ ] → E-006 |
| D6-1 | trajectory/recorder SoT ADR | [ ] |
| D6-2 | ObservabilityBus（可选） | [ ] |
| D6-3 | 测试 | [ ] |

### d7 — CLI 双轨 · d7 窗进行中

| ID | 任务 | 状态 |
|----|------|------|
| D7-0a | `CLI_CONFIG` | [ ] → E-004 |
| D7-0b | chat 解耦 | [ ] → E-005 |
| D7-1 | 单入口文档 | [ ] → E-005 |
| D7-2 | 删 cli.py 等 | [ ] → E-008 |
| D7-3 | gateway/config/chat 测试 | [ ] → E-008 |

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

---

## 9. 续跑提示词（复制到新 Cursor / Mimir 窗）

> 真源：`docs/MIMIR_EXEC_BACKLOG.md` §2 + `docs/MIMIR_HANDOFF_20260520.md`。IR-20260520 工程已结案。

```markdown
# MimirAether 续跑 — 统一 backlog（post IR-20260520）

工作区：`/home/rayliu/src/MimirAether`  
运行时：`MIMIR_AETHER_HOME=~/.mimiraether`  
必读：`docs/MIMIR_HANDOFF_20260520.md` · `docs/MIMIR_EXEC_BACKLOG.md` §2 · `docs/MIMIR_D17_AUDIT_AND_TASKS.md` §5  

合并/宣称完成前：`./run_ralph_tier0.sh` 绿（当前 **181+2**）。勿提交 `data/persistent.json`。无刘哥授权勿 `git push`。

---

## 已完成（勿重做）

| 项 | 说明 |
|----|------|
| E-001～E-003 + **E-IR** | mixin 拆分收尾 + recovery/exec 修复；见 `docs/MIMIR_INCIDENT_IR-20260520.md` |
| T-01 / 工具链 | IR Phase 3c 飞书 read_file Go；tier0 含 mixin 冒烟测 |
| M1 / M4 / M6 / M7 | gateway 重启、tool、ISSUES、十条文档 |
| TRUNCATE | 基线 **19** — 勿再因 NameError 上涨 |

---

## 当前队列头

1. **Mimir：T-02** → T-03 → T-05～T-11（§5 总提示词）  
2. **M-002 / M-003 / M-005** — 飞书发图/表头/OPENROUTER  
3. **Cursor：E-004** `CLI_CONFIG`（单独 PR）  
4. **M-008** — `git push`（刘哥授权后）

---

## Mimir 专用

**入口**：`docs/MIMIR_D17_AUDIT_AND_TASKS.md` §5（post-IR 基线）

| 从 | 任务 |
|----|------|
| **T-02** | 飞书发图+识图（M-002） |
| T-03 | 空表头（M-003） |
| T-05 | OPENROUTER（M-005） |
| T-06～11 | API / reaction / agent 栈 / d5–d7 只读 |

**禁止**：改 mixin；代做 E-004+；删 `role=tool`；未授权 push。

---

## Cursor 工程

- **下一刀**：E-004 only（`mimir_cli/config.py`）  
- **禁止同 PR**：IR 修复 + D6 + 删 `cli.py`

---

## 冒烟命令

cd ~/src/MimirAether && ./run_ralph_tier0.sh
MIMIR_AETHER_HOME=~/.mimiraether ./scripts/restart_gateway_hard.sh
grep -c 'Level 3 TRUNCATE' ~/.mimiraether/logs/agent.log
```

---

## 10. WIP 快照（2026-05-20 末 · 交接）

- **E-001/E-002/E-003/E-IR** ✅ committed；tier0 **181+2 PASS**  
- **TRUNCATE** 冻结 **19**  
- **push**：M-008 ✅ `origin/main` @ `599ecb3`  
- **Mimir**：**T-02** 起；勿重做 T-01/工程  
- **Cursor**：**E-004**  
- **微信**：OpenClaw `mimir-handoff-weixin` skill；DM 已配对  
- **详**：`docs/MIMIR_HANDOFF_20260520.md`
