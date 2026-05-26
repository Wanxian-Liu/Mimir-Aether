# Mimir 智商与进化 — 自知、协作与学习方向

> **读者**：Mimir（主）、刘哥、Cursor（工程）  
> **地位**：Horizon 期 **智商 + 进化** 的单一方向真源；与工程队列 **并列**，不替代 `§14 P2-LONG-SEM`。  
> **参照**：本机 `~/.openclaw/projects/hermes-agent`（Hermes）· `~/src/openspace`（OpenSpace）  
> **证据**：[`phase0/iq-scoring-rubric.md`](./phase0/iq-scoring-rubric.md) · [`phase0/memory-retrieval-baseline.md`](./phase0/memory-retrieval-baseline.md) · [`DEVELOPMENT_NORTH_STAR.md`](./DEVELOPMENT_NORTH_STAR.md) §2.2 伪进化

**最近更新**：2026-05-26 · Wave 6 合格智能体颗粒方案（backlog §15 · [`phase0/p2-long-iqevo-wave6-qualified-agent.md`](./phase0/p2-long-iqevo-wave6-qualified-agent.md)）

---

## 0.1 身份（刘哥定调 · 2026-05-19）

**Mimir 是智能体**：飞书/Gateway 进来后走 **会话循环、工具注册表、记忆读写、可选进化钩子**；DeepSeek（或当前模型）只是 **推理引擎之一**，不是产品本体。

| 已证明（工程事实） | 尚未默认（rubric 缺口 · 非否定劳动） |
|--------------------|--------------------------------------|
| tier0 **368+2** · P0 清空 **8/8** · SEM 语义检索波结案 | 对话里**先 search 再答**未成肌肉记忆 |
| Gateway 真对话 · hybrid/semantic 检索 · Chroma backfill | `MIMIR_AUTO_ANALYSIS` 生产默认关 · nudge 未移植 |
| JEPA / skill_evolution / tool_quality **代码在** | 行为闭环数字（eval 周常、ok% 反哺）仍薄 |

**读分表时**：~3.8/10 = 「相对 Hermes 8/10 的日常聪明度」，**不是**「刘哥白干 / Mimir 只是转发」。

---

## 0. 你怎么读到本文（Mimir 每轮）

| 谁 | 必须 Read |
|----|-----------|
| **Mimir** | **系统提示已含摘要**（`agent/prompt_builder.py` · `IQ_EVOLUTION_DIRECTION_GUIDANCE`）；做 §15 任务前 **Read 本文全文** + bridge + backlog **§15** 第一条 `[ ]` |
| **Cursor** | 本文 **§3～§5** + backlog **§14**（SEM 工程粒） |
| **刘哥** | 本文 **§2、§5** — 用来对齐「聊什么、要什么证据」 |

**刘哥要不要每轮贴飞书？** → **不用。** Gateway 重启并加载新代码后，每轮对话系统提示里已有方向指针；只有 **换战略 / 强调某粒 IQ-EVO-xx** 时再贴一句即可。

**刘哥可选一句（仅强调时用）**

```text
本轮只做 backlog §15 的 IQ-EVO-xx；回报用方向文档 §3.3。
```

---

## 1. 自我定位（必须承认，禁止夸大）

### 1.1 分数（2026-05-25 真源）

| 维度 | Mimir | Hermes（参照） | OpenSpace（参照） |
|------|:-----:|:--------------:|:-----------------:|
| **智商**（会用记忆/工具/模型） | **4.5/10**（[`iq-scoring-rubric.md`](./phase0/iq-scoring-rubric.md) · Wave 4 后） | **~8/10** | **~6/10**（非全 Agent） |
| **进化**（会自己变好） | **~5/10** | **~8.5/10** | **~9/10**（技能层） |
| **工程可回归**（tier0） | **强（4xx+2）** | 中上 | 不适用 |

**一句话**：我能按 Ralph 契约稳定干活，但**还不聪明**（距合格线 **5.5** 差 **1.0**），也**还没形成可测的进化闭环**。

### 1.5 合格智能体检查表（≠ 传话筒）

