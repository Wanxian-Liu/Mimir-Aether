# 世界模型智能体 · 新窗 Handoff（刘哥 → Cursor / Mimir）

> **创建**：2026-05-27 · **真源**：`docs/MIMIR_EXEC_BACKLOG.md` §19 · [`2026-05-27-horizon-c-master-iteration.md`](./2026-05-27-horizon-c-master-iteration.md) · [`world-model-evolution-plan.md`](../proposals/world-model-evolution-plan.md)

---

## 1. 战略一句话（刘哥意图）

**Mimir ≠ DeepSeek 传话桶。** 终局是 **依托 LLM 的 Agent 级世界模型智能体**：

- **世界模型（非像素）**：用 LLM 在**表征空间**里做「下一步需要什么上下文 / 哪些 skill / 预期结果」，并与 **VoE（违背预期）→ 学习** 闭环，而不是只回放历史。
- **已有地基**：`degeneration_guard` · hybrid/semantic 检索 · cross-session 注入 · 进化链 · `skill_curator` · 1c DecisionRing/Compressor。
- **Horizon C（§19.1）**：把 Hermes/OpenSpace **学来的意图**落成 Mimir 自造模块，为世界模型 **Phase 0** 铺路（质量、检索、策展、跨会话战略）。
- **世界模型 Phase 0+**：刘哥 **WM-HORIZON-01 拍板** 后单独开 Wave，**禁止**与 Wave 10–14 混 PR。

---

## 2. 完成度仪表盘（2026-05-27 · HERM-RED-02 收口 · tier0 **555+2**）

### 2.1 分层完成度

| 层级 | 含义 | 完成度 | 说明 |
|------|------|:------:|------|
| **A. 工程底座** | 能跑、能回归、能运维（CLEARANCE 8/8 · M0–M6 · tier0 **555+2**） | **~88%** | 余：Gateway 十条零星 · TRUNCATE 历史噪声 |
| **B. IQ/SEM/Autonomy** | §15 Wave1–8 · §14 SEM · §17 AUTO · §18 Wave9 | **100%** | 本阶段已结案 |
| **C. Horizon C §19.1** | 11+4 工程粒（Wave10→15+） | **46.7%** | **7/15** `[x]` |
| **D. §19.2 运维验收** | 部署/冒烟/eval | **20%** | **1/5** `[x]`（OPS-DEPLOY-W9） |
| **E. 世界模型提案** | `world-model-evolution-plan` Phase0–3 | **~22%** | 仅有 guard/记忆/curator **基础设施**；无预测器·VoE→学习·分层规划 **合约** |
| **F. 行为 rubric** | 相对 Hermes 日常聪明度 | **4.9/10** | 距战役目标 **5.5** 差 **0.6**（需 G-RUBRIC-55 拍板） |

### 2.2 综合进度（通向「LLM 世界模型智能体」）

**公式（权重可调）：**  
`0.25×A + 0.15×B + 0.25×C + 0.05×D + 0.25×E + 0.05×F_norm`

其中 `F_norm = 4.9/10 = 49%`。

| 项 | 计算 |
|----|------|
| 代入 | 0.25×88 + 0.15×100 + 0.25×46.7 + 0.05×20 + 0.25×22 + 0.05×49 |
| **综合** | **≈ 58%** |

**读法：**

- **~58%** = **HERM-RED-02** 运维化 `redact_rules.json`；下一粒 **HERM-CTX-02**。
- **下一程涨分最快**：完成 **Horizon C Wave10–11**（+C）+ 推动 **P3-XSR / ADR-002**（为世界模型注入/预测铺路）+ **WM Phase0 拍板**（+E）。

### 2.3 §19 可勾选进度（执行用）

| 桶 | 完成 | 总数 | % |
|----|:----:|:----:|---:|
| §19.1 工程轨 | 7 | 15 | 46.7% |
| §19.2 运维轨 | 1 | 5 | 20% |
| §19.3 拍板轨 | 0 | 5 | 0%（刘哥） |
| **§19 可执行合计** | **8** | **20** | **40%** |

