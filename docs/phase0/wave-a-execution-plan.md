# Wave A · IQ 5.5 — 完整工程粒与窗口提示词

> **拍板**：§20.3 **IQ-RUBRIC-55** ✅（2026-05-31）  
> **真源**：[`MIMIR_IQ_EVOLUTION_DIRECTION.md`](../MIMIR_IQ_EVOLUTION_DIRECTION.md) §1.5 · §2 阶段 1～2  
> **出口**：rubric **≥5.5** 或 **documented exception**（[`iq-scoring-rubric.md`](./iq-scoring-rubric.md)）  
> **禁止**：与 **Wave B（WM Phase0）** 混 PR · 改 `SESSION_SEARCH`/`MIMIR_CROSS_SESSION_RAG` 生产默认（除非刘哥另批）

**成绩单草稿**：[`wave-a-behavior-report-20260531.md`](./wave-a-behavior-report-20260531.md)

---

## 0. 谁在哪执行？（默认 **Cursor 新窗**）

| 执行面 | 做什么 | Wave A 里 |
|--------|--------|-----------|
| **Cursor 新窗** | 跑脚本、读 `~/src/MimirAether` + `~/.mimiraether` 日志/DB、改 docs、改 `agent/`、tier0、PR | **WA-A00～A08、A10～A12**（默认） |
| **刘哥（飞书）** | 真人 DM 发 3 条探针句（网关在线） | **仅 WA-A09 发话**（~2 min） |
| **Mimir（飞书 @）** | 可选：刘哥不想开 Cursor 时让 Mimir 做只读验收 | **非默认**；与 Cursor 二选一，勿重复 |

**为何上一版写满「Mimir」**：误把 bridge 里「Mimir = 冒烟/§4 签收」扩成「所有度量都通知飞书」。  
脚本与证据文档在 **本机仓库 + runtime home**，**Cursor 有 shell 就能做**，不必占用飞书轮次。

**签收**：每窗结束由 **Cursor** 在 `MIMIR_LIU_CURSOR_BRIDGE.md` **§4** 贴一行（或刘哥指定由 Mimir 贴时写清）。

---

## 0.1 一张图

```text
[Cursor: 单实例] → [Cursor: 周常度量] → [Cursor: 7d search + audit]
       → [Cursor: search-first / nudge / intent 工程] → [刘哥: 飞书3句] → [Cursor: 填 iqevo-30 + grep ok%]
       → [Cursor: rubric复评] → [Cursor: closeout]
```

**并行允许**：刘哥发飞书（A09）可与 Cursor 工程窗 A06～A08 并行；**禁止**跳过度量直接改 rubric 分数。

---

## 1. 工程粒总表（按顺序）

| 序 | ID | Owner | 对应 §1.5 | 任务 | 成功标准 | 状态 |
|:--:|-----|-------|-----------|------|----------|:----:|
| 0 | **WA-A00** | **Cursor**（Mimir 已验收轨完成） | 全表 | 刷新成绩单基线 | 更新 `wave-a-behavior-report-*.md` · **WA-A00 刷新** 节 | [x] |
| 1 | **WA-A01** | **Cursor** | Q7 | 单实例 gateway | `ensure_single_gateway.sh` → count=1 · health ok | [x] |
| 2 | **WA-A02** | **Cursor** | Q3 | 进化 eval 周常 | `run_evolution_eval.sh` exit **0** · JSON 路径进 bridge §4 | [x] |
| 3 | **WA-A03** | **Cursor** | Q4 | 工具质量周常 | `tool_quality_weekly.sh` 一行 · 或 documented 空 DB | [x] |
| 4 | **WA-A04** | **Cursor** | Q2 | 7d `session_search` 基线 | `session_search_usage_baseline.py` → `data/ops/session_search_baseline_7d.json` | [x] |
| 5 | **WA-A05** | **Cursor** | Q2 | search-first 审计 | `search_first_audit.py` → `iqevo-31-search-first-audit.md` + `.json` | [x] |
| 6 | **WA-A06** | **Cursor** | Q2·#5 | search-first **行为加固**（按需） | 审计违例率仍高时：强化 prompt/守卫；**每粒一 PR** · tier0 | [x] |
| 7 | **WA-A07** | **Cursor** | Q6·#8 | Intent 生产证据 | `MIMIR_INTENT_PREDICTOR` 默认开已接线；contract/日志证据 · **不宣称 ML 全量** | [x] |
| 8 | **WA-A08** | **Cursor** | #1·E3 | 对话内 **memory nudge** 最小移植 | 10 轮间隔 nudge（参照 Hermes）；日志可见 · tier0 | [x] |
| 9a | **WA-A09a** | **刘哥** | Q2 | 飞书 DM **发 3 条**探针 | 网关在线；见 iqevo-30 表 | [x] |
| 9b | **WA-A09b** | **Cursor** | Q2 | 读本机 log · **填** iqevo-30 | `agent.log` / tool 痕迹 + 表三行 PASS/FAIL | [x] |
| 10 | **WA-A10** | **Cursor** | Q3·#1 | 进化链 ok% 周常 | grep `post_analysis evolution` 7d · applied/ok · bridge 一行 | [x] |
| 11 | **WA-A11** | **Cursor** | Q1 | Rubric 复评 **IQ-EVO-38** | 重填 `iq-scoring-rubric.md` · **≥5.5** 或 exception 续期理由 | [x] |
| 12 | **WA-A12** | **Cursor** | 出口 | Wave A closeout | `wave-a-closeout.md` · bridge §4 · backlog §20.4 出口说明 | [x] |

