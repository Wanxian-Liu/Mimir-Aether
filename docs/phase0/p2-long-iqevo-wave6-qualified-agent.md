# P2-LONG-IQEVO · Wave 6（合格智能体 · 行为 + rubric）

**Date:** 2026-05-26  
**Baseline:** Wave 5 结案后 · rubric **4.5/10**（距 **5.5** 差 1.0）  
**真源：** [`MIMIR_IQ_EVOLUTION_DIRECTION.md`](../MIMIR_IQ_EVOLUTION_DIRECTION.md) §0.1、§1.5  
**拍板：** 待刘哥 — 本文 + backlog §15 Wave 6 立案

## 放哪？（ISSUES vs backlog）

| 载体 | 放什么 | 不放什么 |
|------|--------|----------|
| **`MIMIR_EXEC_BACKLOG.md` §15** | 本表 IQ-EVO-27～39、`[ ]` 状态、Owner、成功标准 | 长篇设计叙述 |
| **本文** | 目标、范围、验收、冒烟、与 Hermes 对照 | — |
| **`MIMIR_ISSUES.md` #12** | 一行 **direction** 锚点 → 指向 §15 第一条 `[ ]` | 十几条 Active 子任务（违反 ≤3） |
| **GitHub** | 不强制新开；工程仍 **#32**（SEM）等既有号 | 与 docs 双真源 |

## Goal（合格智能体 · 可操作定义）

**不是**「tier0 绿」或「能转发 DeepSeek 回复」。**是** 在 Parity 底座上同时满足：

1. **Rubric**：加权 **≥5.5/10**，或 **documented exception**（写明差多少、下一 Wave）。
2. **行为**（至少 2 项有数字/路径，见 [`MIMIR_IQ_EVOLUTION_DIRECTION.md`](../MIMIR_IQ_EVOLUTION_DIRECTION.md) §3.2）：
   - 跨会话问题 **先 `session_search`**（飞书 log + 7d 抽样率）；
   - **`run_evolution_eval.sh`** 周常 JSON 环比；
   - 生产 **tool_quality** top5 ok% 或 degraded 占比可追溯。
3. **进化边界**：仍 **禁止** 未授权 `MIMIR_AUTO_EVOLVE=1`；Wave 6 可消费 Wave 5 **有界调参**，不扩 1c。

## 前置

- §15 **Wave 5** IQ-EVO-20～26 **全 [x]**（含 rubric 复评 #4）。
- 生产建议：`MIMIR_FEEDBACK_COLLECTOR=1` · staging/生产按 closeout 开 `MIMIR_AUTO_TUNER=1`。

## 颗粒任务（执行顺序 = 表顺序）

### A · 立案与真源

| ID | 任务 | Owner | 成功标准 |
|----|------|-------|----------|
| **IQ-EVO-27** | Wave 6 立案 + backlog 表 + bridge §1 一行拍板 | Cursor | 本文 + §15 表；刘哥可回复「开 Wave 6」 |
| **IQ-EVO-28** | 方向文档 **§1.1→4.5** + **§1.5 合格检查表** | Cursor | `MIMIR_IQ_EVOLUTION_DIRECTION.md` 与 rubric 一致 |

### B · 反「传话筒」行为证据

| ID | 任务 | Owner | 成功标准 |
|----|------|-------|----------|
| **IQ-EVO-29** | **session_search 使用率基线**（7d） | Cursor | `scripts/` 或 `mimir_ops` 子命令输出路径；含调用次数/会话比 |
| **IQ-EVO-30** | **飞书 3 场景冒烟**（历史 IR / 用户偏好 / 上次决策） | Mimir+刘哥 | 每场景 1 条：用户句 + log 含 `session_search` 或 documented fail |
| **IQ-EVO-31** | **search-first 违例审计**（抽样 10 条） | Mimir | 表格：是否先 search；违例率 %；无则「0 违例」证据 |

### C · rubric 核心缺口（#1 学习 · #8 意图）

