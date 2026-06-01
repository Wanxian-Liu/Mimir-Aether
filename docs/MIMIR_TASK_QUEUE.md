# Mimir 任务清单（bridge · backlog · issues 合一）

> **读者**：Mimir（主执行）· 刘哥（拍板/飞书）· Cursor（工程轨，本清单 **不含** §20.1 写码粒）  
> **目的**：Cursor 流量不足时，Mimir 按 **单线第一条 `[ ]`** 自驱运维、证据与只读学习；避免 bridge/backlog/issues 三处真源漂移。  
> **真源优先级**：**§11 IQ #17**（有可执行 `[ ]`）> **§12 ENG-WF 工程链**（IQ 仅剩 BLOCK 或 §11 全 [x]）> **§10**（仅 SELF-LOOP `[ ]`）> §9（已闭合）> §6.1 周常 > §2/§3 归档 > backlog §20  
> **分工契约**：[`MIMIR_PRIMARY_EXECUTOR.md`](./MIMIR_PRIMARY_EXECUTOR.md)（Mimir 全做 · Cursor 只复核合 main）

**最近更新**：2026-06-02 · **§11 IQ-17 执行闭合**（IQ-14·CLR-B [x]）· 主链 → **§12 ENG-WF**

---

## 0. 每轮开场（复制给 Mimir）