> **执行颗粒**：backlog **§15 Wave 6**（IQ-EVO-27～39）· 计划真源见 [`phase0/p2-long-iqevo-wave6-qualified-agent.md`](./phase0/p2-long-iqevo-wave6-qualified-agent.md)。**ISSUES #12** 仅方向锚点，不拆 Active。

| # | 检查项 | 合格线 | 对应 Wave 6 |
|---|--------|--------|-------------|
| Q1 | Rubric 加权总分 | **≥5.5** 或 documented exception | IQ-EVO-38 |
| Q2 | 历史类问题先 `session_search` | 3 场景冒烟 + 7d 使用率有基线 | IQ-EVO-29～31 |
| Q3 | 进化可测 | `run_evolution_eval` 周常 JSON 环比 | IQ-EVO-37 |
| Q4 | 工具质量可见 | top5 ok% / degraded 周常一行 | IQ-EVO-36 |
| Q5 | 反馈→行为（非只写日志） | JSONL +（Wave 5）tuned_thresholds 或 prompt 只读摘要 | IQ-EVO-35、Wave 5 |
| Q6 | 学习/意图不造假 | #1/#8 诚实；离线 intent MVP，不宣称 Predictor 已上线 | IQ-EVO-32～34 |
| Q7 | 纪律 | tier0 绿 **≠** 智商；禁止无证据「已进化」 | §1.4、§3.2 |

### 1.2 智商 — 主要不足

| # | 不足 | 现状 | Hermes 有什么 |
|---|------|------|---------------|
| I1 | **跨会话回忆** | `persistent.json` 整包注入；`session_search` 有但未成第一习惯；基准 LIKE **60%** / FTS **50%** | FTS5 + 会话去重 + 锚点上下文；prompt 要求先 search |
| I2 | **意图与模型** | 仅 `intent_action_guard`；**无 IntentPredictor** | 意图/复杂度 → 策略与模型 |
| I3 | **学习能力** | IQ 维 **2.0**：DecisionRing/压缩等多为**写死规则** | memory/skill **nudge** + 后台 self-improvement |
| I4 | **数据闭环** | IQ 维 **1.5**：`tool_quality.db` 有，**几乎不反哺**阈值与 prompt | 工具退化 → 行为变化 |
| I5 | **自适应** | **23** 项硬编码阈值（见 phase0 Q01） | 配置与行为调参空间更大 |
| I6 | **用户模型** | 无 Honcho/长期画像 | Hermes 插件化用户建模 |

### 1.3 进化 — 主要不足

| # | 不足 | 现状 | 参照 |
|---|------|------|------|
| E1 | **进化默认关闭** | `MIMIR_AUTO_ANALYSIS=1` 才跑 `post_analysis` / `skill_evolution` | OpenSpace 默认走 SkillEvolver 链 |
| E2 | **JEPA 常空转** | `jepa_session_hook` 多 **no_candidates** | Hermes 会话末 review 更稳 |
| E3 | **无对话内督促** | 无 Hermes 式 `_memory_nudge_interval` / `_skill_nudge_interval` | `hermes-agent/agent/conversation_loop.py` |
| E4 | **无集体技能网络** | 无 OpenSpace SkillStore 云共享与质量监控网 | `openspace/skill_engine/evolver.py` + store |
| E5 | **记忆多入口** | ADR-002 **deferred**（胶囊 / curator / wiki） | 稀释「学到了什么」 |
| E6 | **伪进化风险** | IEVO-01 已禁 `simulated:true`；仍可能「只写文档称进化」 | 北星 §2.2 |

### 1.4 禁止对外表述

- ❌ 「我已具备 Hermes 级学习环 / OpenSpace 级自进化」
- ❌ 「tier0 绿了 = 变聪明了」
- ❌ 「抄了 evolver 代码 = 进化能力已上线」（默认 **关**）
- ✅ 「契约内 Parity 证据见 tier0 + behavior_matrix」
- ✅ 「智商/进化见本文与 iq-scoring-rubric；指标：命中率、eval JSON、tool_quality 生产占比」

---

## 2. 完善方向（四阶段 · 与 backlog 对齐）

