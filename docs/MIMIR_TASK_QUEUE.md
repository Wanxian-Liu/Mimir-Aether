# Mimir 任务清单（bridge · backlog · issues 合一）

> **读者**：Mimir（主执行）· 刘哥（拍板/飞书）· Cursor（工程轨，本清单 **不含** §20.1 写码粒）  
> **目的**：Cursor 流量不足时，Mimir 按 **单线第一条 `[ ]`** 自驱运维、证据与只读学习；避免 bridge/backlog/issues 三处真源漂移。  
> **真源优先级**：本文件执行顺序 > [`MIMIR_EXEC_BACKLOG.md`](./MIMIR_EXEC_BACKLOG.md) §20.2 > [`MIMIR_LIU_CURSOR_BRIDGE.md`](./MIMIR_LIU_CURSOR_BRIDGE.md) §4 签收  

**最近更新**：2026-05-31  

---

## 0. 每轮开场（复制给 Mimir）

```text
你是 Mimir 运维轨。本轮开始前必读（顺序）：

1) ~/.openclaw/workspace/CLAUDE.md — 行为准则（Think/Simplicity/Surgical/Goal-Driven）
2) ~/src/MimirAether/AGENTS.md — 仓库 vs MIMIR_AETHER_HOME、Ralph、M6
3) ~/src/MimirAether/docs/MIMIR_TASK_QUEUE.md — 只认「执行队列」第一条 [ ]
4) ~/src/MimirAether/docs/MIMIR_IQ_EVOLUTION_DIRECTION.md — §0、§3.2 证据类型、§3.3 回报模板
5) ~/src/MimirAether/docs/MIMIR_LIU_CURSOR_BRIDGE.md — §1「@Mimir 必读」最新一段

纪律：
- 默认轨 A（提案/验收/只读学习）；改 agent|gateway|tools|mimir_cli 须 bridge §1 授权轨 B 或记 ISSUES 交 Cursor §20.1
- 禁止 git push；禁止提交 data/persistent.json
- 每粒结束：bridge §4 一行 +（若触达进化指标）更新 ~/.mimiraether/data/ops/ 下 JSON

回报必须用 MIMIR_IQ_EVOLUTION_DIRECTION §3.3 模板（子项 ID 填本表任务号）。
```

### Superpowers（需要拆步骤时）

| 技能 | 路径（本机） | 何时用 |
|------|----------------|--------|
| executing-plans | `~/.cursor/plugins/cache/cursor-public/superpowers/b7a8f76985f1e93e75dd2f2a3b424dc731bd9d37/skills/executing-plans/SKILL.md` | 多步任务按检查点执行 |
| verification-before-completion | 同上目录 `verification-before-completion/SKILL.md` | 声称完成前必须有命令输出 |
| systematic-debugging | 同上目录 `systematic-debugging/SKILL.md` | health/飞书/进化异常排查 |

Mimir **不运行** superpowers 子代理；把技能当 **检查清单** 读一遍再动手。

---

## 1. 三源未竟事项（快照 2026-05-31）

| 来源 | 仍 open / 需跟进 | 本清单映射 |
|------|------------------|------------|
| **backlog §20.2** | **CLR-B-FEISHU** [ ] | **M-OPS-10**（刘哥飞书）+ **M-OPS-11**（Mimir 预检） |
| **backlog §20.3** | **EV-VISION-DEFER** [ ] 搁置 | **M-BLOCK-01**（勿做，等刘哥） |
| **backlog §20.1** | 工程轨 **3/3 [x]** | → **Cursor**，不进 Mimir 队列 |
| **issues** | **#22** icebox D6 余债 | **M-ICE-22**（只读状态说明） |
| **issues** | **#21** | [x] 已 close（D5-ADR） |
| **Phase3 closeout** | P3-12 生产 ok% 观测窗 | **M-EVO-12**（周常） |
| **MI-AWAY / bridge** | 先搜再答 1/3、L2 `<retrieved-sessions>` 侧证 | **M-IQ-02**、**M-IQ-03** |
| **bridge 历史** | Chroma 增量 / hybrid 默认 / 生产 AUTO_EVOLVE 等 | **M-BLOCK-02**（须刘哥拍板，Mimir 只提案） |

