# 健康反馈闭环 — 修正实现计划

基于三篇论文（DreamerV3、Decision Transformer、Plan2Explore）修正的三环闭环。

## 1. 修正后的架构

```
                    ┌──────────────────────────────────────┐
                    │          World Model (LWM)            │
                    │  ﹣ 分层时间尺度 (token/step/episode)  │
                    │  ﹣ 多样性正则化 (entropy bonus)       │
                    │  ﹣ 密集预测loss (token-level)         │
                    └──────────┬───────────────────────────┘
                               │ 预测误差 / 不确定性
    ┌──────────────────────────┼──────────────────────────┐
    │       Monitor Ring       │      Decision Ring       │
    │  (密集token级监控)        │  (分层策略决策)           │
    │  ・soft_beat → 序列化     │  ・token级: 即时纠偏       │
    │  ・token级预测误差        │  ・step级: 策略切换        │
    │  ・episode级趋势          │  ・episode级: 演化方向     │
    └──────────────────────────┴──────────────────────────┘
                               │
                    ┌──────────┘
                    ▼
               Execution Ring
               (多样性驱动执行)
               ・熵正则化策略采样
               ・探索 vs 利用平衡
               ・效果验证 + 回滚
```

### 三篇论文的修正点

| 原三环 | 问题 | 论文修正 |
|--------|------|---------|
| 单层监控 | 无法区分瞬时抖动 vs 趋势漂移 | DreamerV3 分层时间尺度 (token/step/episode) |
| 单一策略选择 | 陷入局部最优 | 多样性正则化 (Decision Transformer entropy bonus) |
| 事件级loss | 反馈稀疏、延迟 | 密集预测loss (token-level prediction error) |
| 被动等待异常 | 无主动探索 | Plan2Explore 不确定性驱动探索 |

## 2. 每个环的具体职责与频率

### Monitor Ring (密集token级)

**触发频率**: 每次工具调用后（复用 soft_beat）

做什么:
- 记录每个工具调用的 token 级指标（耗时、状态、预测误差）
- 每 N 步计算 step 级聚合（滑动窗口均值、方差）
- 每 episode 结束时计算 episode 级趋势（退化斜率、能力漂移）

三个时间尺度:
```
token级: soft_beat.log 每行 ← 已有，扩展字段
step级:  window_metrics.json (N=50步滑动窗口) ← 新增
episode级: episode_summary.json (会话级别)    ← 新增
```

### Decision Ring (分层策略)

**触发频率**: 
- token级: 实时（异常值立即响应）
- step级: 每50步（策略微调）
- episode级: 会话结束时（演化方向决策）

做什么:
- token级: 预测误差 > 阈值 → 立即纠偏（回滚/重试/切换方法）
- step级: 滑动窗口指标 → 策略切换（调整探索率/温度/路由）
- episode级: 趋势分析 → 演化方向（生成胶囊/更新技能/代码重构）

### Execution Ring (多样性驱动)

**触发频率**: 按需（Decision Ring 触发后执行）

做什么:
- 策略采样时不取 argmax，而是用熵正则化采样（保留多样性）
- 执行后验证效果，记录 effectiveness_score
- 失败时回滚，并将该路径标记为低分（避免重复踩坑）

## 3. 第一周最小可跑版本

### 文件清单

```
mimicore/evolve/
├── __init__.py
├── three_ring_architecture.py   ← 已有，需修正
├── monitor_collector.py         ← 已有，需修正
├── self_evolution.py            ← 已有，需修正
├── feedback_closed_loop.py      ← 新增：闭环编排器
├── layered_monitor.py           ← 新增：分层时间尺度监控
├── diversity_executor.py        ← 新增：多样性驱动执行
└── tests/
    └── test_feedback_closed_loop.py  ← 新增：集成测试
```

### 最小可跑定义

1. `layered_monitor.py`: 从 soft_beat.log 读取，按 token/step/episode 三级聚合
2. `feedback_closed_loop.py`: 编排器，串联 monitor → decision → execution
3. 能跑通一次完整的监控→决策→执行流程（用模拟数据）
4. 验证：分层聚合结果正确 + 闭环至少走完一圈

### 不做（后续周）

- 不做真实 LLM 决策（第一周用规则决策）
- 不做自动回滚（第一周只记录不执行）
- 不做技能生成（第一周只输出建议）
- 不做 UI/可视化

## 4. 与已有心跳基座的关系

### 数据流

```
soft_beat.py (已有)
  │  每次工具调用后写入一行到 soft_beat.log
  ▼
layered_monitor.py (新增)
  │  从 soft_beat.log 读取原始 token 级数据
  │  按 N=50 聚合为 step 级窗口指标
  │  按会话边界聚合为 episode 级趋势
  ▼
feedback_closed_loop.py (新增)
  │  读取三层指标 → 触发 Decision Ring
  │  Decision Ring → Execution Ring
  ▼
capability_snapshot.py (已有)
  │  每50步触发（保持原有逻辑）
  │  新增：snapshot 中嵌入 episode 级趋势摘要
```

### 不破坏的契约

1. `soft_beat.py` 和 `log_beat.py` 不动——只新增读取端
2. `capability_snapshot.py` 不动——只在其输出中嵌入新数据
3. 现有 `MonitorCollector` 和 `MonitorRing` 作为 fallback 保留
4. 新 `layered_monitor` 与旧 `MonitorRing` 可并行运行

### 集成点

| 心跳组件 | 与反馈闭环关系 |
|----------|--------------|
| soft_beat.log | 原始数据源（token级） |
| capability_snapshot | 每50步触发一次，嵌入趋势摘要 |
| MonitorCollector | 作为 step 级指标的补充来源 |
| MonitorRing | fallback，当 layered_monitor 不可用时降级 |

## 5. 第一周实施步骤

```
Day 1: layered_monitor.py — 三层聚合读取 soft_beat.log
Day 2: feedback_closed_loop.py — 编排器 + 规则决策
Day 3: diversity_executor.py — 策略采样 + 效果记录
Day 4: 集成测试 + 修正 three_ring_architecture.py
Day 5: 验证：闭环走通 + 分层聚合正确
```
