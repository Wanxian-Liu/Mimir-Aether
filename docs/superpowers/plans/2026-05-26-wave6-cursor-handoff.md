# Wave 6 — Cursor 新窗执行手册（Superpowers）

> **给刘哥**：每个灰框 = **新开一个 Cursor 对话**，整段粘贴发送。一次只做 **一个 IQ-EVO-xx**。  
> **给 Agent**：必须先 Read 本页 **§0 主上下文**，再执行对应 **§N**；用 `executing-plans` + `verification-before-completion`；结束回报 bridge §4 一行。

**Goal：** 刘哥的大模型不适合跑 backlog 颗粒 → **Cursor 代执行** §15 Wave 6（IQ-EVO-28～39），直至 rubric ≥5.5 或 documented exception。

**Architecture：** 每粒独立 PR/提交；`./run_ralph_tier0.sh` 为 merge gate；触达 `agent|gateway|tools` 时 `./scripts/record_m6_evolution.sh`。

**Tech Stack：** Python 3.12 · `$MIMIR_AETHER_HOME=~/.mimiraether` · 仓库 **`~/src/MimirAether/`**（勿用 `~/.openclaw/projects/MimirAether`）

**Out of scope（未过门禁前）：** 生产 `MIMIR_AUTO_EVOLVE=1` · Unified Plan **1c** 实现 · 提交 `data/persistent.json`

**任务制门禁真源：** [`docs/phase0/iqevo-evolution-gates.md`](../../phase0/iqevo-evolution-gates.md) — **档位 A 已 [x]**；staging 开 AUTO_EVOLVE 需刘哥确认后做 **档位 B**。

---

## §0 主上下文（每个新窗先读，不必重复粘贴）

```text
仓库：~/src/MimirAether
运行时：MIMIR_AETHER_HOME=~/.mimiraether（与 HERMES_HOME 对齐）
真源：docs/MIMIR_EXEC_BACKLOG.md §15 Wave 6 · docs/phase0/p2-long-iqevo-wave6-qualified-agent.md
方向：docs/MIMIR_IQ_EVOLUTION_DIRECTION.md（当前智商 4.7/10，合格线 5.5）
协作：docs/MIMIR_LIU_CURSOR_BRIDGE.md

硬约束：
- 禁止 MIMIR_AUTO_EVOLVE=1（除非刘哥在 bridge §1 明文授权）
- 禁止 Unified Plan 1c（全量 DecisionRing/Compressor 学习）
- 每粒结束：./run_ralph_tier0.sh 全绿；触达 agent/gateway/tools 则 record_m6_evolution.sh
- 只改与本粒相关的文件（surgical）

Superpowers 链：
1. Announce: using executing-plans
2. 只做 backlog 指定 ID 一行
3. verification-before-completion 后再标 [x]
4. 更新 backlog 状态 + bridge §4 一行（模板见方向文档 §3.3）
```

---

## §28 · IQ-EVO-28（方向文档真源）

**状态：** 若 `MIMIR_IQ_EVOLUTION_DIRECTION.md` §1.1 已是 **4.7/10**、§1.5 合格检查表存在 → 仅核对并标 backlog `[x]`。

```text
【IQ-EVO-28 · 新窗执行】

Read §0 主上下文（docs/superpowers/plans/2026-05-26-wave6-cursor-handoff.md）。

任务：IQ-EVO-28 — 更新 docs/MIMIR_IQ_EVOLUTION_DIRECTION.md
- §1.1：智商 **4.7/10**（Wave 5）、tier0 **441+2**、距 5.5 差 **0.8**
- §1.5：合格智能体检查表 Q1–Q7 与 backlog Wave 6 颗粒对应
- §1.4 I4/I5 与 Wave 5 feedback/tuner 一致

验证：rg "4\.7/10" docs/MIMIR_IQ_EVOLUTION_DIRECTION.md；无需 tier0（纯文档）

完成：backlog IQ-EVO-28 → [x]；bridge §4 一行。
```

---

## §29 · IQ-EVO-29（session_search 7d 基线）

