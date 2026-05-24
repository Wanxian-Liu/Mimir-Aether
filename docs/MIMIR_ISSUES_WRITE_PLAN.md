# Mimir ISSUES 写入轨道 — 缺口审计与长期计划

> **最近更新**：2026-05-24  
> **用途**：刘哥不必盯屏时，Mimir / Cursor 各开新窗按本文件 **§4 队列** 逐粒执行；每粒 ≤30min，可中断续跑。  
> **命名**：口语「isurus」= 本轨道（**I**ssues **S**tatus **U**pdate **R**epo **S**ync）。  
> **真源队列索引**：[`MIMIR_EXEC_BACKLOG.md`](./MIMIR_EXEC_BACKLOG.md) **§12**

---

## 1. 写入面矩阵（什么必须写、写在哪）

| 面 | 文件 | 谁写 | 何时写 | 禁止 |
|----|------|------|--------|------|
| **运维签收** | `MIMIR_LIU_CURSOR_BRIDGE.md` §4 | Mimir 每轮；Cursor 合 PR 后 | 任意 smoke / 工程合并 / 硬重启 | 不写密钥 |
| **执行队列** | `MIMIR_EXEC_BACKLOG.md` §11/§12 | Cursor 工程；Mimir 运维粒 | 子项完成即 `[x]` + 日期 | 勿与 §2 工程归档混读 |
| **主线快照** | `MAINLINE_STATUS.md` | 问进度时；大里程碑 | A/B 阶段结案、长任务结案 | 不代替 backlog 细项 |
| **飞书 Bug** | `docs/ISSUES.md` | Mimir | 复验 pass/fail；Gateway 重启后 | — |
| **工程 Issue** | `docs/MIMIR_ISSUES.md` Active≤3 | Mimir / Cursor | 新阻塞；旧项 resolved | Active 超过 3 须归档 |
| **Gateway 十条** | `GATEWAY_STABILITY_BACKLOG.md` | Mimir grep 后 | 复验 / 重启 / log 新证据 | — |
| **进化审计** | `docs/evolution_log.md` | Cursor | 触达 agent/gateway/tools 合并前 | Mimir 默认不写 |
| **GitHub Issues** | `gh issue …` | Cursor（已授权）或 Mimir comment | 工程结案 / ops 结案 | 无授权不 close |
| **Phase 0 产出** | `docs/phase0/*.md` | Mimir 只读审计 | 已完成 14/14 | 勿改 agent 代码 |
| **runtime** | `data/persistent.json` | **勿提交 git** | — | Mimir/Cursor 均禁止 commit |

**单轮最小闭环（Mimir）**：Read bridge + backlog §12 → 做 **一条** MW-* → 更新 **≥2** 个写入面（通常 §4 + 一个 ISSUES/backlog 行）→ 飞书 3～5 行（若在线）。

---

## 2. 缺口审计（2026-05-24 · 应写未写）

