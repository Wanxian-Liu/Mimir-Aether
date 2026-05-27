# 初代世界模型改进方案

> **方向**：非像素类 · CPU 可运行 · Agent 级世界模型  
> **创建**：2026-05-26  
> **来源**：飞书会话 Mimir ↔ 刘哥  
> **相关文件**：`docs/MIMIR_LIU_CURSOR_BRIDGE.md` · `agent/degeneration_guard.py` · `data/degeneration_guard.json` · `~/.mimiraether/research/world-models-reading-list.md`

---

## 论文索引表

**阅读本方案前建议先过一遍这篇索引，后面每个改进点会标注引用。**

| # | 论文 | arXiv/出处 | 发 表 | 对应方案 | 关键词 |
|---|------|-----------|------|---------|--------|
| P1 | **LeWorldModel (LeWM)** | `2603.19312` | 2026.03 | §3.1～§3.3 | SIGReg 正则化 · VoE 违背预期检测 |
| P2 | **Hierarchical Planning with Latent World Models** | — | 2026.04 | §4.1～§4.2 | 多尺度分层 · 误差截断 |
| P3 | **H-JEPA (Introduction to Latent Variable EBMs)** | `2306.02572` | 2023 | §5.1～§5.2 | 抽象表征预测 · 能量函数 |
| P4 | **World Models (Recurrent World Models Facilitate Policy Evolution)** | NeurIPS 2018 | 2018 | §6.1 | 温度 τ · 梦境训练 · 对抗鲁棒性 |

> **要求再阅读的人员**：先打开这 4 篇论文的摘要/相关章节，再读本方案的对应章节。

---

## 1. 当前状态

### 1.1 已有的（不重复造）

| 基础设施 | 对应论文概念 | 现在能做什么 |
|----------|------------|------------|
| `degeneration_guard`（loop_detection / information_density / context_quality / surprise_gate / recovery_loop） | P1 §3.1 SIGReg + §5.2 VoE | 运行时监控退化、检测意外 |
| `session_search`（FTS5 + Chroma 语义混合） | P3 — 表征空间操作 | 跨会话检索 |
| `memory` + `skills` | P3 — 抽象知识结构 | 持久记忆 + 可复用技能 |
| `skill_curator` | P3 — 元层能力判断 | 追踪技能使用情况 |
| `context_compressor` | P4 V（Vision）类比 | 压缩上下文 |
| evaluator-optimizer | P2 — 分层评估 | 多轮评估与修正 |

### 1.2 缺失的（本文目标）

| 缺失能力 | 对应论文 | 严重程度 |
|----------|---------|---------|
| surprise → 学习（非仅告警） | P1 §5.2 VoE | 🔴 核心 |
| 分层规划合约 | P2 §4 Multi-Scale | 🔴 核心 |
| 预测式检索（被动→主动） | P3 抽象预测 | 🟡 重要 |
| 受控噪声（防止检索坍缩） | P4 τ | 🟢 锦上添花 |
| 信息密度 → 主动探索 | P1 §3.1 SIGReg | 🟡 重要 |

---

## 2. 总体架构

```
                    用户输入
                       │
                       ▼
             ┌───────────────────┐
             │ 上下文编码器       │  ← P3 H-JEPA: 压缩到表征空间
             │ (current_context) │
             └────────┬──────────┘
                      │
                      ▼
             ┌───────────────────┐
             │ 世界模型预测器     │  ← P3: 预测而非回放
             │ 1) 下次需要什么    │     基于当前 + 记忆 + skills
             │ 2) 哪些技能适用    │
             │ 3) 预期结果        │
             └────────┬──────────┘
                      │
              ┌───────┴────────┐
              ▼                ▼
      ┌────────────┐    ┌────────────┐
      │ 分层规划器   │    │ VoE 检测器  │ ← P1 §5.2
      │ 高层: 目标   │    │ 结果 vs 预期 │
      │ 中层: 策略   │    │ 语义意外 =  │
      │ 低层: 工具   │    │ 学习事件    │
      └──────┬───────┘    └──────┬──────┘
             │                   │
             └───────┬───────────┘
                     ▼
              ┌──────────────┐
              │ SIGReg 学习器  │ ← P1 §3.1
              │ surprise→memory│
              │ 低密度→探索    │
              └──────────────┘
```

---

## 3. 改进方案：从 LeWM（P1）出发

### 3.1 🔴 Surprise → 学习（由告警升级为训练）

**灵感来源**：P1 §5.2 VoE（Violation-of-Expectation）

**问题**：当前 `surprise_gate` 检测到语义意外后，只触发重规划——意外场景被丢弃，下次遇到同样问题仍会 surprise。

**改进**：