**已闭合（勿再取任务）**：§20.1 工程 · Wave A/B/C Phase3 · D5-ADR 刘哥签收 · Horizon C 17/17 · MI-AWAY 16/16。

---

## 2. Mimir 执行队列（只认第一条 `[ ]`）

> 状态：`[ ]` 待做 · `[~]` 进行中/阻塞 · `[x]` 完成  
> 完成标准必须 **可命令复现**（见「验证」列）。

### 2A. 周常（重复）

| ID | 源 | 任务 | 验证 | 状态 |
|----|-----|------|------|------|
| **M-WEEKLY-01** | §20.2 OPS-EVAL-WEEKLY | 跑进化检索周常 | `MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh` → exit 0；记 latest JSON 路径 | [ ] |
| **M-WEEKLY-02** | §20.2 OPS-MW-REFRESH | MW 轻量刷新 | 按 [`docs/OPERATIONS_GATEWAY.md`](./OPERATIONS_GATEWAY.md) / bridge MI-AWAY 口径；TRUNCATE=0 或无新 P0 | [ ] |
| **M-WEEKLY-03** | P3-12 / iq-p3 | 进化 ok% 快照 | `MIMIR_AETHER_HOME=~/.mimiraether python3 scripts/iq_p3_evolution_ok_baseline.py`；对比 `data/ops/iq-p3-baseline.json` | [ ] |

**M-WEEKLY-01 提示词**

```text
任务 M-WEEKLY-01：只跑 eval，不改代码。
cd ~/src/MimirAether && MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh
把 pass/fail、compare JSON 路径、LIKE/FTS/semantic 三率写入 bridge §4 一行。
失败则 grep agent.log 末 50 行 evolution，记 ISSUES 标题草案（勿 push）。
```

---

### 2B. 运维与飞书证据（优先）

| ID | 源 | 任务 | 验证 | 状态 |
|----|-----|------|------|------|
| **M-OPS-11** | CLR-B 预检 | Gateway #9 / 空表头 **上线前**检查 | `curl -s http://127.0.0.1:18999/health`；`rg 230099 ~/.mimiraether/logs/agent.log` 近 7d；空表头相关 ERROR 无新增 | [ ] |
| **M-OPS-10** | CLR-B | **刘哥**飞书复验（Mimir 不代测） | 刘哥发话后 Mimir 只读 log：无新 230099；bridge §4「CLR-B 刘哥=PASS/FAIL」 | [ ] |
| **M-OPS-20** | Gateway 十条 #2/#9 | 健康与错误率 | `mimir_ops(health_check)` 或文档等价命令；error_rate 与 bridge MI-AWAY-01 同口径 | [ ] |
| **M-OPS-21** | 日常 | `/new` 后 key_decisions 仍可读 | 飞书或 CLI 一轮 `/new` + 问「列出 key_decisions」；截 log 一行 | [ ] |

**M-OPS-11 提示词**

```text
任务 M-OPS-11：为刘哥 CLR-B 飞书复验准备证据包（你不发飞书消息）。
1) health: curl -s http://127.0.0.1:18999/health | head -c 400
2) 230099: rg -c 230099 ~/.mimiraether/logs/agent.log 或近 7d 时间窗
3) 空表头：rg -i "table|header|列" ~/.mimiraether/logs/agent.log | tail -5
输出三段摘要到 bridge §4，并写 docs/phase0/ 下 5 行 md 备忘（可选）。
```

**M-OPS-10 提示词（给刘哥，可转发）**

```text
刘哥 CLR-B：请在飞书对 Mimir 发 1～2 轮验收——
① 要一张「只有表头、无数据行」的表（复现历史 #9）
② 任意正常对话一轮，看是否出现 230099
通过后回 bridge 一句「CLR-B PASS」；Mimir 只负责读 log 核对。
```