| # | 事件 | 应更新 | 实际 | 缺口 |
|---|------|--------|------|------|
| G1 | A1 Gateway 硬重启 PID 691521 | bridge §4、GH #19、ISSUES #3 | 均已写 | **已闭合**（MW-001/004/005） |
| G2 | A2 `.openclaw` #2 结案 | bridge §4、MIMIR_OPENCLAW §7、GH #2 | 均已写 | **已闭合** |
| G3 | P1-M01～M03 合 main | backlog §11、MAINLINE | 已 [x] | **已闭合**（MW-002） |
| G4 | P1-LONG-GOD 合 main (#16) | backlog §11 并行长任务 | evolution + plan | **已闭合**（MW-002） |
| G5 | PR #23/#24 openclaw | MIMIR_ISSUES / ISSUES | OPENCLAW_BOUNDARY §7 | MIMIR_ISSUES **未记 #2**（低优；可选 MW-W02） |
| G6 | 2026-05-23 后无 Mimir 轮次 | bridge §4 连续签收 | MW-001 已补 | **已闭合** |
| G7 | D17 §5 总提示词 | 指向当前执行源 §11 | MW-003 横幅 | **已闭合** |
| G8 | Feishu T-03/T-04 | ISSUES #2/#3 resolved | #3 `fixed-pending-smoke` | **等刘哥复验**（非 Mimir 独力） |
| G9 | skills manifest / #19 | ops issue 描述 | Gateway 已重启 | **已闭合**（#19 closed） |

**结论**：代码与 tier0 真源领先 **bridge 签收** 与 **backlog 表头快照** 约 1～2 天；不是功能回退，是 **写入纪律** 未跟上。

---

## 3. 安全边界（无人值守）

### Mimir 可自动做

- Read/grep/tail/curl `127.0.0.1:18999/health`
- 改 `docs/**`（除 wiki HTML 真源）、bridge §4、backlog §12 状态
- `./scripts/mimir_health_check.sh --quick`（若有）
- `gh issue comment`（不 close）— 可选
- **单轮一条** MW-*；失败记 `MIMIR_ISSUES.md` 并 **停手**

### Mimir 禁止（除非刘哥本条授权）

- 改 `agent/` / `gateway/` / `mimir_cli/` / `tools/` 行为
- `git push` / `git commit`（默认 **只改 docs 也不 commit**，留 Cursor 或刘哥批）
- 提交 `data/persistent.json`
- 飞书代发 / 配密钥 / OpenRouter
- 硬重启 Gateway **连续多轮**（一天最多 1 次，除非 IR）

### Cursor 可自动做（bridge §1 常备授权）

- §11 **P1-M04～M06** 工程 PR + tier0 + push/merge feature→main
- 关 GitHub 工程 issue、更新 evolution_log
- **每 merge 一条** bridge §4 + backlog §11

### 人工门（刘哥）

- 飞书 T-03/T-04 卡片复验
- `git push --force` 到 main
- 恢复识图 / OpenRouter

---

## 4. 长期队列 MW-*（小颗粒 · 顺序执行）

> 规则：**只做第一条 `[ ]`**；完成改 `[x]` + 日期；卡住标 `[~]` + ISSUES 一行。

### 4A — 回填（一次性 · 2026-05-24 起）

| ID | 颗粒 | 做什么 | 成功标准 | 状态 |
|----|------|--------|----------|------|
| **MW-001** | bridge 回填 | §4 追加 05-24 行：A1 重启、A2 #2 关、P1-M03、GOD 合 main | ≥4 行新签收 | [x] 2026-05-24 |
| **MW-002** | backlog 表头 | 修 §10 WIP：下一条 **P1-M04**；P1-LONG-GOD → **[x]** | 与 §11 一致 | [x] 2026-05-24 |
| **MW-003** | D17 提示词 | §5 顶部加 **「已过期 → 读 ISSUES_WRITE_PLAN §6」** 横幅 | 新窗不误导 | [x] 2026-05-24 |
| **MW-004** | GH #19 | `gh issue comment 19` + close：附 PID 691521、health、skills 重启 | #19 closed | [x] 2026-05-24 |
| **MW-005** | ISSUES 同步 | `ISSUES.md` #3：若刘哥未复验保持 pending；补 **#19 已重启** 交叉引用 | 无矛盾 | [x] 2026-05-24 |
| **MW-006** | bridge §5 | 更新进度笔记（main tier0 245+2；Phase0 14/14；§11 Active） | §5 ≤8 行 | [x] 2026-05-24 |
| **MW-007** | GitHub 对账 | open issues #17-22 与 backlog §11/§8 各一行映射表写入 **本文件 §7** | §7 表存在 | [x] 2026-05-24 |

### 4B — 日常（Gateway 活着时 · 每 24h 最多一轮）

| ID | 颗粒 | 做什么 | 成功标准 | 状态 |
|----|------|--------|----------|------|
| **MW-D01** | 健康 | `curl /health` + `pgrep gateway/run.py` + TRUNCATE `grep -c` | TRUNCATE≤19；一行写 §4 | [ ] |
| **MW-D02** | ERROR 扫 | `grep ERROR agent.log \| tail -20` 归类 top3 | 新 P0 则 ISSUES；否则 §4「无新 P0」 | [ ] |
| **MW-D03** | 230099 | `grep 230099 gateway.log agent.log \| tail -5` | 有则 GATEWAY #9 [~]；无则 note | [ ] |

### 4C — 工程后（Cursor merge 触发 · 非 Mimir 主责）

| ID | 颗粒 | 负责 | 做什么 |
|----|------|------|--------|
| **MW-E01** | MAINLINE | Cursor | 一条 changelog |
| **MW-E02** | backlog §11 | Cursor | 子项 `[x]` |
| **MW-E03** | evolution | Cursor | `record_m6_evolution.sh` |
| **MW-E04** | bridge §4 | Cursor | merge 签收一行 |

### 4D — 周检（每 7 天或刘哥问进度时）

| ID | 颗粒 | 做什么 | 状态 |
|----|------|--------|------|
| **MW-W01** | Gateway 十条 | 刷新 `GATEWAY_STABILITY_BACKLOG.md` 状态列日期 | [ ] |
| **MW-W02** | Active≤3 | 审计 `MIMIR_ISSUES.md` 是否可归档 | [ ] |

### 4E — 人工门（只做提醒，不自动勾）

| ID | 内容 | 阻塞 |
|----|------|------|
| **MW-H01** | 飞书 T-03 空表头 | ISSUES #2/#3、#9 backlog |
| **MW-H02** | 飞书 T-04 双按钮 | ISSUES #3 |
| **MW-H03** | 刘哥 push 授权 | M-008 类 |

---

## 5. 与工程长任务的关系（并行但不混源）

```
刘哥不在时默认两条轨：

  Cursor 窗 → MIMIR_EXEC_BACKLOG §11 P1-LONG-MEM（P1-M04 起）
  Mimir 窗  → 本文件 §4 MW-*（写入/冒烟/对账）

禁止：Mimir 窗做 P1-M04 代码；Cursor 窗跳过 tier0。
```

| 轨 | 执行源 | 下一粒 |
|----|--------|--------|
| **工程** | §11 | **P1-M04** FTS5 |
| **写入** | §12 / 本文件 §4A | **MW-001** |

---

## 6. 新窗提示词（复制即用）

### 6A — Mimir 运维窗（飞书 / 本地 smoke / 写入）

```markdown
# Mimir 运维窗 — ISSUES 写入轨道

工作区：~/src/MimirAether
运行时：MIMIR_AETHER_HOME=~/.mimiraether
必读（顺序）：
1. docs/MIMIR_ISSUES_WRITE_PLAN.md（本轨道）
2. docs/MIMIR_LIU_CURSOR_BRIDGE.md §1 授权边界
3. docs/MIMIR_EXEC_BACKLOG.md §12

你是 **Mimir**：写入、grep、health、文档对账。禁止改 agent/gateway/mimir_cli/tools 行为；禁止 commit/push persistent.json。

## 本轮
- 只做 **§4 第一条 `[ ]` 的 MW-*** 一颗粒（当前：**MW-001**）。
- 完成后：更新 bridge §4 + 本表该 MW 行 `[x]` + 日期。
- 若需 Gateway 硬重启：一天最多一次；用 scripts/restart_gateway_hard.sh。

## 验证命令包
curl -s http://127.0.0.1:18999/health | head -c 200
pgrep -af 'gateway/run.py'
grep -c 'Level 3 TRUNCATE' ~/.mimiraether/logs/agent.log

## 回报（飞书或会话末尾）
MW-ID: 结果 | 更新了哪几个写入面 | 下一粒 MW-xxx | 需刘哥（≤3条）
```

### 6B — Cursor 工程窗（刘哥已授权 push/merge）

```markdown
# Cursor 工程窗 — Phase 1 Memory

工作区：~/src/MimirAether
必读：docs/MIMIR_EXEC_BACKLOG.md §11、docs/DEVELOPMENT_NORTH_STAR.md

## 本轮
Read §11，从 **P1-LONG-MEM 第一条 `[ ]`** 开始（当前 **P1-M04** FTS5）。
每次一颗粒；触达 agent/gateway/tools 后 ./run_ralph_tier0.sh。
合并后：MW-E01～E04（MAINLINE、§11、evolution、bridge §4）。

禁止：与 Mimir 抢改同一 docs 行（Mimir 负责 §12 MW-*，Cursor 负责 §11）。

成功：tier0 245+2 PASS + PR 或 main 上可指 commit。
```

### 6C — 刘哥 30 秒验收（可选）

飞书 T-03/T-04 按 `docs/mimir_prod_smoke.md` §2026-05-24；通过后回「T-03/T-04 pass」→ Mimir 窗做 MW-H 收尾。

---

## 7. GitHub ↔ Backlog 映射（MW-007 产出位）

| GH | 标题 | Backlog / 轨 | 关窗条件 |
|----|------|--------------|----------|
| #17 | P1-M04 FTS5 | §11 P1-M04 | 代码+基准+issue close |
| #18 | P1-M05 persistent | §11 P1-M05 | 路径烟测 |
| #19 | Gateway 重启 | MW-004 / A1 | **closed** 2026-05-24 |
| #20 | 单写者 icebox | §8 P3-0 | Phase 2 |
| #21 | D5 进化 icebox | §6 d5 | Phase 2 |
| #22 | D6 可观测 icebox | §6 d6 | Phase 2 |
| ~~#2~~ | openclaw 审计 | A2 | **closed** |

---

## 8. 修订

| 日期 | 说明 |
|------|------|
| 2026-05-24 | 初版：缺口审计 G1–G9；MW 队列；Mimir/Cursor 分轨提示词 |
