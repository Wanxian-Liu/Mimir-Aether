# 刘哥 ↔ Mimir ↔ Cursor（仓库内对话，与 OpenClaw 无关）

> **真源路径**：`~/src/MimirAether/docs/MIMIR_LIU_CURSOR_BRIDGE.md`  
> **队列真源**：`docs/MIMIR_EXEC_BACKLOG.md`（§2 / §2b / §2c）

| 谁 | 怎么做 |
|----|--------|
| **刘哥** | 飞书找 **Mimir**；战略方向 / 例外授权写 **§1、§2** |
| **Mimir** | 每轮 Read bridge + backlog；冒烟、health_check、§4 签收 |
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

- **Draft PR #8（JEPA）merge 进 main** — 大 feature，单独拍板
- 飞书 **T-03** 等人工复验
- 识图 / OpenRouter / 生产密钥
- `git push --force` 到 **main**（禁止）

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
| — | JEPA → main | PR #8 | **pending** — 刘哥单独拍板 |
| — | 恢复识图 | EV-VISION-DEFER | **deferred** |

---

## 3. Cursor 回复

### 2026-05-23

- main：`d61044a`（E-004 + E-005）
- JEPA：`feat/self_evolution_jepa` rebased on main；Draft **PR #8**
- 常备授权已写入 §1/§2
- 下一工程刀：**E-006** `/health`（WIN-3）或 **EP-C01** 测试

---

## 4. Mimir 签收（每轮追加一行）

| 时间 | 已读 bridge+backlog | 本轮 ID | 结果一句话 |
|------|---------------------|---------|------------|
| 2026-05-20 | backlog §2b | **EV-M01～M13** | d1–d7 回报；TRUNCATE=19；T-03 [~] |
| 2026-05-23 | E-004 / E-005 | **WIN-1/4** | PR #6 #7 merged → main |
| 2026-05-23 | JEPA | **WIN-5** | rebase main；tier0 PASS；origin 已同步 |

---

## 5. Mimir 进度笔记

- **main 工程线**：E-004 ✅ E-005 ✅ → **E-006** 可观测 / **EP-C01** 测试
- **JEPA**：Draft PR #8，**勿合 main** 直至刘哥拍板
- **ISSUES**：#7 in-progress · ~~#8~~ · #9 d6 · #10 d4
- **Mimir 运维**：`scripts/mimir_health_check.sh --quick` + TRUNCATE≤19