```python
# 当前逻辑（告警模式）
if surprise_gate_triggered:
    warn("🔴 Surprise 门控触发: 重规划中...")
    replan()

# 改进逻辑（学习模式）
if surprise_gate_triggered:
    # 1. 记录意外事件到 memory
    memory.save_surprise_event({
        "expected": predicted_outcome,
        "actual": actual_outcome,
        "context_snapshot": current_context_snapshot(),
        "root_cause_hint": diff_analysis(expected, actual),
        "timestamp": now(),
    })
    # 2. 用新学到的信息修正规划
    replan(extra_context=f"注意：之前的预期 '{predicted_outcome}' 与实际 '{actual_outcome}' 不符，已记录学习")
```

**验证标准**：同一场景第二次触发时，不再 surprise（因为已有记忆覆盖）。

### 3.2 🟡 信息密度低 → 主动探索

**灵感来源**：P1 §3.1 SIGReg（强制潜表示不坍塌）

**问题**：当前 information_density <40% 只告警，不采取行动。信息空间在被动缩小。

**改进**：当信息密度连续 N 轮低于阈值时，自动触发一次「探索行动」：

```
信息密度低 → session_search("当前话题附近未探索的方向")
           → 向用户提出一个延伸问题或补充一个相关事实
           → 信息密度重新评估
```

这相当于 SIGReg 的运行时版本——强制表征空间不坍缩到同一个点。

### 3.3 🟢 区分表面意外 vs 语义意外（已有雏形，需加固）

**灵感来源**：P1 §5.2 VoE（区分视觉变化 vs 物理违反）

**问题**：当前 `surprise_gate` 的 `surface_vs_semantic` 区分已在 JSON 中定义，但实际触发时可能混淆。

**改进**：在执行前显式保存「预期结果摘要」（一行），执行后做差异分析时才用语义而非表面比较。

---

## 4. 改进方案：从 Hierarchical Planning（P2）出发

### 4.1 🔴 分层规划合约

**灵感来源**：P2 §4 Multi-Scale Planning（70% vs 0%）

**问题**：当前任务规划是**单层链**——没有显式的高中低三层，误差在长链上累积。

**改进**：每个任务执行前转为三层合约：

```
┌─ 高层合约 ──────────────────────────────┐
│ 目标: 完成 §17 飞书验收                   │
│ 判断标准: /new→health_check→context_usage │
│ 全部返回预期值                            │
└──────────────────┬──────────────────────┘
                   │ 分解
                   ▼
┌─ 中层合约 ──────────────────────────────┐
│ 策略:                                     │
│ Step 1: 发 /new                          │
│ Step 2: mimir_ops(health_check, quick)    │
│ Step 3: mimir_ops(context_usage)          │
└──────────────────┬──────────────────────┘
                   │ 分解
                   ▼
┌─ 低层合约 ──────────────────────────────┐
│ 工具: 具体的 tool 调用参数                │
│ 预期: 每步返回 ok:true                    │
└─────────────────────────────────────────┘
```

**合约反馈机制**：低层完成后 → 反馈「ok/error/surprise」给中层 → 中层决定重试/换策略/上报给高层 → 高层决定继续/变更目标/终止。

### 4.2 🟡 MVP 模板化

**灵感来源**：P2 — 跨尺度信息传递

**改进**：将高频任务类型预编译为 MVP 模板，避免每次从零构造三层合约：

| 任务类型 | 模板 | 状态 |
|---------|------|------|
| 冒烟验收 | /new → health_check → context_usage | ✅ 已有 |
| 论文研读 | search → extract → analyze → compare | 🟡 建议 |
| 代码修复 | reproduce → diagnose → fix → verify | 🟡 建议 |

---

## 5. 改进方案：从 H-JEPA（P3）出发

### 5.1 🟡 预测式检索（从回放到预测）

**灵感来源**：P3 — 抽象表征预测（非回放）

**问题**：当前 `session_search` 是被动的——用户问了才搜。H-JEPA 的核心是主动预测。

**改进**：在回复末尾隐式添加预测步骤：

```
完成当前回复后：
1. 预测：基于刚完成的这步，用户下一步可能需要什么？
2. 预热：用这个预测做 session_search
3. 缓存：如果命中，预加载到上下文边缘（不显示，但 ready）
```

**实现代价**：低——只是多一次 `session_search` 调用 + 一个 prompt 让模型预测关键词。

### 5.2 🟢 不确定性显式化

**灵感来源**：P3 能量函数（天然给出不确定性）

**问题**：当前 Mimir 没有「我有多不确定」的显式信号。

**改进**：在 `degeneration_guard` 中加入「不确定性维度」：

