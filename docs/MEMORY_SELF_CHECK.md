# MimirAether 三层记忆自检协议

> **来源**: V-JEPA 2.1 (2603.14482) §3.1 Dense Predictive Loss + §3.2 Deep Self-Supervision
> **日期**: 2026-05-14
> **状态**: 已定义，集成中

---

## 0. 核心原理（论文 → MimirAether 映射）

| V-JEPA 2.1 发现 | MimirAether 映射 |
|----------------|-----------------|
| 只监督最终层 → 中间层信息退化 (变成 register tokens) | 只检查 Wiki 质量 → Session/Cross-session 记忆可能已腐坏 |
| 密集预测损失: visible + masked tokens 都参与 loss | 密集信息损失: 原始输入 + 压缩中间态 + 最终持久化 都参与质量评分 |
| 深层自监督: 编码器多个中间层有独立监督目标 | 层级自检: Session / Cross-session / Wiki 各有独立质检 |
| 距离加权: 靠近关键 token 的预测权重更高 | 靠近用户决策的信息节点权重更高 |

---

## 1. 三层架构

```
Layer 1: Session 记忆 (会话上下文)
  ├── 存储: 当前对话消息 + 工具调用历史
  ├── 压缩: context_compressor (头尾保护 + 中间摘要)
  ├── 自检: 压缩后关键实体可恢复性
  └── 指标: 实体保留率、信息密度

Layer 2: Cross-Session 记忆 (跨会话持久化)
  ├── 存储: persistent.json / ground_truth.json / sessions_search.db
  ├── 压缩: key_decisions 提取 + 过期机制
  ├── 自检: 决策可追溯性、记忆新鲜度
  └── 指标: 决策追溯率、stale 记忆比例

Layer 3: Wiki (长期知识库)
  ├── 存储: ~/wiki/ (concepts / entities / comparisons)
  ├── 压缩: auto-archive 从 learnings/ + 对话提取
  ├── 自检: 引用完整性、概念覆盖度
  └── 指标: 孤立页面率、引用断裂率
```

---

## 2. 密集信息损失 (Dense Information Loss)

**类比 V-JEPA 2.1**: ALL tokens get loss signal, not just masked ones.

**MimirAether 实现**:

```
信息流追踪:
  原始对话 ──→ 上下文压缩 ──→ 关键决策提取 ──→ Wiki 归档
     │              │                │              │
     │         Layer 1 质检      Layer 2 质检    Layer 3 质检
     │         (保留率)           (可追溯性)      (完整性)
     │              │                │              │
     └──────────────┴────────────────┴──────────────┘
                    密集信息损失评分
                    (加权合成三层得分)
```

**评分公式**:

```
密集信息损失 = Σ wᵢ × lossᵢ

w₁ = 0.5  (Session — 离用户最近，权重最高)
w₂ = 0.3  (Cross-session — 中等距离)
w₃ = 0.2  (Wiki — 最远，参考性质)

lossᵢ = 1 - quality_scoreᵢ  (0-1, 越低越好)

阈值:
  < 0.3 → ✅ 信息保留良好
  0.3-0.6 → ⚠️ 需要关注
  > 0.6 → 🔴 记忆退化告警
```

---

## 3. 层级自检细则

### Layer 1: Session 自检

| 检查项 | 方法 | 阈值 | 动作 |
|--------|------|------|------|
| 实体保留率 | 压缩后能否回溯原始关键实体(任务/文件/决策) | ≥80% | <80%: 增加 HEAD 保留 |
| 信息密度 | 最近N轮是否引入新工具/文件/概念 | 每4轮≥2 | 不足: 触发 MVA |
| 压缩频率 | 是否过频压缩(>1次/3轮) | ≤1/3轮 | 过频: 提高阈值 |

**集成点**: `agent/context_compressor.py` — `compress()` 后执行自检

### Layer 2: Cross-Session 自检

| 检查项 | 方法 | 阈值 | 动作 |
|--------|------|------|------|
| 决策追溯性 | key_decisions 能否回溯到源会话 | ≥90% | <90%: 标记 orphaned |
| 记忆新鲜度 | 最近3会话引用的记忆占比 | ≥30% | <30%: 归档休眠 |
| 文件完整性 | ground_truth ↔ persistent 是否一致 | 100% | 不一致: 触发调和 |

**集成点**: `cross_session_memory.py` — 每次 `save()` 后执行自检

### Layer 3: Wiki 自检

| 检查项 | 方法 | 阈值 | 动作 |
|--------|------|------|------|
| 孤立页面率 | 未被 index.md 引用的页面占比 | ≤10% | >10%: 更新 index |
| 引用断裂率 | 页面间的 [[wikilink]] 目标不存在 | ≤5% | >5%: 修复或删除 |
| 概念覆盖度 | learnings/ 中有 wiki 对应的比例 | ≥50% | <50%: 触发批量归档 |

**集成点**: `wiki-auto-archive` — 每次归档后执行自检

---

## 4. 缩放监控 (Scale Validation)

**类比 V-JEPA 2.1**: 随着模型和数据规模增长，质量是否持续提升？

| 维度 | 监控指标 | 基线 | 告警线 |
|------|---------|------|--------|
| 会话数增长 | 平均信息密度趋势 | 当前值 | 下降 > 20% |
| 技能数增长 | Skill Curator stale 比例 | <10% | >20% |
| Wiki 页面增长 | 孤立页面率趋势 | <10% | >15% |
| 记忆条目增长 | key_decisions 可追溯率 | >90% | <80% |

**集成点**: `skills_qa.py` — 增加缩放趋势指标
**检查频率**: 每 10 会话 或 手动触发

---

## 5. 实施优先级

| 优先级 | 检查项 | 集成点 | 改动量 |
|--------|--------|--------|--------|
| P0 | Layer 1 信息密度 | degeneration_guard (✅ 已完成) | 0 |
| P1 | Layer 2 记忆新鲜度 | cross-session save() | ~10行 |
| P1 | Layer 1 实体保留率 | context_compressor compress() | ~20行 |
| P2 | Layer 3 Wiki 孤立页面 | wiki-auto-archive | ~15行 |
| P2 | 缩放监控 | skills_qa.py | ~30行 |
| P3 | 密集信息损失加权评分 | 新模块或 skill | 设计 |

---

## 6. 修订记录

| 日期 | 变更 |
|------|------|
| 2026-05-14 | 初稿：三层自检协议 + 密集信息损失 + 缩放监控 |
