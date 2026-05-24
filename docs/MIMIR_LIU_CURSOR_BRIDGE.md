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
- **Cursor 工程**：**不**自动开 `P2-LONG-SEM`；等刘哥点名。

### 2026-05-25 — P0-LONG-CLEARANCE 工程授权

- **刘哥**：「按你建议我授权。」→ Cursor 执行 **W0-06 结案 A** + **STAB-03** 起 **C 轨**；`commit`/`push`/`tier0`/gateway 重启脚本范围内自行推进。
- **并行**：刘哥 **W1** 飞书 T-03/T-04（Mimir 可提醒，不代测）。

### （新留言写在此下）

_示例：@Mimir EV-M02。@Cursor WIN-3 /health。_

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

---

## 5. Mimir 进度笔记

- **main**：tier0 **246+2**（STAB-03 后待确认）· 母任务 **§13.1 `P0-LONG-CLEARANCE`**
- **Wave 0 A**：**[x] 结案**（W0-06 2026-05-25）
- **Wave 1 B**：**[x] 结案**（T-03/T-04 + R5 2026-05-25）
- **Wave 2 C**：**STAB-05 [x]**（2026-05-25）→ 下一条 **STAB-07**（结案）
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