**状态：** 工程已合入时 → 跑脚本、写 bridge 证据、标 `[x]`。

```text
【IQ-EVO-29 · 新窗执行】

Read §0 主上下文。

任务：IQ-EVO-29 — session_search 7 天使用率基线
- 代码：tools/session_search_usage_baseline.py · scripts/session_search_usage_baseline.py
- mimir_ops action: session_search_baseline
- 输出：$MIMIR_AETHER_HOME/data/ops/session_search_baseline_7d.json

步骤：
1. cd ~/src/MimirAether && MIMIR_AETHER_HOME=~/.mimiraether python3 scripts/session_search_usage_baseline.py
2. pytest tests/tools/test_session_search_usage_baseline.py -q
3. ./run_ralph_tier0.sh
4. ./scripts/record_m6_evolution.sh "IQ-EVO-29 session_search 7d baseline JSON + mimir_ops"

完成：backlog [x]；bridge §4 贴 session_search_session_rate 数字 + JSON 路径。
```

---

## §30 · IQ-EVO-30（飞书 3 场景 · 日志证据）

```text
【IQ-EVO-30 · 新窗执行】

Read §0 + docs/phase0/p2-long-iqevo-wave6-qualified-agent.md §B。

任务：飞书 3 场景冒烟（历史 IR / 用户偏好 / 上次决策）
- 优先：从 gateway/agent log + state.db 构造 **documented** 证据表（用户句 + 是否 session_search）
- 若 log 不足：写 docs/phase0/iqevo-30-feishu-smoke-evidence.md 标明 fail 与 ISSUES

禁止：为通过冒烟改 agent 默认行为（除非 tier0 契约已要求）

验证：证据表 3 行；./run_ralph_tier0.sh（若只文档则说明等价检查）

完成：backlog [x]；bridge §4。
```

---

## §31 · IQ-EVO-31（search-first 违例审计）

```text
【IQ-EVO-31 · 新窗执行】

Read §0。Read agent/prompt_builder.py SESSION_SEARCH_GUIDANCE 片段。

任务：抽样 10 条「应 search-first」会话，审计是否先调用 session_search
- 数据源：state.db 最近 7d 含 user 跨会话关键词的会话
- 输出：docs/phase0/iqevo-31-search-first-audit.md（表格：session_id, 违例 Y/N, 备注）
- 汇总违例率 %；0 违例也要写证据

验证：文档 + 可选 scripts/ 小工具；tier0 若新增脚本则全绿

完成：backlog [x]；bridge §4 违例率一行。
```

---

## §32 · IQ-EVO-32（离线 intent 标签 MVP）

```text
【IQ-EVO-32 · 新窗执行】

Read §0 + docs/phase0/intent-predictor-audit.md（Q03）。

任务：离线 intent 标签 MVP — 读 JSONL/log，输出标签字段；**不**默认生产 IntentPredictor
- 建议：scripts/label_intent_offline.py 或 tools/ 模块 + tests/agent/
- 输入：feedback_events.jsonl 或 session 导出（document 路径）

验证：pytest 新测 + ./run_ralph_tier0.sh + evolution_log

完成：backlog [x]；bridge §4 脚本路径 + 样例 1 行输出。
```

---

## §33 · IQ-EVO-33（nudge 7d 计数）

```text
【IQ-EVO-33 · 新窗执行】

Read §0 + agent/conversation_nudges.py。

任务：memory/skill nudge 过去 7d 触发计数
- grep gateway.log 或 $MIMIR_AETHER_HOME/logs 中 [MIMIR_MEMORY_NUDGE] / [MIMIR_SKILL_NUDGE]
- 或 mimir_ops 扩展子命令（若更小）

输出：docs/phase0/iqevo-33-nudge-7d.md 或 data/ops/nudge_counts_7d.json

验证：tier0 若改代码；否则文档等价

完成：backlog [x]；bridge §4 两行计数。
```

---

## §34 · IQ-EVO-34（JEPA no_candidates 占比）