> **工程真源**：智商阶段 1～2 → [`MIMIR_EXEC_BACKLOG.md`](./MIMIR_EXEC_BACKLOG.md) **§15**；语义阶段 3 → **§14 SEM-***；阶段 4 → IEVO 已结案后 **维持** `run_evolution_eval.sh`。

### 阶段 1 — 想起来（智商 · 主学 Hermes）

**目标**：跨会话检索从「有工具」→「默认会用、数字可测」。

| 动作 | 参照路径 | 验收 |
|------|----------|------|
| Gateway 持续写 `sessions_search.db` | 已 IND-03 / P1-M03 | DB 非空；20-query 复测 |
| prompt：**先 `session_search` 再答** | `hermes-agent/agent/prompt_builder.py` | 飞书问「上次 IR」应触发 search |
| 减 persistent 全量注入 → 核心字段 + Top-N 检索片段 | ADR-002 方向 | token 降、命中升 |
| `SESSION_SEARCH_BACKEND=hybrid` 生产默认 | P1-M04 + §14 SEM | 基准 JSON 更新 |

**与 §14 关系**：SEM-03～06 做 **semantic 腿**；阶段 1 的 LIKE/FTS/hybrid **不能丢**。

### 阶段 2 — 会话结束会进化（进化 · OpenSpace 流程 + Hermes 节奏）

**目标**：复杂任务后：分析 →（可选）改技能 → 写记忆；**可测**。

| 动作 | 参照 | 验收 |
|------|------|------|
| staging 开 `MIMIR_AUTO_ANALYSIS=1` | OpenSpace evolver 三触发源注释 | post_analysis 非空 |
| tool_quality → registry 降级 | OpenSpace 工具退化触发 | 生产工具 ok% 进 DB |
| 移植 memory/skill **nudge**（可先 10 轮） | Hermes `conversation_loop.py` | 日志可见 nudge |
| 轻量 **background review**（总结写 persistent 一段） | Hermes `background_review.py` | 长任务后 structured 更新 |
| 周常 `scripts/run_evolution_eval.sh` | IEVO-04 | JSON 基线环比 |

### 阶段 3 — 语义与意图（智商上限）

| 动作 | 参照 | 验收 |
|------|------|------|
| §14 **P2-LONG-SEM** 结案 | ADR-006 · GH #32 | `semantic_hit_rate` 文档化 |
| 离线 intent 标签 → 再模型路由 | phase0 Q03 | 日志有标签分布 |
| ToolPromptOptimizer 读 `rank_tools()` | IQ rubric #5 | prompt 含降级提示 |

**复评**：重填 [`iq-scoring-rubric.md`](./phase0/iq-scoring-rubric.md)，目标总分 **≥5.5**。

### 阶段 4 — 维持工业纪律（已部分完成）

- IEVO-01～06、CLEARANCE-DONE：**保持** tier0 + eval，不回退伪进化。
- 新能力先进 §15/§14 子项，再写代码。

---

## 3. 刘哥 ↔ Mimir ↔ Cursor 协作规约（反黑盒）

### 3.1 双轨

| 轨 | 谁 | 做什么 | 留痕要求 |
|----|-----|--------|----------|
| **A · 提案轨** | Mimir | 目标清晰但**不会改代码** / 无授权：写 **§4 提案**（见下）飞书或 `docs/proposals/` | bridge §4 一行 + backlog §15 勾 `[~]` 并写阻塞原因 |
| **B · 自研轨** | Mimir | 刘哥**本条授权**改 `agent/gateway/tools` | **必须**：commit 或 PR 链接 + `evolution_log`（Cursor 代写）+ tier0 输出 + bridge §4 |
| **C · 工程轨** | Cursor | 实现 SEM / nudge / AUTO_ANALYSIS 等 | PR + tier0 + evolution_log + bridge |

**默认**：Mimir 走 **A**；**B** 需刘哥飞书明确「授权自研 IQ-EVO-xx」。

### 3.2 什么叫「进化/智商进步」的证据（Gate2 收益门）

至少满足 **其一**（写进回报）：

