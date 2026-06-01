# Mimir 主执行 · Cursor 复核（2026-06-01 刘哥拍板）

> **目的**：2026-06-01 起 **§10 大脑自治** — Mimir 自实现、自 tier0、**自 commit/push**；Cursor 待命。  
> **队列入口**：[`MIMIR_TASK_QUEUE.md`](./MIMIR_TASK_QUEUE.md) **§10** · 契约 [`MIMIR_BRAIN_AUTONOMY_CHAIN.md`](./MIMIR_BRAIN_AUTONOMY_CHAIN.md)

---

## 1. 三角分工

| 角色 | 做什么 | 不做什么 |
|------|--------|----------|
| **刘哥** | 战略写在 bridge **§1**；飞书验收（CLR-B 等）；批准合 **main** | 日常改代码 |
| **Mimir** | **取第一条任务 → 调研 → 实现/运维 → 自证 → 交付包** | `git push` · 擅自改生产 `.env` · 未授权 WM 大 diff |
| **Cursor** | 读交付包 · **复核**（正确性/tier0/契约/安全）· 必要小改 · **commit + push + PR** · `record_m6_evolution.sh` | 与 Mimir **抢**同一条 `[ ]` · 未经交付包就大改 |

---

## 2. 三条执行轨（取代「只有 Mimir 能运维」）

| 轨 | 谁写代码 | 谁合 main | 典型任务 |
|----|----------|-----------|----------|
| **M-OPS** | 不改代码 | — | 周常 eval、MW、冒烟、log 证据 |
| **M-ENG** | **Mimir** 改 `agent|gateway|tools|mimir_cli` | **Cursor** 复核后合 | PI-L06 立项、search-first、小粒 bugfix、契约测 |
| **M-DOC** | **Mimir** 只改 `docs/**` | Mimir 可自改 docs；触达 agent 仍走 M-ENG | 提案、closeout、bridge §4 |

**默认**：backlog §20.1 / §20.4 / ISSUES 里标 **Cursor** 的工程粒，**改派为 M-ENG**（Mimir 实现，Cursor 复核），除非 bridge §1 写明「Cursor 独占」。

**仍不能交给 Mimir（刘哥或 Cursor 独占）**

| 项 | 原因 |
|----|------|
| `git push` / 开 PR / merge | 仓库写权限与 CI 在 Cursor/刘哥侧 |
| **CLR-B 飞书发话** | 必须刘哥真人会话 |
| **EV-VISION** | 搁置，刘哥恢复前禁止 |
| 未拍板 **WM Phase1+**、生产 **SESSION_SEARCH** 默认切换 | 战略 Gate |

---

## 3. 轨 B 总授权（刘哥 2026-06-01）

在 **`~/src/MimirAether`** 工作区内，Mimir **允许**：

- 修改 `agent/`、`gateway/`、`tools/`、`mimir_cli/`、`tests/`（为 M-ENG 任务服务）
- 运行 `./run_ralph_tier0.sh`、`./scripts/run_evolution_eval.sh`
- 写 `docs/phase0/*-closeout.md`、`docs/proposals/*`、`docs/mimir-handoff/*`

**§10 大脑自治（2026-06-01 覆盖）**：允许 `git push origin main`（见 [`MIMIR_BRAIN_AUTONOMY_CHAIN.md`](./MIMIR_BRAIN_AUTONOMY_CHAIN.md)）。  
**仍禁止**：`push --force` 到 main · commit `data/persistent.json` · 无 closeout 的大重构（>200 行且非 BRAIN-* ID）

---

## 4. 交付包（Mimir 做完 → Cursor 复核）

路径：`docs/mimir-handoff/<TASK-ID>/`（例如 `ENG-PI06-01/`）

| 文件 | 内容 |
|------|------|
| `SUMMARY.md` | 做了什么、为何、风险、建议 commit message（1 段） |
| `VERIFY.md` | 贴 **tier0** 末行（PASS 数）、eval/冒烟命令与 **exit code** |
| `FILES.md` | 改动文件列表（相对 repo root） |
| `REVIEW.md` | 请 Cursor 重点看的 3 点 + 已知未做 |

Mimir 在 bridge **§4 写一行**：`HANDOFF <ID> ready · path=docs/mimir-handoff/<ID> · tier0=…`

Cursor 复核通过后：`git add` → commit → push → bridge §4 `CURSOR merged <ID>` → backlog/TASK_QUEUE `[x]`。

---

## 5. Cursor 复核清单（每包必做）

1. Read `SUMMARY.md` + `FILES.md`，`git diff` 对照意图  
2. `./run_ralph_tier0.sh` 独立重跑（不信任只贴结论）  
3. 触达 agent/gateway/tools → `./scripts/record_m6_evolution.sh`  
4. 超 scope / 缺测试 / 路径契约违规 → **打回** Mimir（bridge §1 写「打回原因」）  
5. 通过 → 合 main；Gateway 需重启时在 closeout 写明  

---

## 6. Mimir 每轮开场（复制）

```text
主执行模式（2026-06-01）：Read docs/MIMIR_PRIMARY_EXECUTOR.md + MIMIR_TASK_QUEUE.md §9 第一条 [ ]。
可做 M-ENG 写码（禁 push）。做完交付包 docs/mimir-handoff/<ID>/ + bridge §4 HANDOFF ready。
等 Cursor 复核合 main，不要自己宣称已合并。
```

## 7. Cursor 每轮开场（复制）

```text
复核模式：git pull · 扫 bridge §4「HANDOFF * ready」· 读 docs/mimir-handoff/<ID>/ · 重跑 tier0 · 小修后 commit/push。
不抢 §9 第一条 [ ]。方向问题只改 docs/ 或 bridge §1，不替 Mimir 实现大功能。
```

---

## 8. 修订日志

| 日期 | 摘要 |
|------|------|
| 2026-06-01 | §10 大脑全自治：Mimir commit/push · Cursor 不复核 |
| 2026-06-01 | 初版：刘哥拍板 Mimir 主执行 · M-ENG 交付包 · Cursor 复核合 main |