---

### 2C. 智商/进化证据（提案轨 A）

| ID | 源 | 任务 | 验证 | 状态 |
|----|-----|------|------|------|
| **M-IQ-02** | MI-AWAY-11 | **先搜再答** 3 场景 | 3 个问题应触发 `session_search`；`rg session_search ~/.mimiraether/logs/agent.log` 计数 | [ ] |
| **M-IQ-03** | OPS-L2 后续 | L2 `<retrieved-sessions>` 飞书侧证 | Feishu `/new` 后首条回复是否含检索块或 log 有 prefetch 命中 | [ ] |
| **M-EVO-12** | P3-12 | 盯 **真实** evolution ok=1 | 排除 iq07/iq40/fb-sess；出现 `post_analysis evolution … ok=1` 且 session 为 UUID | [ ] |
| **M-EVO-13** | tool_quality | top5 工具一行 | `python3 -m tools.tool_quality` 周常口径或文档命令；ok% 写入 bridge | [ ] |

**M-IQ-02 提示词**

```text
任务 M-IQ-02：3 场景 session_search 冒烟（生产 Gateway，勿改代码）。
场景建议：
1) 「上次 IR-20260520 我们做到哪一步？」
2) 「继续上次 gateway 稳定性」
3) 「查 key_decisions 里关于进化 ok% 的条目」
每轮后：rg "session_search|post_analysis" ~/.mimiraether/logs/agent.log | tail -3
回报 §3.3：3 轮中几轮触发 search、session_id、是否先搜后答。
```

**M-EVO-12 提示词**

```text
任务 M-EVO-12：观测生产进化成功率（ADR-008 路径 A 已上线）。
读 ~/.mimiraether/data/ops/iq-p3-baseline.json 与 agent.log 中 post_analysis evolution 行。
目标：排除测试 session 后 ok_pct 上升或出现 ok=1 的真实 session。
若无样本：在 bridge 说明「需真实带 errors 的 close」，勿宣称达标。
```

---

### 2D. Icebox / 文档（只读）

| ID | 源 | 任务 | 验证 | 状态 |
|----|-----|------|------|------|
| **M-ICE-22** | GH #22 | D6 余债 **不实现** | Read ADR-007 + ADR-005；写 10 行「为何 defer」到 bridge 或 `docs/proposals/` | [ ] |
| **M-BLOCK-01** | §20.3 | 识图 / OpenRouter | **不做**；刘哥未恢复 EV-VISION-DEFER 前仅记 OPENROUTER:absent | [x] 搁置 |
| **M-BLOCK-02** | bridge 历史 | 生产开关提案 | 仅当刘哥问时：整理「Chroma 增量 / hybrid 默认 / AUTO_EVOLVE 已开」状态表，**不擅自改 .env** | [ ] |

---

## 3. π-agent（pi-mono）只读学习计划