```text
你是 Mimir 运维轨。本轮开始前必读（顺序）：

0) ./scripts/mimir_iq17_run_next.sh --dry-run → 若有可执行 IQ 粒，走 §11；否则 ./scripts/mimir_eng_run_next.sh --dry-run → §12
1) ~/.openclaw/workspace/CLAUDE.md — 行为准则（Think/Simplicity/Surgical/Goal-Driven）
2) ~/src/MimirAether/AGENTS.md — 仓库 vs MIMIR_AETHER_HOME、Ralph、M6
3) §11 或 §12 第一条 [ ] 的真源计划（IQ17_EXECUTION_PLAN 或 MIMIR_ENGINEERING_WORKFLOW.md）
4) ~/src/MimirAether/docs/MIMIR_IQ_EVOLUTION_DIRECTION.md — §0、§3.2 证据类型、§3.3 回报模板
5) ~/src/MimirAether/docs/MIMIR_LIU_CURSOR_BRIDGE.md — §1「@Mimir 必读」最新一段

纪律：
- **§10 大脑自治**（2026-06-01）：可改 agent|gateway|tools|tests；**每粒 commit+push**；见 BRAIN_AUTONOMY_CHAIN §2
- **元认知**：`[MIMIR_SKILL_ROUTE_NUDGE]` → 必须先 `skill_view`；**禁止**等刘哥说「继续下一粒」
- 禁止提交 data/persistent.json
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

## 1. 三源状态（快照 2026-06-01）

| 来源 | 状态 | 说明 |
|------|------|------|
| **本清单 §2/§3** | **全部 [x]** | Mimir 批跑完成；勿再从头扫 §2 |
| **backlog §20.2** | **4/4** | **CLR-B-FEISHU** [x] 2026-06-01 · `clr-b-feishu-closeout.md` |
| **backlog §20.3** | **EV-VISION-DEFER** [ ] | 搁置，非 Mimir 任务 |
| **backlog §20.1** | **3/3 [x]** | → **Cursor** / §20.4 / ISSUES |
| **issues #22** | icebox | M-ICE-22 已文档化 defer |
| **π-agent PI-L01～06** | **[x]** | 产出见 `docs/proposals/pi-learn-*.md` |

**周常重复（非「队列空」）**：每周可重跑 **M-WEEKLY-01～03**（不必改回 `[ ]`，bridge §4 记日期即可）。

**已闭合（勿再取任务）**：§20.1 工程 · Wave A/B/C Phase3 · D5-ADR · Horizon C · MI-AWAY · 本表 §2/§3 一次性粒。

---

## 2. Mimir 执行队列（一次性粒 · 已全部 [x]）

> **2026-06-01**：本节 **无待办 `[ ]`**。新任务由刘哥写入 §20.2 / §20.4 或新开 TASK_QUEUE 行。  
> 状态：`[ ]` 待做 · `[~]` 进行中/阻塞 · `[x]` 完成  
> 完成标准必须 **可命令复现**（见「验证」列）。

### 2A. 周常（重复）

| ID | 源 | 任务 | 验证 | 状态 |
|----|-----|------|------|------|
| **M-WEEKLY-01** | §20.2 OPS-EVAL-WEEKLY | 跑进化检索周常 | `MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh` → exit 0；记 latest JSON 路径 | [x] |
| **M-WEEKLY-02** | §20.2 OPS-MW-REFRESH | MW 轻量刷新 | 按 [`docs/OPERATIONS_GATEWAY.md`](./OPERATIONS_GATEWAY.md) / bridge MI-AWAY 口径；TRUNCATE=0 或无新 P0 | [x] |
| **M-WEEKLY-03** | P3-12 / iq-p3 | 进化 ok% 快照 | `MIMIR_AETHER_HOME=~/.mimiraether python3 scripts/iq_p3_evolution_ok_baseline.py`；对比 `data/ops/iq-p3-baseline.json` | [x] |

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
| **M-OPS-11** | CLR-B 预检 | Gateway #9 / 空表头 **上线前**检查 | `curl -s http://127.0.0.1:18999/health`；`rg 230099 ~/.mimiraether/logs/agent.log` 近 7d；空表头相关 ERROR 无新增 | [x] |
| **M-OPS-10** | CLR-B | **刘哥**飞书复验（Mimir 不代测） | 刘哥发话后 Mimir 只读 log：无新 230099；bridge §4「CLR-B 刘哥=PASS/FAIL」 | [x] |
| **M-OPS-20** | Gateway 十条 #2/#9 | 健康与错误率 | `mimir_ops(health_check)` 或文档等价命令；error_rate 与 bridge MI-AWAY-01 同口径 | [x] |
| **M-OPS-21** | 日常 | `/new` 后 key_decisions 仍可读 | 飞书或 CLI 一轮 `/new` + 问「列出 key_decisions」；截 log 一行 | [x] |

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
| **M-IQ-02** | MI-AWAY-11 | **先搜再答** 3 场景 | 3 个问题应触发 `session_search`；`rg session_search ~/.mimiraether/logs/agent.log` 计数 | [x] |
| **M-IQ-03** | OPS-L2 后续 | L2 `<retrieved-sessions>` 飞书侧证 | Feishu `/new` 后首条回复是否含检索块或 log 有 prefetch 命中 | [x] |
| **M-EVO-12** | P3-12 | 盯 **真实** evolution ok=1 | 排除 iq07/iq40/fb-sess；出现 `post_analysis evolution … ok=1` 且 session 为 UUID | [x] |
| **M-EVO-13** | tool_quality | top5 工具一行 | `python3 -m tools.tool_quality` 周常口径或文档命令；ok% 写入 bridge | [x] |

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
| **M-ICE-22** | GH #22 | D6 余债 **不实现** | Read ADR-007 + ADR-005；写 10 行「为何 defer」到 bridge 或 `docs/proposals/` | [x] |
| **M-BLOCK-01** | §20.3 | 识图 / OpenRouter | **不做**；刘哥未恢复 EV-VISION-DEFER 前仅记 OPENROUTER:absent | [x] 搁置 |
| **M-BLOCK-02** | bridge 历史 | 生产开关提案 | 仅当刘哥问时：整理「Chroma 增量 / hybrid 默认 / AUTO_EVOLVE 已开」状态表，**不擅自改 .env** | [x] |

---

## 3. π-agent（pi-mono）只读学习计划

