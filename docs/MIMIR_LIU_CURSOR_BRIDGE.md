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

### （新留言写在此下）

_示例：@Mimir 先做 EV-L01。@Cursor E-004 可以开工（见 §2 授权）。_

---

## 2. 授权登记（给 Cursor 工程用）

| 时间 | 授权 | 范围 | 状态 |
|------|------|------|------|
| 2026-05-20 | push（IR/doc） | main | **done** |
| — | push + PR（**E-004**） | 仅 `CLI_CONFIG` | **pending** — 刘哥在此行改为 authorized |
| — | 恢复识图 | EV-VISION-DEFER | **deferred** |

**授权写法：** `授权: git push — 范围: E-004 — 状态: authorized`

---

## 3. Cursor 回复

### 2026-05-20

- 已简化本 bridge：**只给 Mimir 直接读仓库**，不绑 OpenClaw/微信。
- 队列与自学习轨见 `MIMIR_EXEC_BACKLOG.md` §2b / §2c。

---

## 4. Mimir 签收（每轮追加一行）

| 时间 | 已读 bridge+backlog | 本轮 ID | 结果一句话 |
|------|---------------------|---------|------------|
| _待 Mimir 填_ | | | |

---

## 5. Mimir 进度笔记（可选；Mimir 每完成一颗粒可追加）

_（由 Mimir 用 read_file 看 backlog 后，在此写 2～3 行快照，勿依赖外部 cron）_