**说明**

- **OPS-L2 飞书复验**：可与 WA-A09a 同轮顺带 `/new` → 发一句，**不挡** Cursor 工程窗。
- **可选 Mimir**：飞书 @「按 bridge Wave A 验收」= 只读对照，**不替代** Cursor 跑脚本/改 docs。
- **已有脚本**：见 [`docs/ops/evolution-eval-weekly.md`](../ops/evolution-eval-weekly.md)、[`tool-quality-weekly.md`](../ops/tool-quality-weekly.md)。
- **Python**：仓库内用 `~/src/MimirAether/.venv/bin/python`（系统 python 常缺依赖）。

---

## 2. 过线粗算（诚实 · 来自 rubric）

要到 **5.5** 通常需抬 **#1 学习能力**（3.5→≥5.0）和/或 **#8 意图**（3.5→≥5.5），或刘哥接受 **新 exception** 档位。  
Wave A 工程粒 **A06/A08** 对准 #1；**A07/A09** 对准 #8/Q2 行为。

---

## 3. Cursor 新窗口提示词（按序复制）

> **Workspace**：`~/src/MimirAether`（仓库根）。  
> 每窗 **只做表中一条**；回报 **bridge §4 一行** + 更新本表 `[x]`。  
> **仅 WA-A09a** 由刘哥在飞书完成（无 Cursor 窗）。

---

### 窗口 0 · Cursor — WA-A00 基线

```text
【角色】Cursor 新窗 · MimirAether（~/src/MimirAether）

【必读】docs/MIMIR_IQ_EVOLUTION_DIRECTION.md §1.5
docs/phase0/wave-a-execution-plan.md §0～§1
docs/phase0/wave-a-behavior-report-20260531.md

【本窗】WA-A00：刷新 behavior-report「基线」一节
- 列出 Q1～Q7 PASS/FAIL/部分 + 证据路径（可 Read ~/.mimiraether/logs、data/ops）
- 本窗只改 docs/phase0/*.md；不 push 除非刘哥要 commit

【回报】改动的 md 路径 + bridge §4 一行：WA-A00 baseline …
```

---

### 窗口 1 · Cursor — WA-A01 单实例（若已做可跳过）

```text
【角色】Cursor 执行窗 · MimirAether

【必读】docs/phase0/wave-a-execution-plan.md · WA-A01
scripts/ensure_single_gateway.sh

【本窗】确认 gateway 仅 1 个 python 进程；health ok
MIMIR_AETHER_HOME=~/.mimiraether ./scripts/ensure_single_gateway.sh

【禁止】WM Phase0 · 大范围 gateway 重构

【回报】bridge §4：WA-A01 gateway single pid=… health=ok
```

---

### 窗口 2 · Cursor — WA-A02 进化 eval

```text
【角色】Cursor 新窗 · MimirAether

【本窗】WA-A02 · Q3
cd ~/src/MimirAether
MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh
记录 latest/compare JSON 路径与 like/fts/semantic 命中率

【回报】bridge §4：WA-A02 evolution_eval exit=0 · latest=… · LIKE=… FTS=… semantic=…
```

---

### 窗口 3 · Cursor — WA-A03 工具质量

```text
【角色】Cursor 新窗 · MimirAether

【本窗】WA-A03 · Q4
cd ~/src/MimirAether
MIMIR_AETHER_HOME=~/.mimiraether ./scripts/tool_quality_weekly.sh
若无 DB 数据 → 在 docs/phase0 写 documented empty，不造假 ok%

【回报】bridge §4：WA-A03 tool_quality … 或 documented empty
```

---

### 窗口 4 · Cursor — WA-A04 + WA-A05 检索度量