| ID | 任务 | Owner | 成功标准 |
|----|------|-------|----------|
| **IQ-EVO-32** | **离线 intent 标签 MVP**（[`intent-predictor-audit.md`](./intent-predictor-audit.md)） | Cursor | 脚本/模块：日志或 JSONL 打标签；**不**默认生产 Predictor |
| **IQ-EVO-33** | **nudge 有效性** — memory/skill nudge 7d 触发计数 | Mimir | log 统计或 `mimir_ops` 可读指标；bridge §4 一行 |
| **IQ-EVO-34** | **JEPA 候选率** — `no_candidates` 占比周报 | Mimir | 7d 样本 + 较 Wave 4 基线对比（升/平/降） |

### D · 数据闭环（#10 · 承接 Wave 5）

| ID | 任务 | Owner | 成功标准 |
|----|------|-------|----------|
| **IQ-EVO-35** | **analysis artifact 摘要 → prompt**（只读第二段） | Cursor | tier0；`MIMIR_AUTO_ANALYSIS=1` 时可见摘要；仍不改技能文件 |
| **IQ-EVO-36** | **tool_quality 周常一行** — top5 ok% | Mimir | bridge §4 模板 + `tool_quality.db` 查询命令 |

### E · 进化纪律（维持 · 非伪进化）

| ID | 任务 | Owner | 成功标准 |
|----|------|-------|----------|
| **IQ-EVO-37** | **`run_evolution_eval.sh` 周常** — 手册 + JSON 环比字段 | Cursor | `docs/ops/` 或 phase0 模板；一次真实 exit 0 输出路径 |
| **IQ-EVO-38** | **rubric 复评 #5** + Wave 6 closeout | Mimir+刘哥 | ≥5.5 或 documented exception；ISSUES **#12** resolved 或续期理由 |

### F · 设计债（可选 · 不挡 Wave 6 工程结案）

| ID | 任务 | Owner | 成功标准 |
|----|------|-------|----------|
| **IQ-EVO-39** | **ADR-002 统一写入 Spike** | Cursor | `docs/adr/` 或 phase0 一页：三入口对比 + 推荐序；**不**改三条写路径代码 |

## Out of scope

- `MIMIR_AUTO_EVOLVE=1` 默认开 · 技能自动写入  
- Unified Plan **1c** 全量 DecisionRing/Compressor 学习  
- IntentPredictor **生产默认**（仅 IQ-EVO-32 离线 MVP）  
- 新开 GitHub issue 替代 backlog §15  

## Mimir 新窗一句（Wave 6）

```text
Read docs/phase0/p2-long-iqevo-wave6-qualified-agent.md + backlog §15 第一条 [ ]。
本轮只做 IQ-EVO-30/31/33/34/36/38 中刘哥点名的粒；回报方向文档 §3.3。
勿开 AUTO_EVOLVE；勿改 agent/gateway 除非 bridge §1 授权 B。
```

## Cursor 新窗一句（Wave 6 工程）

```text
Read backlog §15 Wave 6。实现 IQ-EVO-27～29、32、35、37、39（按表顺序第一条 [ ]）。
每粒 ./run_ralph_tier0.sh + evolution_log；前置 Wave 5 全 [x]。
```

## Success（Wave 6 结案）

- IQ-EVO-27～38 **全 [x]**（IQ-EVO-39 可 `[~]` defer 不挡结案）  
- Rubric **≥5.5** 或 closeout **documented exception**（含 #1/#8 是否仍 <4）  
- 行为证据包：`session_search` 基线 + 3 场景冒烟 + eval JSON 路径 + tool ok% 一行  

## 与「传话筒」对照（验收时自问）

| 传话筒表现 | Wave 6 要证明的反面 |
|------------|---------------------|
| 每问都从零上下文答 | 历史类问题 log 有 `session_search` |
| 只说「我会学习」无文件 | `feedback_events.jsonl` / `tune_audit.jsonl` / eval JSON |
| tier0 绿当智商 | rubric 表 + 复评 #5 数字 |
| 工具失败重复犯 | tool_quality 周常 + 可选 tuned_thresholds 变更 |