> **源码（只读，禁止整库复制进 Mimir）**：`~/.openclaw/projects/pi-agent`（上游 [pi-mono](https://github.com/badlogicgames/pi-mono)）  
> **原则**：学 **模式**（agent 循环、工具状态、测试 harness、多模型抽象），在 Mimir 写 **提案** 交 Cursor，不直接粘贴 TS 进 `agent/`。

| 周次 | ID | 读本仓库路径 | 产出（Mimir 写） | 状态 |
|------|-----|--------------|------------------|------|
| 1 | **PI-L01** | `packages/agent/README.md` + `src/**/agent.ts`（入口） | `docs/proposals/pi-learn-01-agent-loop.md`：事件流 vs Mimir core_loop | [ ] |
| 2 | **PI-L02** | `packages/agent` 工具执行与 state 序列化 | `pi-learn-02-tool-state.md`：对比 `execution_pipeline` / ExecutionRecorder | [ ] |
| 3 | **PI-L03** | `packages/coding-agent/README.md` + `examples/` | `pi-learn-03-coding-agent-cli.md`：TUI/子 agent 与 Mimir CLI 边界 | [ ] |
| 4 | **PI-L04** | `packages/ai` 多 provider 抽象 | `pi-learn-04-llm-providers.md`：对比 `auxiliary_client` / credential_pool | [ ] |
| 5 | **PI-L05** | `packages/coding-agent/test/suite/harness.ts` | `pi-learn-05-test-harness.md`：可移植契约测想法（给 Cursor） | [ ] |
| 6 | **PI-L06** | 复盘 + Mimir 对照表 | `pi-learn-06-synthesis.md`：3 条 **可立项** 改进（≤1 页） | [ ] |

**PI-L01 提示词**

```text
任务 PI-L01（只读 pi-agent，不写 Mimir 代码）：
1) Read ~/.openclaw/projects/pi-agent/packages/agent/README.md
2) 浏览 packages/agent/src 主入口（Agent 类、subscribe 事件）
3) 对照 ~/src/MimirAether/agent/core_loop.py 与 execution_pipeline（各列 5 条异同）
产出 ~/src/MimirAether/docs/proposals/pi-learn-01-agent-loop.md（≤80 行）
禁止：复制 TS 文件进 Mimir；禁止 push
完成：bridge §4 一行「PI-L01 done + 提案路径」
```

**PI-L06 提示词**

```text
任务 PI-L06：读完 PI-L01～05 备忘录后写 synthesis。
输出 docs/proposals/pi-learn-06-synthesis.md 结构：
- 可借鉴 3 条（带 pi 路径 + Mimir 落点）
- 明确不做 3 条（版权/复杂度/已有 ADR）
- 请 Cursor 立项 1 条（若有）：ISSUES 标题 + 验收命令
```

---

## 4. 刘哥专用（Mimir 勿代劳）

| ID | 事项 | Mimir 角色 |
|----|------|------------|
| L-01 | **CLR-B-FEISHU** 飞书发话验收 | 只做 M-OPS-11 预检 + 事后 log 核对 |
| L-02 | **EV-VISION-DEFER** 恢复识图 | 未恢复前禁止测 OpenRouter/vision |
| L-03 | 生产 **SESSION_SEARCH_BACKEND** / Chroma 增量 / 1c 等 | 仅准备对比表，等拍板 |

---

## 5. Cursor 专用（不进 Mimir 队列）

| 来源 | 说明 |
|------|------|
| backlog **§20.1** | 工程轨已空；新工程粒由刘哥开 §20.4 或 ISSUES |
| Horizon Wave 10+ | [`superpowers/plans/2026-05-27-horizon-c-master-iteration.md`](./superpowers/plans/2026-05-27-horizon-c-master-iteration.md) — Cursor + tier0 |
| 进化 ok% **代码**修复 | 真实 session `ok=0` 归因 → Cursor + ADR-008 |

**Cursor 新窗一句（保留给刘哥转发）**

```text
Read backlog §20.1 第一条 [ ]（若空则 §20.4 或 ISSUES）。
git pull · ./run_ralph_tier0.sh · 触达 agent/gateway/tools 则 record_m6_evolution.sh。
Mimir 并行只做 docs/MIMIR_TASK_QUEUE.md，勿抢 §20.1。
```

---

## 6. 完成定义（整表）

- **Mimir 运维轨**：§2 全部 **[x]** 或明确标 **[~] 阻塞**（写清缺刘哥/Cursor 哪一项）  
- **π 学习轨**：**PI-L06** synthesis 已交付且 bridge 有签收  
- **刘哥轨**：CLR-B 飞书 PASS 写入 backlog §20.2 `[x]`  

---

## 7. 修订日志

| 日期 | 摘要 |
|------|------|
| 2026-05-31 | 初版：三源合并 · Mimir 队列 · π-agent 六周只读课 · 提示词块 |