```text
【角色】Cursor 新窗 · MimirAether

【本窗】WA-A04 + WA-A05 · Q2
cd ~/src/MimirAether
.venv/bin/python scripts/session_search_usage_baseline.py --days 7
.venv/bin/python scripts/search_first_audit.py   # 按 --help
更新 docs/phase0/iqevo-31-search-first-audit.md（及脚本输出的 json 若需）

【回报】bridge §4：WA-A04/A05 session_search_7d=… · search_first_audit=…
```

---

### 窗口 5 · Cursor — WA-A06 search-first 加固（条件触发）

```text
【角色】Cursor · 工程轨 Wave A

【前置】Read WA-A05 审计结果；仅当违例率仍高或生产 log 无 session_search 时做本窗

【必读】docs/MIMIR_IQ_EVOLUTION_DIRECTION.md §2 阶段1
agent/prompt_builder.py SESSION_SEARCH_GUIDANCE
tools/session_search_tool.py

【本窗】WA-A06：最小 diff 让「历史类问题」更易触发 session_search
- 可改 prompt 守卫或 intent 标签触发 search；禁止改生产 SESSION_SEARCH_BACKEND 默认
- 每粒一 commit · ./run_ralph_tier0.sh · 触达 agent 则 evolution_log 一行

【禁止】WM Phase0 · OPS-L2 无关重构

【回报】PR/commit · tier0 · bridge §4：WA-A06 search-first …
```

---

### 窗口 6 · Cursor — WA-A07 Intent 证据

```text
【角色】Cursor · Wave A

【本窗】WA-A07 · Q6/Q8
- 确认 agent/intent_predictor.py + prompt <intent-context> 生产路径
- 补/跑 contract 或 agent 烟测（若缺则最小测试）
- 更新 phase0 证据几行：不宣称 ML Predictor 全量上线

【禁止】夸大 rubric #8 分数

【回报】tier0 子集 · bridge §4：WA-A07 intent evidence …
```

---

### 窗口 7 · Cursor — WA-A08 memory nudge

```text
【角色】Cursor · Wave A

【必读】docs/MIMIR_IQ_EVOLUTION_DIRECTION.md §2 阶段2（Hermes nudge）
agent/core_loop.py 或 conversation 路径

【本窗】WA-A08：移植最小 memory nudge（建议每 10 user 轮一次，可 env 门控）
- 参照 Hermes conversation_loop nudge 节奏；默认开/关与现网一致
- tier0 + 小测试

【禁止】与 WA-A06 同 PR · 禁止 WM

【回报】bridge §4：WA-A08 nudge interval=… log=…
```

---

### 窗口 8a · 刘哥 — WA-A09a 飞书发话（非 Cursor）

刘哥在飞书 DM 对 Mimir 发 **3 条**（表见 `iqevo-30-feishu-smoke-evidence.md`）。  
网关需已 `ensure_single_gateway.sh`。可选：`/new` 后一句做 OPS-L2 顺带。

---

### 窗口 8b · Cursor — WA-A09b + WA-A10

```text
【角色】Cursor 新窗 · MimirAether

【前置】刘哥已完成 WA-A09a 三句话

【本窗】WA-A09b：读 MIMIR_AETHER_HOME 下 agent.log / 工具痕迹
- 填 docs/phase0/iqevo-30-feishu-smoke-evidence.md 三行 PASS/FAIL + 摘录

【本窗】WA-A10：grep 7d post_analysis evolution applied/ok
grep -E 'post_analysis evolution' ~/.mimiraether/logs/agent.log | tail …

【回报】bridge §4 两行：WA-A09b feishu3=… · WA-A10 evolution_ok%=…
```

---

### 窗口 9 · Cursor — WA-A11 rubric 复评

```text
【角色】Cursor 新窗 · MimirAether

【必读】docs/phase0/iq-scoring-rubric.md · 本计划表全部 [x] 证据

【本窗】WA-A11：诚实复评加权总分，只改 docs/phase0
- 目标 ≥5.5；否则 exception 续期（差多少、缺 #1/#8 什么）

【回报】iq-scoring-rubric 摘要 + bridge §4：WA-A11 rubric x.x/10 或 exception
```

---

### 窗口 10 · Cursor — WA-A12 closeout

```text
【角色】Cursor

【必读】docs/phase0/wave-a-execution-plan.md 全表 · wave-a-behavior-report

【本窗】WA-A12
- 写 docs/phase0/wave-a-closeout.md（证据链、是否达 5.5、未达则 exception）
- bridge §4 一行 · 不修改 §20.3 拍板勾

【回报】closeout 路径 · tier0 若本窗有代码则绿
```

---

## 4. Wave A 完成后

- 再开 **Wave B**：见 `world-model-agent-handoff.md` §7（独立 PR）。
- **§20.2 运维**（OPS-MW-REFRESH 等）可随时并行，不挡 A/B。