```
每次回复后评估：
- LVU（语言化不确定性）得分：回复中 hedging 词密度
- Consistency 得分：对关键判断做 2 次采样，一致 = 确定
- 证据充分性：检索到的 memory 条数
```

三合一输出一个 `confidence: high/medium/low`，低置信度时自动触发学习行动。

---

## 6. 改进方案：从 World Models 2018（P4）出发

### 6.1 🟢 受控检索噪声

**灵感来源**：P4 温度 τ（τ=0.1 翻车 · τ=1.15 最佳）

**问题**：当前 `session_search` 的匹配太精确——用户换个说法就歪了。

**改进**：给检索加入可控噪声参数 `τ_search`：

| τ | 行为 | 适用场景 |
|---|------|---------|
| 0.0 | 精确匹配，只返回最高分 | 已知路径、固定语法 |
| 0.5 | 默认，Top-5 后 heuristic 排序 | 常规对话 |
| 1.0 | 宽松检索，Top-15 再过滤 | 模糊描述、新领域 |

等价于做了对抗鲁棒性训练——不让检索坍缩到同一个点。

---

## 7. 实施路线图

### Phase 1（优先级高，核心闭环）

| 序号 | 改进 | 难度 | 依赖 | 预期效果 |
|------|------|------|------|---------|
| 1.1 | Surprise → 学习 | 低 | `memory.save_surprise_event()` | 同一场景不再二次 surprise |
| 1.2 | 分层规划合约 | 中 | 现有的 `executing-plans` 技能改造 | 长任务误差不累积 |
| 1.3 | MVP 模板化 | 低 | 现有 `backlog-runner` 对齐 | 高频任务不再每次立项 |

### Phase 2（优先级中）

| 序号 | 改进 | 难度 | 依赖 | 预期效果 |
|------|------|------|------|---------|
| 2.1 | 预测式检索 | 中 | `session_search` + prompt 改造 | 主动预热，减少等待 |
| 2.2 | 信息密度 → 探索 | 低 | `degeneration_guard` 回调 | 对话不陷入循环 |
| 2.3 | 不确定性显式化 | 中 | LVU 分析器 | 自我校准 |

### Phase 3（锦上添花）

| 序号 | 改进 | 难度 | 依赖 | 预期效果 |
|------|------|------|------|---------|
| 3.1 | 受控检索噪声 τ | 低 | search params 加参数 | 模糊描述匹配率提升 |
| 3.2 | VoE 表面/语义加固 | 低 | 预期摘要显式化 | surprise 误报减少 |

---

## 附录 A：阅读指南（给后续参与人员）

### 第一步：读论文

按 P1 → P2 → P3 → P4 顺序，每篇只看以下章节：

| 论文 | 必读 | 速读 | 略过 |
|------|------|------|------|
| P1 LeWM | §3.1 SIGReg · §5.2 VoE | §2 相关工作 | §4 实验（太多图） |
| P2 Hierarchical Planning | §4 Multi-Scale | §1 Intro · §5 结果 | §6 附录 |
| P3 H-JEPA | §3 JEPA · §5 抽象预测 | §1-2 动机 | §6-7 数学推导 |
| P4 World Models | §3 V-M-C · 温度 τ | §4 实验 | §2 相关工作 |

### 第二步：读本方案

按 §3 → §4 → §5 → §6 顺序。每个改进点的开头标有该点对应哪篇论文的哪一节。

### 第三步：读现有实现

- `agent/degeneration_guard.py` — 检测引擎
- `data/degeneration_guard.json` — 配置（对标 SIGReg/VoE）
- `~/.mimiraether/research/world-models-reading-list.md` — 前一版的完整阅读笔记
- `docs/MIMIR_LIU_CURSOR_BRIDGE.md` — 刘哥 ↔ Mimir ↔ Cursor 三方对话记录

---

## 附录 B：关键词速查

| 关键词 | 出处 | 定义 |
|--------|------|------|
| SIGReg | P1 §3.1 | 强制潜表示匹配各向同性高斯 → 防止表征坍塌 |
| VoE | P1 §5.2 | Violation-of-Expectation：检测语义意外，区别表面变化 |
| 分层规划 | P2 §4 | 多时间尺度规划，90%→70% 提升 |
| 抽象表征预测 | P3 §3/P5 | 在潜空间预测而非像素空间 |
| 温度 τ | P4 §3 | 控制虚拟环境噪声，τ 低 → overfit，τ 高 → robust |
| 能量函数 | P3 | EBM 用能量而非概率建模可能性 |
| SURPRISE | 本方案 | 语义意外 → 触发学习事件而非仅告警 |
| MVP 模板 | 本方案 | 高频任务的三层合约模板 |
| τ_search | 本方案 | 检索噪声参数，类比 WM 的温度 τ |