每完成 1 粒工程项：**§19.1 进度 +6.7%**（1/15）。  
Wave 10 全完成（3 粒）：**+20%** §19.1。

---

## 3. 我从哪开始（Cursor 决策 · 2026-05-27 更新）

**已完成：** Wave 11–12 [x]（… · SCR · **RED** 工作区 dirty）· tier0 **555+2**

**下一粒：** **HERM-CTX-02**（Wave 12 Task 8）— 飞书 cross-session 冒烟

**合并策略：** 每粒一 commit（`commit RED-02` / `commit CTX-02`）；排除 `data/persistent.json`。

**禁止：** WM Phase0 · ADR-002 实现 · rubric 5.5 空喊

---

## 4. 新 Cursor 窗 · 粘贴提示词（Superpowers 强制）

**整段复制到新 Agent 窗（当前粒：HERM-CTX-02）：**

```text
【角色】Cursor 工程 · MimirAether · 主线：依托 LLM 的世界模型智能体（非传话桶）。

【Superpowers】using-superpowers → subagent-driven-development → TDD → verification-before-completion → finishing-a-development-branch（commit CTX-02）

【真源】主计划 Task 8 · backlog §19.1 第一条 [ ]（HERM-CTX-02）· handoff §2–§3

【本粒 · HERM-CTX-02】飞书 1 条自然语言 context_references 冒烟（DSL 已存在）；contract + tier0 + closeout

【收尾】record_m6 → backlog [x] → bridge §4 → commit CTX-02（不含 persistent.json）

【已推/待推】RED-02 工作区 dirty · tier0 555+2 · §19.1 7/15 · ~58%

【禁止】persistent.json · WM Phase0 · ADR-002 · 与 RED/REV 混做

【仓库】~/src/MimirAether · MIMIR_AETHER_HOME=~/.mimiraether
```

---

## 5. 新 Mimir 窗 · 粘贴提示词（运维轨 · Superpowers 轻量）

```text
【角色】Mimir 运维 · 不抢 §19.1 代码。

【必读】bridge §1「@Mimir 必读」+ backlog §19.2 第一条 [ ]。

【Superpowers】Read superpowers:verification-before-completion — 无 log/health 证据不得宣称 smoke pass。

【本窗】
1) OPS-IQ-SMOKE-49：/new 后问 key_decisions 是否在 cross-session 出现
2) OPS-EVAL-WEEKLY：MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh
3) 回报：MIMIR_IQ_EVOLUTION_DIRECTION.md §3.3 模板 + bridge §4 一行

【禁止】改 agent/gateway/tools · git push
```

---

## 6. 刘哥只需拍板的一次性清单（§19.3）

| 顺序 | Gate | 建议时机 |
|------|------|----------|
| 1 | **IQ-RUBRIC-55** | Wave 11 后（有 TQM+Search 行为证据再冲 5.5） |
| 2 | **ADR-002-impl** | Wave 14 P3-XSR 调研 doc 出炉后 |
| 3 | **WM-HORIZON-01** | ADR-002 方向清晰后 · 开 WM Phase0 spike |
| 4 | D5-ADR / 识图 | 不阻塞 Horizon C |

---

## 7. 世界模型路线图与 §19 的对应（给新窗建立全局观）

```
[今] Wave10 curator/TGR/SDH  ──► 元层：什么 skill/context 相关
[W3-4] Wave11 TQM+Search    ──► 工具与记忆「预测输入」质量
[W7-8] Wave14 P3-XSR+ADR   ──► 分层注入 = 世界模型上下文编码器设计输入
[G-WM 拍板]                 ──► WM Phase0：LLM 预测器 + VoE→学习 最小 spike
[W13+]                      ──► 分层规划合约 · surprise→skill 写入
```

**每一粒 Horizon C 都在回答：**「世界模型还需要哪块 **可测** 的地基？」——不是抄 Hermes 代码。

---

## 8. 进度更新约定

完成任意 §19.1 粒后，在本文件 **§2.3** 更新 x/15，并重算 **§2.2 综合 %**（C 层 = x/15×100%，E 层仅在 WM milestone 时手动调）。