```text
【IQ-EVO-34 · 新窗执行】

Read §0 + docs/phase0 中 JEPA 相关 closeout。

任务：7d `no_candidates` 占比 vs Wave 4 基线（升/平/降）
- 数据源：$MIMIR_AETHER_HOME 下 JEPA/进化 log（rg no_candidates）

输出：docs/phase0/iqevo-34-jepa-candidate-rate.md

验证：只读分析优先；tier0 若改脚本

完成：backlog [x]；bridge §4。
```

---

## §35 · IQ-EVO-35（analysis artifact → prompt 只读）

```text
【IQ-EVO-35 · 新窗执行】

Read §0 + agent/post_close_analysis.py + prompt_builder 注入点。

任务：MIMIR_AUTO_ANALYSIS=1 时，将最近 analysis artifact 摘要注入 prompt **第二段（只读）**
- 不改技能文件 · 不 AUTO_EVOLVE

验证：tests/agent/ 或 contract；./run_ralph_tier0.sh；evolution_log

完成：backlog [x]；bridge §4 + 一条 staging 可见性说明（env 即可）。
```

---

## §36 · IQ-EVO-36（tool_quality top5 ok%）

```text
【IQ-EVO-36 · 新窗执行】

Read §0 + tools/tool_quality.py + $MIMIR_AETHER_HOME/data/tool_quality.db。

任务：周常 top5 工具 ok% 查询命令 + bridge §4 模板行
- 可扩展 scripts/ 或 docs/ops/ 一节

输出：docs/ops/tool-quality-weekly.md + 一次真实查询结果粘贴 closeout

验证：tier0 若改 tools/

完成：backlog [x]；bridge §4 模板。
```

---

## §37 · IQ-EVO-37（run_evolution_eval 手册）

```text
【IQ-EVO-37 · 新窗执行】

Read §0 + scripts/run_evolution_eval.sh。

任务：周常手册 + JSON 环比字段说明；**真实跑通一次** exit 0
- 文档：docs/ops/evolution-eval-weekly.md（或 phase0 附录）

验证：
cd ~/src/MimirAether && MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh
贴 JSON 路径

完成：backlog [x]；bridge §4。
```

---

## §38 · IQ-EVO-38（rubric #5 + Wave 6 closeout）

```text
【IQ-EVO-38 · 新窗执行】

Read §0 + docs/phase0/iq-scoring-rubric.md。

前置：IQ-EVO-28～37 尽量已 [x]。

任务：
1. 复评 rubric 第 5 轮（Wave 6）；目标 ≥5.5 或 documented exception（差值 + 下一 Wave）
2. 写 docs/phase0/p2-long-iqevo-wave6-closeout.md
3. ISSUES #12：resolved 或续期理由
4. backlog §15 Wave 6 全 [x] 或标明例外粒

验证：./run_ralph_tier0.sh

完成：bridge §4 智商分数 + closeout 链接。
```

---

## §39 · IQ-EVO-39（ADR-002 Spike · 可选）

```text
【IQ-EVO-39 · 新窗执行】

Read §0。Read docs 中 memory/skill/persistent 三写入入口。

任务：ADR-002 或 phase0 一页 — 三入口对比 + 推荐写入序；**不改**三条写路径代码

验证：纯文档 → tier0 说明 docs-only

完成：backlog [x]；bridge §4 链接。
```

---

## 执行顺序（刘哥无需记 — 按 backlog `[ ]` 从上到下）

| 顺序 | ID | 本页 |
|------|-----|------|
| 1 | IQ-EVO-28 | §28 |
| 2 | IQ-EVO-29 | §29 |
| … | … | … |
| 末 | IQ-EVO-38/39 | §38 / §39 |

**当前仓库进度（2026-05-26）：** **IQ-EVO-27～39 全 [x]** · Wave 6 结案 · rubric **4.8/10** documented exception · closeout `docs/phase0/p2-long-iqevo-wave6-closeout.md`。

---

## M6 提醒

触达 `agent/`、`gateway/`、`tools/`、`tests/contract/` 时：

```bash
./scripts/record_m6_evolution.sh "IQ-EVO-xx: <one line>"
```