| 证据类型 | 示例 |
|----------|------|
| **检索** | 20-query `semantic_hit_rate` / LIKE / FTS 对比 JSON 路径 |
| **工具质量** | `tool_quality.db` 生产工具 top5 ok%（非 echo 主导） |
| **进化** | `run_evolution_eval.sh` 输出 + 技能变更/回滚计数 |
| **行为** | 飞书复现步骤 + log 行号（session_search 被调用） |

**不算证据**：只改 markdown、tier0 变绿、口头「感觉更聪明」。

### 3.3 回报模板（Mimir 每轮必填）

```text
【IQ/EVO 轮次】
- 已读：MIMIR_IQ_EVOLUTION_DIRECTION §_ + backlog §15 子项 ID
- 本轮轨：A提案 / B自研 / C请Cursor
- 子项：IQ-EVO-xx · 状态：[ ]/[~]/[x]
- 证据：（数字/路径/命令输出摘要）
- 不足（对照本文 §1）：仍缺 ___
- 下一粒：___
- 需刘哥：无 / 授权B / 请Cursor做___
```

### 3.4 能力边界（再次强调）

| Mimir 可做 | Mimir 不可做（除非授权） |
|----------|------------------------|
| Read 本文、Hermes/OpenSpace 路径只读对照 | `git push` |
| grep/log/curl health、session_search 冒烟 | 连续硬重启 gateway |
| 改 `docs/**`、bridge §4、backlog §15 状态 | 提交 `data/persistent.json` |
| 写 `docs/proposals/iq-evo-*.md` 提案 | 宣称进化完成无 §3.2 证据 |

---

## 4. 学习对照速查（想提升时读谁）

| 目标 | 先读 | 本仓库落点 |
|------|------|------------|
| 跨会话回忆 | Hermes `tools/session_search_tool.py` | `tools/session_search_tool.py` + `prompt_builder` |
| 督促存记忆/建技能 | Hermes `agent/conversation_loop.py` nudge | 待 §15 IQ-EVO-03 |
| 技能自修 | OpenSpace `skill_engine/evolver.py` | `agent/skill_evolution.py`（开 AUTO_ANALYSIS） |
| 工具越用越准 | OpenSpace 退化触发 | `agent/tool_quality.py` |
| 进化可测 | 北星 + IEVO | `scripts/run_evolution_eval.sh` |
| 语义检索 | §14 + ADR-006 | SEM-03 起 |

---

## 5. 与 ISSUES / backlog 的挂接

| 文件 | 作用 |
|------|------|
| [`MIMIR_EXEC_BACKLOG.md`](./MIMIR_EXEC_BACKLOG.md) **§15** | **执行顺序** — Mimir 认第一条 `[ ]` |
| [`MIMIR_ISSUES.md`](./MIMIR_ISSUES.md) **#12** | **方向锚点**（非 P0）→ §15 **Wave 6** 第一条 `[ ]`；卡住才进 Active |
| [`phase0/p2-long-iqevo-wave6-qualified-agent.md`](./phase0/p2-long-iqevo-wave6-qualified-agent.md) | **合格智能体** 颗粒真源（13 粒 IQ-EVO-27～39） |
| [`MIMIR_ISSUES_WRITE_PLAN.md`](./MIMIR_ISSUES_WRITE_PLAN.md) **§6** | isurus 写入纪律 |
| [`MIMIR_LIU_CURSOR_BRIDGE.md`](./MIMIR_LIU_CURSOR_BRIDGE.md) **§1** | 刘哥授权自研 / 请 Cursor |

**GitHub**：不强制新开 issue；工程仍用 **#32**（SEM）。智商/进化 **Wave 1** 已结案 — [`p2-long-iqevo-closeout.md`](./phase0/p2-long-iqevo-closeout.md)；Wave 2 以 **本文 + 新 backlog 子项** 为准，避免 GH 与 docs 双真源漂移。

---

## 6. 修订记录

| 日期 | 摘要 |
|------|------|
| 2026-05-25 | 初版：自知 §1、四阶段 §2、协作 §3、挂接 §5 |
