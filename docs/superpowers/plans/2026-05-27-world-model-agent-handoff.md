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

## 2. 完成度仪表盘（2026-05-27 · OS-REV-01 收口 · tier0 **578+2** · base **ac29465**）

### 2.1 分层完成度

| 层级 | 含义 | 完成度 | 说明 |
|------|------|:------:|------|
| **A. 工程底座** | 能跑、能回归、能运维（CLEARANCE 8/8 · M0–M6 · tier0 **578+2**） | **~88%** | 余：Gateway 十条零星 · TRUNCATE 历史噪声 |
| **B. IQ/SEM/Autonomy** | §15 Wave1–8 · §14 SEM · §17 AUTO · §18 Wave9 | **100%** | 本阶段已结案 |
| **C. Horizon C §19.1** | 11+4 工程粒（Wave10→15+） | **60%** | **9/15** `[x]` |
| **D. §19.2 运维验收** | 部署/冒烟/eval | **20%** | **1/5** `[x]`（OPS-DEPLOY-W9） |
| **E. 世界模型提案** | `world-model-evolution-plan` Phase0–3 | **~22%** | 仅有 guard/记忆/curator **基础设施**；无预测器·VoE→学习·分层规划 **合约** |
| **F. 行为 rubric** | 相对 Hermes 日常聪明度 | **4.9/10** | 距战役目标 **5.5** 差 **0.6**（需 G-RUBRIC-55 拍板） |

### 2.2 综合进度（通向「LLM 世界模型智能体」）

**公式（权重可调）：**  
`0.25×A + 0.15×B + 0.25×C + 0.05×D + 0.25×E + 0.05×F_norm`

其中 `F_norm = 4.9/10 = 49%`。

| 项 | 计算 |
|----|------|
| 代入 | 0.25×88 + 0.15×100 + 0.25×60 + 0.05×20 + 0.25×22 + 0.05×49 |
| **综合** | **≈ 61%** |

**读法：**

- **~76%** = **P3-XSR-02** L2 预取已勾；下一工程粒 **P3-XSR-03**（L3）或 **ENGINE-WS-01**。
- **下一程涨分最快**：完成 **Horizon C Wave10–11**（+C）+ 推动 **P3-XSR / ADR-002**（为世界模型注入/预测铺路）+ **WM Phase0 拍板**（+E）。

### 2.3 §19 可勾选进度（执行用）

| 桶 | 完成 | 总数 | % |
|----|:----:|:----:|---:|
| §19.1 工程轨 | 11 | 16 | 69% |
| §19.2 运维轨 | 1 | 5 | 20% |
| §19.3 拍板轨 | 1 | 5 | 20%（**G-ADR-002** ✅） |
| **§19 可执行合计** | **10** | **20** | **50%** |

每完成 1 粒工程项：**§19.1 进度 +6.25%**（1/16）。  
Wave 10 全完成（3 粒）：**+20%** §19.1。

---

## 3. 我从哪开始（Cursor 决策 · 2026-05-27 更新）

**已完成：** Wave 13–14 [x] · TOOL-SRCH `6112f38` · P3-XSR `c7f4bc4` · tier0 **595+2**

**下一粒：** **P3-XSR-03**（L3 RAG flag）或 **ENGINE-WS-01** · **P3-XSR-02** L2 已勾（2026-05-27）

**合并策略：** 每粒一 commit；排除 `data/persistent.json`。

**禁止：** WM Phase0 · ADR-002 实现 · rubric 5.5 空喊

---

## 4. 执行窗口 · 粘贴提示词（Superpowers 强制）

**整段复制到执行窗口：**

```text
【角色】Cursor 执行窗口 · MimirAether

【Superpowers】using-superpowers → verification-before-completion

【真源】backlog §19.1 · docs/proposals/p3-cross-session-retrieval.md §6（L2）

【默认下一工程粒】P3-XSR-03（L3 semantic prefetch · flag 默认关）或 ENGINE-WS-01

【基线 main】99ac4f1 · §19.1 11/16 · G-ADR-002 ✅ · tier0 595+2

【禁止】改 SESSION_SEARCH 生产默认 · WM Phase0 · persistent.json commit

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
