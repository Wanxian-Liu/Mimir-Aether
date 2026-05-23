# 刘哥 ↔ Mimir ↔ Cursor（仓库内对话，与 OpenClaw 无关）

> **真源路径**：`~/src/MimirAether/docs/MIMIR_LIU_CURSOR_BRIDGE.md`  
> **队列真源**：`docs/MIMIR_EXEC_BACKLOG.md`（§2 / §2b / §2c）

| 谁 | 怎么做 |
|----|--------|
| **刘哥** | 飞书找 **Mimir** 说话；离线留言/授权写 **§1、§2**（可 `git pull` 或让 Mimir 代读） |
| **Mimir** | 每轮先 **Read** 本文件 + `MIMIR_EXEC_BACKLOG.md`；做完在 **§4 签收** 写一行、在 backlog 勾 `[x]` |
| **Cursor** | 刘哥回电脑后说「读 bridge」；读 §1–§4 知进度与授权 |

**不走**：OpenClaw cron、微信同步 backlog（微信仍是琬弦/OpenClaw 的事，与 Mimir 队列无关）。

---

## 1. 刘哥 → Mimir / Cursor（你编辑）

### 2026-05-20 — 策略（已读）

- 识图 **搁置**；**DeepSeek-only**，不配 OpenRouter。
- Mimir 继续 **§2c EV-L**；§2b 冒烟已基本完成。

### 2026-05-23 — 执行授权（刘哥 → Cursor）

- E-004 PR #6、E-005 PR #7：**merged** → main
- WIN-2 JEPA：`feat/self_evolution_jepa` rebase main（WIN-5 进行中）
- **push 各分支前必须先问刘哥**（JEPA 已 push；rebase 后 force-with-lease 需再确认）

### （新留言写在此下）

_示例：@Mimir 先做 EV-M02。@Cursor WIN-3 /health 可以开工。_

---

## 2. 授权登记（给 Cursor 工程用）

| 时间 | 授权 | 范围 | 状态 |
|------|------|------|------|
| 2026-05-20 | push（IR/doc） | main | **done** |
| 2026-05-23 | push + PR + merge（**E-004**） | PR [#6](https://github.com/Wanxian-Liu/MimirAether/pull/6) → main | **done** |
| 2026-05-23 | push + PR + merge（**E-005**） | PR [#7](https://github.com/Wanxian-Liu/Mimir-Aether/pull/7) → main | **done** |
| 2026-05-23 | **WIN-2 JEPA** push | `feat/self_evolution_jepa` | **done** · rebase 后 push 再问 |
| — | 恢复识图 | EV-VISION-DEFER | **deferred** |

**授权写法（写在本表，不要在 shell 里跑）：** `授权: git push — 范围: … — 状态: authorized`

---

## 3. Cursor 回复

### 2026-05-20

- 已简化本 bridge：**只给 Mimir 直接读仓库**，不绑 OpenClaw/微信。
- 已收 Mimir **d1–d7 最终回报**（见 §4/§5）。

### 2026-05-23

- PR #6、#7 merged → main（E-004、E-005）。
- WIN-5：JEPA rebase onto main（E-004+E-005）。

---

## 4. Mimir 签收（每轮追加一行）

| 时间 | 已读 bridge+backlog | 本轮 ID | 结果一句话 |
|------|---------------------|---------|------------|
| 2026-05-20 | backlog §2b | **EV-M01～M13** | d1–d7 训练回报完成；TRUNCATE=19；T-03 [~] 待飞书复验 |
| 2026-05-23 | backlog §2 E-004 | **WIN-1** | CLI_CONFIG 默认；PR #6 merged |
| 2026-05-23 | backlog §2 E-005 | **WIN-4** | chat_runner；PR #7 merged |
| 2026-05-23 | feat/self_evolution_jepa | **WIN-5** | rebase main 进行中（bridge 冲突已解） |

---

## 5. Mimir 进度笔记（2026-05-20 · d1–d7 回报摘要）

- **§2b**：T-02/04/05/06/07/08/09/10/11 [x]；T-03 [~]；识图 N/A（DeepSeek）。
- **ISSUES**：#7 d5 / ~~#8 CLI_CONFIG~~ resolved / #9 d6 / #10 d4。
- **下一颗粒**：**E-006** /health（Cursor WIN-3）；Mimir health_check + TRUNCATE。
- **注**：main 含 E-004+E-005；JEPA 见 Draft PR #8。
