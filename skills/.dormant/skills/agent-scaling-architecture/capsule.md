# [DORMANT] agent-scaling-architecture

**沉寂时间**: 2026-11-22T02:34:57.830121+00:00
**原始分类**: skills
**描述**: Google 180 配置实证——Agent 架构选型（单 vs 多 agent）科学决策。设计 agent 系统/决定用单 agent 还是多 agent/架构评审时用。
**触发阈值**: 60天未触碰

---

## 技能要点

# Agent 架构选型（Google scaling——180 配置实证）

> **来源**：Google Research《Towards a Science of Scaling Agent Systems》（2026-01——arXiv 2512.08296——PDF 在 `~/wiki/raw/agent-architecture/B1-*`）
> **核心结论**："更多 agent 更好"是迷思——**任务性质决定架构**——并行任务多 agent 提升/顺序任务退化

## 五种架构速查

| 架构 | 机制 | 错误放大 | 适用 |
|:--|:--|:--|:--|
| **单 agent（SAS）** | 统一记忆流顺序执行 | 基线 | 顺序任务/工具密集任务 |
| **独立（Independent）** | 并行无通信——末尾聚合 | **17.2x** ⚠️ | 极少用（错误不可控）|
| **集中式（Centralized）** | hub-and-spoke——orchestrator 委派+综合 | 4.4x | **并行可分解任务**（研究/多源）|
| **去中心（Decentralized）** | 点对点协商 | 高 | 需共识场景（辩论）|
| **混合（Hybrid）** | 层级监督+点对点 | 中 | 复杂混合任务 |

## 三大实证原则

1. **对齐原则**：并行可分解任务（Finance-Agent）→ 集中式 +80.9%（vs 单 agent）
2. **顺序惩罚**：严格顺序任务（PlanCraft）→ 所有多 agent 变体 **-39~-70%**（通信开销碎片化推理——认知预算不够）
3. **工具瓶颈**：任务工具越多（16+）→ 多 agent 协调税越大（tool-coordination trade-off）

## 选型决策（可操作）

```
1. 任务可分解为独立子任务？→ 是（并行）→ 集中式多 agent
2. 任务严格顺序（依赖链）？→ 是 → 单 agent（多 agent 反而退化）
3. 工具数量 >16？→ 协调税高——优先单 agent + 批量工具（execute_code）
4. 错误风险高？→ 集中式（orchestrator=验证瓶颈——错误放大 4.4x vs 17.2x）
```

## 与我们系统对照

- 四方协作 = **集中式**（Hermes orchestrator）——实证正确（错误放大 4.4x 优于独立 17.2x）
- Mimir 任务多为顺序性（读卡→分析→落盘）→ **单 agent 最优**——并行只用于可并行子任务（多源调研/批量验证）
- **工具瓶颈启示**：Mimir 工具多 → 批量读（execute_code）比多 agent 更优
- 预测模型：R²=0.513——用任务属性（工具数/可分解性）预测——87% 正确

## 反模式
- ❌ 盲目加 agent（"more agents is all you need"是迷思）
- ❌ 顺序任务用多 agent（-70%）
- ❌ 独立并行无校验（17.2x 错误放大）
- ❌ 高工具密度还用多 agent（协调税）

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("agent-scaling-architecture")` 即可自动唤醒。