> **源码（只读，禁止整库复制进 Mimir）**：`~/.openclaw/projects/pi-agent`（上游 [pi-mono](https://github.com/badlogicgames/pi-mono)）  
> **原则**：学 **模式**（agent 循环、工具状态、测试 harness、多模型抽象），在 Mimir 写 **提案** 交 Cursor，不直接粘贴 TS 进 `agent/`。

| 周次 | ID | 读本仓库路径 | 产出（Mimir 写） | 状态 |
|------|-----|--------------|------------------|------|
| 1 | **PI-L01** | `packages/agent/README.md` + `src/**/agent.ts`（入口） | `docs/proposals/pi-learn-01-agent-loop.md`：事件流 vs Mimir core_loop | [x] |
| 2 | **PI-L02** | `packages/agent` 工具执行与 state 序列化 | `pi-learn-02-tool-state.md`：对比 `execution_pipeline` / ExecutionRecorder | [x] |
| 3 | **PI-L03** | `packages/coding-agent/README.md` + `examples/` | `pi-learn-03-coding-agent-cli.md`：TUI/子 agent 与 Mimir CLI 边界 | [x] |
| 4 | **PI-L04** | `packages/ai` 多 provider 抽象 | `pi-learn-04-llm-providers.md`：对比 `auxiliary_client` / credential_pool | [x] |
| 5 | **PI-L05** | `packages/coding-agent/test/suite/harness.ts` | `pi-learn-05-test-harness.md`：可移植契约测想法（给 Cursor） | [x] |
| 6 | **PI-L06** | 复盘 + Mimir 对照表 | `pi-learn-06-synthesis.md`：3 条 **可立项** 改进（≤1 页） | [x] |

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

## 5. Cursor 专用（复核轨 · 不抢 §9）

| 动作 | 说明 |
|------|------|
| **扫 HANDOFF** | bridge §4 含 `HANDOFF <ID> ready` → 读 `docs/mimir-handoff/<ID>/` |
| **独立 tier0** | 重跑 `./run_ralph_tier0.sh` 后再 commit/push |
| **合 main** | M6 · PR · Gateway 重启记在 closeout |
| **方向** | 只改 bridge §1 / 计划 docs；**不**替 Mimir 实现 §9 第一条 |

**Cursor 新窗一句**

```text
复核模式：git pull · bridge §4 找 HANDOFF * ready · 读 mimir-handoff · tier0 · commit/push。
不抢 TASK_QUEUE §9 第一条 [ ]。方向问题写 bridge §1。
```

---

## 9. 主执行轨（Mimir 做 · Cursor 复核）— 只认第一条 `[ ]`

> **交付**：每粒结束建 `docs/mimir-handoff/<ID>/`（见 [`MIMIR_PRIMARY_EXECUTOR.md`](./MIMIR_PRIMARY_EXECUTOR.md) §4）+ bridge §4：`HANDOFF <ID> ready`。  
> **来源**：PI-L06 立项 · Wave A 余债 · Phase3 ok% · backlog 改派。

| ID | 优先级 | 任务 | Mimir 交付 | Cursor 复核 | 状态 |
|----|--------|------|------------|-------------|------|
| **ENG-PI06-01** | P0 | **测试 Harness**（PI-L06 #1） | `tests/conftest.py` 工厂 + FauxLlm + 迁移 2～3 测例 · tier0 绿 · handoff | **Cursor merged** · tier0 **681** | [x] |
| **ENG-SF-01** | P0 | **先搜再答**（Wave A WA-A05/A06） | preemptive nudge + audit 脚本 · handoff | **Cursor merged** · tier0 **681** · **Gateway 需重启** | [x] |
| **ENG-EVO-01** | P1 | **真实 session evolution ok=1** | 归因 ok=0 + detail 日志缺口修复 · handoff | **Cursor merged** · tier0 **681** | [x] |
| **ENG-TOOL-01** | P2 | 工具执行事件流（PI-L06 #2） | `tool_event_emitter` + agent_loop hooks · handoff | **Cursor merged** · tier0 **681** | [x] |
| **ENG-CLI-01** | P2 | CLI `--one-shot`（PI-L06 #3） | `cmd_one_shot` + 5 测例 · handoff | **Cursor merged** · tier0 **681** | [x] |
| **ENG-ICE-22** | P3 | GH #22 文档 | `docs/proposals/d6-observability-defer.md`（若未写）· 无代码 | docs-only 可直接 [x] | [x] |

**ENG-PI06-01 提示词**

```text
任务 ENG-PI06-01（M-ENG）：实现 PI-L06 第 1 条「统一测试 Harness」。
读 docs/proposals/pi-learn-06-synthesis.md + pi-learn-05-test-harness.md。
在 tests/conftest.py 增加 create_mimir_harness() 与轻量 FauxLlm；迁移 2～3 个现有测试示范。
自证：./run_ralph_tier0.sh 末行 PASS 数。
交付：docs/mimir-handoff/ENG-PI06-01/{SUMMARY,VERIFY,FILES,REVIEW}.md
bridge §4：HANDOFF ENG-PI06-01 ready · tier0=…
禁止 git push。
```

**ENG-SF-01 提示词**

```text
任务 ENG-SF-01：降低「历史类问题未 session_search」违规率（见 bridge WA-A05/A06）。
先只读复现：跑文档中的 audit 命令，贴 filtered_violation_rate。
再最小改动（prompt_builder 或 intent）：目标 filtered 违规显著下降，tier0 仍绿。
交付 handoff ENG-SF-01；禁止改 SESSION_SEARCH_BACKEND 生产默认。
```

---

## 6. 完成定义（整表）

- **Mimir 运维轨**：§2 全部 **[x]** ✅（2026-06-01）  
- **π 学习轨**：**PI-L06** + `docs/proposals/pi-learn-*.md` ✅  
- **刘哥轨**：**CLR-B-FEISHU** — **[x] 2026-06-01**（见 `docs/phase0/clr-b-feishu-closeout.md`）

### 6.1 队列闭合后 Mimir 做什么

| 模式 | 频率 | 动作 |
|------|------|------|
| **周常** | 每周 1 次 | 重跑 M-WEEKLY-01～03 三命令 + bridge §4 一行（不必改表为 `[ ]`） |
| **待命** | 刘哥点名 | bridge §1 新条或 §20.2 新粒 |
| **禁止** | — | 无新授权不得重开 §2 已 [x] 粒「凑工作量」 |

---

## 10. 自我完善链（Mimir 全自治）

> **真源**：[`MIMIR_SELF_IMPROVEMENT_CHAIN.md`](./MIMIR_SELF_IMPROVEMENT_CHAIN.md) · **§5 开场复制到飞书**  
> **下一粒**：`./scripts/mimir_self_run_next.sh --dry-run`  
> **纪律**：第一条 `[ ]` → 做完 **立刻**下一粒；**禁止**问「要不要继续」

| ID | 波次 | 任务 | 状态 |
|----|------|------|------|
| **SELF-00** | A | baseline + gateway + tier0 | [x] |
| **SELF-01** | A | 路由冒烟 3 场景 | [x] |
| **SELF-02** | A | 扩展 skill_scenario_router | [x] |
| **SELF-03** | A | audit_skill_usage.py | [x] |
| **SELF-04** | A | brain_metrics_snapshot.py | [x] |
| **SELF-05** | A | 更新 self-audit 技能 | [x] |
| **SELF-06** | A | 禁止等继续（文档） | [x] |
| **SELF-07** | A | mimir_self_run_next.sh | [x] |
| **SELF-08** | B | monitor 真/假阳性 | [x] |
| **SELF-09** | B | memory 固化冲动 | [x] |
| **SELF-10** | B | FEEDBACK / AUTO_EVOLVE | [x] |
| **SELF-11** | C | preemptive search | [x] |
| **SELF-12** | C | nudge 契约 | [x] |
| **SELF-13** | C | search-first 审计 | [x] |
| **SELF-14** | C | VoE + WM | [x] |
| **SELF-15** | C | evolution eval | [x] |
| **SELF-16** | C | rubric | [x] |
| **SELF-17** | C | closeout M1～M6 | [x] |
| **SELF-LOOP** | D | 每周周报 | [ ] |

---

## 11. IQ #17 提升链（Mimir 主执行 · Cursor 指挥）

> **真源**：[`MIMIR_IQ17_EXECUTION_PLAN.md`](./MIMIR_IQ17_EXECUTION_PLAN.md) · **ISSUES** #17 · **下一粒**：`./scripts/mimir_iq17_run_next.sh --dry-run`  
> **纪律**：只认第一条 `[ ]`；未拍板项见 `docs/phase0/iq17-liu-decisions.md`；**禁止**飞书内 restart gateway

| ID | 波次 | 任务 | 状态 |
|----|------|------|------|
|| **IQ-00** | 0 | 读真源 + pull + health | [x] |
|| **IQ-00B** | 0 | Cursor PREREQ 登记 | [x] |
|| **IQ-01** | 0 | tier0 基线 | [x] |
|| **IQ-02** | 0 | 验证 SELF-11 已部署 | [x] |
|| **IQ-03** | 0 | iq17-baseline.md | [x] |
|| **IQ-04** | 1 | #16 方向 bridge 一行 | [x] |
|| **IQ-05** | 1 | 拍板表 + 飞书 @刘哥 | [x] |
|| **IQ-06** | 1 | 同步 ISSUES #16/#17 | [x] |
|| **IQ-10** | 2 | A prompt 先搜再答 | [x] |
|| **IQ-11** | 2 | WM B1 VoE LEARNING | [x] |
|| **IQ-12** | 2 | WM B2 RECALL | [ ] BLOCK: WM-Q2=每步问我+B1<3d, skip |
|| **IQ-13** | 2 | C AUTO_EVOLVE | [x] |
| **IQ-14** | 2 | 飞书冒烟 3 场景 | [x] 🚢 IQ-55 3P · `iq17-feishu-smoke.md` |
| **IQ-15** | 2 | search_first 审计复跑 | [x] |
|| **IQ-20** | 3 | brain_metrics 观察 | [x] |
|| **IQ-21** | 3 | evolution eval | [x] |
|| **IQ-22** | 3 | WM 日志检查 | [x] |
|| **IQ-23** | 3 | skill_view 7d 审计 | [x] |
|| **IQ-24** | 3 | 观察窗 bridge 周报 | [x] |
|| **IQ-25** | 3 | brain_metrics 增 skill_view_7d | [x] 🚢 6397160 |
|   | **IQ-30** | 4 | WM B3 REPLAN_CTX | [x] 🚢 env by 刘哥 |
||| **IQ-31** | 4 | WM B4 预测器接线 | [x] 🚢 a0dc323 |
||| **IQ-32** | 4 | D intent fallback | [x] 🚢 a0dc323 |
||| **IQ-33** | 4 | D 与 preemptive 契约测 | [x] 🚢 a0dc323 |
||| **IQ-34** | 4 | P1 handoff 汇总 tier0 | [x] 🚢 a0dc323 |
|| **IQ-40** | 5 | E nudge 设计稿 | [x] 🚢 design |
|| **IQ-41** | 5 | F 并行工具设计稿 | [x] 🚢 design |
|| **IQ-42** | 5 | Cursor backlog 建议表 | [x] 🚢 proposal |
|| **IQ-45** | 6 | iq17-closeout + IQ-M1～M6 | [x] 🚢 closeout |

---

## 12. 工程工作流链（ENG-WF · Mimir 主执行）

> **真源**：[`MIMIR_ENGINEERING_WORKFLOW.md`](./MIMIR_ENGINEERING_WORKFLOW.md) · 评估 [`output/2026-06-01-MIMIR评估与改造方向.md`](../output/2026-06-01-MIMIR评估与改造方向.md)  
> **下一粒**：`./scripts/mimir_eng_run_next.sh --dry-run`  
> **纪律**：只认第一条 **`[ ]` 且非 BLOCK`**；BLOCK 行 SKIP 并 bridge 记原因；做完 **立刻**下一粒

| ID | 波次 | 任务 | Owner | 状态 |
|----|------|------|-------|------|
| **ENG-WF-00** | 0 | 基线 health + tier0 + eng-wf-00-baseline.md | Mimir | [x] ✅ 刘哥 |
| **ENG-WF-01** | 1 | systemd stop/disable mimiraether | **刘哥** | [x] ✅ 2026-06-02 inactive/disabled · `eng-wf-ops-gateway.md` |
| **ENG-WF-02** | 1 | OPERATIONS §5 单 Owner 文档 | Mimir | [x] ✅ |
| **ENG-WF-03** | 1 | 编造 spec（eng-wf-fabrication-spec.md） | Mimir | [x] ✅ |
| **ENG-WF-04** | 1 | 编造契约测 test_eng_wf_fabrication_guard.py | Mimir | [x] ✅ |
| **ENG-WF-05** | 1 | tool result 优先级 / 测例 | Mimir | [x] ✅ |
| **ENG-WF-06** | 1 | 波次 1 closeout | Mimir | [x] ✅ |
| **ENG-WF-10** | 2 | coverage_baseline.sh + baseline md | Mimir | [ ] |
| **ENG-WF-11** | 2 | 覆盖率 ratchet 文档（非 50% 悬崖） | Mimir | [ ] |
| **ENG-WF-12** | 2 | tool_registry cov ≥80% | Mimir | [ ] |
| **ENG-WF-13** | 2 | search_first + credential 各 +3 测 | Mimir | [ ] |
| **ENG-WF-14** | 2 | 波次 2 closeout + 覆盖率对比 | Mimir | [ ] |
| **ENG-WF-20** | 3 | 上下文三套 inventory（只读） | Mimir | [ ] |
| **ENG-WF-21** | 3 | turn_loop 抽 1 函数 + 单测 | Mimir | [ ] |
| **ENG-WF-22** | 3 | FauxLlm 再迁 2 测 | Mimir | [ ] |
| **ENG-WF-90** | 4 | eng-wf-closeout + ENG-WF-M1～M6 | Mimir | [ ] |

**§11 剩余 BLOCK（仅占 ENG-WF 下一粒之外的拍板项）**

| ID | 说明 |
|----|------|
| IQ-12 | 刘哥确认后 shell：`MIMIR_WM_VOE_RECALL=1` + gateway 重启（WM-Q2=每步问我，**故意未开**） |

---

## 7. 修订日志

| 日期 | 摘要 |
|------|------|
| 2026-06-02 | IQ-14 [x] · CLR-B [x] · `iq17-feishu-smoke.md` + `clr-b-feishu-closeout.md`（Cursor 文档对齐） |
| 2026-06-01 | §12 ENG-WF 工程工作流（`MIMIR_ENGINEERING_WORKFLOW.md` + `mimir_eng_run_next.sh`）· IQ 后默认主链 |
| 2026-06-01 | §11 IQ #17 执行链（`MIMIR_IQ17_EXECUTION_PLAN.md`）· 优先级高于 §10 LOOP |
| 2026-06-01 | IQ-31/32/33/34 Cursor 合入（`a0dc323`）+ IQ-40/41 design + IQ-42 backlog + IQ-45 closeout · 4.9→5.2 |
| 2026-06-01 | §10 大脑自治链 BRAIN-00～10 + LOOP · 全自治 push |
| 2026-06-01 | §9 主执行轨 · MIMIR_PRIMARY_EXECUTOR · ENG-* 改派 Mimir |
| 2026-06-01 | §2/§3 全 [x] · 闭合模式 §6.1 · §1 快照更新 |
| 2026-05-31 | 初版：三源合并 · Mimir 队列 · π-agent 六周只读课 · 提示词块 |
