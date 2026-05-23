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
- 下一工程刀：**EP-C01** 测试（E-006 health 切片 ✅ WIN-3）

---

## 4. Mimir 签收（每轮追加一行）

| 时间 | 已读 bridge+backlog | 本轮 ID | 结果一句话 |
|------|---------------------|---------|------------|
| 2026-05-20 | backlog §2b | **EV-M01～M13** | d1–d7 回报；TRUNCATE=19；T-03 [~] |
| 2026-05-23 | E-004 / E-005 | **WIN-1/4** | PR #6 #7 merged → main |
| 2026-05-23 | JEPA | **WIN-5** | rebase；tier0 3×181+2；@ ae8a5c7 |
| 2026-05-23 | PR #8 | **WIN-8** | JEPA+skills+IC 合入 main @ d3cc0a6；post-merge tier0 PASS |
| 2026-05-23 | E-006 health | **WIN-3** | loopback /health 默认 18999；tier0 186+2 |

---

## 5. Mimir 进度笔记

- **main**：E-004 ✅ E-005 ✅ JEPA ✅ → **E-006** [~] health 切片 ✅ · **EP-C01** 测试
- **ISSUES**：#7 引擎在 main；接 agent loop 若未接仍标 in-progress
- **Mimir 运维**：`scripts/mimir_health_check.sh --quick` + TRUNCATE≤19；读 `MIMIR_UNIFIED_PLAN.md`
