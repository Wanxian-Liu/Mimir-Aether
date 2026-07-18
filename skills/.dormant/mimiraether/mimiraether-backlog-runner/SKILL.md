---
name: mimiraether-backlog-runner
description: >
  领 MIMIR_EXEC_BACKLOG 一条未勾选项执行：做完打勾、验证、回报；卡住写 ISSUES 并停。
  飞书/离机指挥用。触发词：做下一条 backlog、按执行清单、backlog-runner。
auto_load: false
---

# backlog-runner — 执行清单一条

**真源**：[`docs/MIMIR_EXEC_BACKLOG.md`](../../../docs/MIMIR_EXEC_BACKLOG.md)（做）、[`docs/MIMIR_ISSUES.md`](../../../docs/MIMIR_ISSUES.md)（卡）。约定见 [`docs/MIMIR_LONG_PLAN.md`](../../../docs/MIMIR_LONG_PLAN.md) §5。

**路径**：代码在 **git clone 根**（`MIMIR_REPO_ROOT`）；数据在 **`$MIMIR_AETHER_HOME`**。禁止 OpenClaw 真源（[`docs/MIMIR_OPENCLAW_BOUNDARY.md`](../../../docs/MIMIR_OPENCLAW_BOUNDARY.md)）。

---

## 何时激活

- 用户说：**「做下一条 backlog」**、**「按执行清单」**、**「backlog-runner」**、**「按 `MIMIR_EXEC_BACKLOG` 做一条」**
- 飞书离机：负责人授权「连续做 N 条 **S** 级」时，仍 **一条接一条**，每条走完本流程再领下一条

**不激活**：战略讨论、多任务并行、未读 BACKLOG 就改代码。

---

## 步骤（一次一条）

1. **Read** — 打开 `docs/MIMIR_EXEC_BACKLOG.md`，在 **「待办」** 区找 **第一条** `- [ ]`（跳过已完成区）。记下 **任务 ID**（如 T10）、**档位** S/M/L、**做/验/人** 三行。
2. **选一条** — 只领这一条。若依赖未满足（BACKLOG 写明依赖且未完成）→ 写 ISSUES **停**，勿跳过。
3. **执行** — 严格按该行 **「做」**；不扩大 scope。分支仅 **`feat/mimir-*`**（需要时从 main 拉）；**不推 main**。
4. **验证** — 按该行 **「验」** 与档位：
   - **S**：多为文档/单文件；能跑则 `./run_ralph_tier0.sh`（改代码时必跑）。
   - **M**：**必须** `./run_ralph_tier0.sh` 全绿后再收尾。
   - **L**：默认 **不合并**；需人在 BACKLOG 标 **人：是** 时停等。
   - 推分支后：提醒负责人看 GitHub **Actions → Ralph**（与 tier0 同源）。
5. **打勾** — 将 `[ ]` 改为 `[x]`，在任务下增一行：`done: YYYY-MM-DD, tier0: …` 或 `done: …, 仅文档`。
6. **回报** — 用下文 **回报格式** 回复（飞书摘要即可）。
7. **停** — 本条结束后 **结束本轮**；下一条须负责人再次触发或明确「连续 N 条」。

---

## 禁止

- **一次做多条** BACKLOG（「连续 N 条」= N 次完整 1–7 循环）
- 动 **OpenClaw** 真源：不启 `~/.openclaw/projects/MimirAether` gateway、不部署 weavevault、不把 `~/.openclaw` 当 `MIMIR_AETHER_HOME`
- **删** `~/.openclaw` 或用户数据目录（下线见 `MIMIR_DECOMMISSION_CHECKLIST.md`，须人执行）
- **推 main** / 直接 merge（除非 BACKLOG 行写明且负责人已授权）
- 在 **ISSUES** 写密钥、`.env` 全文、长日志（只写日志 **路径** 一行）

---

## 卡住时

同一问题 **最多试 2 次**；仍失败 → **写 ISSUES → 停止该任务**（勿无限重试）。

1. 打开 `docs/MIMIR_ISSUES.md`，在 **Open** 下复制模板，新建 **I-xxx**（自增编号）。
2. 填五行：**现象** / **已试** / **需要**（人 / 继续自主 / 等 CI）/ **关联**（Txx）/ 状态 `open`。
3. **不要** 擅自改 BACKLOG 为 `[x]`。
4. 回报：已开 ISSUES + **已停止**。

---

## 分支 / CI（按档位）

| 档位 | 代码改动 | 验证 | 推送 |
|------|----------|------|------|
| **S** | 常仅 `docs/` 或单文件 | 文档可说明「未跑 tier0」；触达 `agent/`/`gateway/`/`tools/` 则跑 tier0 | 可选 `feat/mimir-<id>` |
| **M** | 多文件 + 测试 | **必须** `./run_ralph_tier0.sh` 绿 | 推 `feat/mimir-*` → Actions Ralph |
| **L** | 大改/迁移 | tier0 + 人审 | 默认等人 merge |

合并、是否 push：**以 BACKLOG 行「人：」为准**；默认 **等人回电脑**。

---

## 回报格式（给负责人）

```
任务 ID: Txx
改了什么: （1–3 句，路径列表）
验证: tier0 绿 / 仅文档 / ISSUES 已开 I-xxx
分支/PR: feat/mimir-… / 无 / 待推
下一步: 停等人 / 可领下一条（若已授权连续）
```

---

## 相关链接

- [`docs/MIMIR_EXEC_BACKLOG.md`](../../../docs/MIMIR_EXEC_BACKLOG.md)
- [`docs/MIMIR_ISSUES.md`](../../../docs/MIMIR_ISSUES.md)
- [`docs/MIMIR_LONG_PLAN.md`](../../../docs/MIMIR_LONG_PLAN.md) §5
- [`docs/MIMIR_OPENCLAW_BOUNDARY.md`](../../../docs/MIMIR_OPENCLAW_BOUNDARY.md)
- [`docs/DEVELOPMENT_NORTH_STAR.md`](../../../docs/DEVELOPMENT_NORTH_STAR.md) — 勿宣称 Parity/Evolution 已达成
