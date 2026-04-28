# MimirAether 自我迭代计划
## 基于Hermes三环闭环模式的全面演进路线图

**制定日期**: 2026-04-28  
**版本**: v1.0  
**目标**: 建立完整的自我感知、自我决策、自我执行闭环

---

## 一、Hermes三环闭环模式深度分析

### 1.1 监控环 (Monitor Ring)

**Hermes实现**:
```
hermes_agent/agent/
├── insights.py (洞察引擎)           - 使用模式分析
├── usage_pricing.py (成本追踪)      - USD实时估算
├── rate_limit_tracker.py (限流追踪) - API限制监控
└── memory_manager.py (记忆管理)     - 记忆状态监控

hermes_agent/environments/
└── agent_loop.py (AgentResult)     - 完整执行元数据
```

**核心监控指标**:
- `turns_used`: LLM调用次数
- `tool_errors`: 工具错误记录
- `reasoning_per_turn`: 每轮推理内容
- `finished_naturally`: 自然结束标志
- `managed_state`: 托管状态快照

**监控数据持久化**: `hermes_state.py` - SQLite + FTS5

---

### 1.2 决策环 (Decision Ring)

**Hermes实现**:
```
hermes_agent/agent/
├── error_classifier.py (错误分类)      - 错误模式识别
├── smart_model_routing.py (模型路由)   - 模型选择决策
└── prompt_builder.py (提示构建)        - 决策上下文构建

hermes_agent/trajectory_compressor.py    - 轨迹压缩决策
```

**决策类型**:
1. **错误恢复决策**: 错误分类 → 恢复策略匹配 → 执行
2. **模型选择决策**: 任务复杂度评估 → 模型能力匹配 → 成本优化
3. **压缩决策**: Token预算 → 摘要策略 → 质量阈值

---

### 1.3 执行环 (Execution Ring)

**Hermes实现**:
```
hermes_agent/model_tools.py              - 工具执行分发
hermes_agent/environments/agent_loop.py  - 完整执行循环
hermes_agent/cron/
├── jobs.py (定时任务)                 - 周期性执行
└── scheduler.py (调度器)              - 执行调度
```

**执行模式**:
- **同步执行**: ThreadPoolExecutor (128 workers)
- **异步执行**: async/await
- **批量执行**: batch_runner.py
- **定时执行**: cron scheduler

---

### 1.4 反馈闭环 (Feedback Loop)

**Hermes实现**:
```
hermes_agent/trajectory_compressor.py
├── 轨迹收集 → 压缩 → 保存
└── 用于RL训练数据

hermes_agent/cron/jobs.py
├── 任务完成 → 触发后续任务
└── 状态反馈
```

---

## 二、MimirAether现有模块对照

### 2.1 已有模块清单

| 模块 | 位置 | 状态 | 说明 |
|------|------|------|------|
| `MonitorRing` | `mimicore/evolve/three_ring_architecture.py` | ⚠️ 框架级 | 仅骨架，指标收集未实现 |
| `DecisionRing` | `mimicore/evolve/three_ring_architecture.py` | ⚠️ 框架级 | 仅骨架，策略库未完善 |
| `ExecutionRing` | `mimicore/evolve/three_ring_architecture.py` | ❌ 不完整 | 类未完成 |
| `ThreeRingClosedLoop` | `mimicore/evolve/three_ring_architecture.py` | ❌ 未实现 | 缺失 |
| `ProactiveKnowledgeCorrector` | `mimicore/evolve/self_evolution.py` | ⚠️ 部分实现 | 置信度评估+RAG验证 |
| `IntentPredictor` | `mimicore/evolve/self_evolution.py` | ⚠️ 部分实现 | 基于规则的预测 |
| `AutomatedRootCauseFixer` | `mimicore/evolve/self_evolution.py` | ⚠️ 部分实现 | 基础修复流程 |
| `AutonomousRepairExecutor` | `mimicore/evolve/self_evolution.py` | ⚠️ 部分实现 | 沙箱模拟缺失 |
| `SessionDB` | `hermes_state.py` | ✅ 已实现 | SQLite + FTS5 |
| Cron | `cron/` | ⚠️ 基础实现 | 简单的jobs.json |

### 2.2 关键差距

| 差距 | 严重度 | 说明 |
|------|--------|------|
| 三环未闭环 | 🔴 Critical | 三个环之间无数据流连接 |
| 执行环缺失 | 🔴 Critical | ExecutionRing类不完整 |
| 监控指标未采集 | 🔴 Critical | 无系统指标收集器 |
| 决策策略库不完善 | 🟠 Major | 策略过于简单，无学习能力 |
| 反馈机制缺失 | 🟠 Major | 无执行结果反馈到监控 |
| 调度器缺失 | 🟠 Major | cron/scheduler.py未实现 |

---

## 三、完整迭代清单

### Phase 0: 基础设施 (Foundation)
**时间估计**: 1周  
**依赖**: 无

| # | 任务 | 优先级 | 复杂度 | 估计时间 | 依赖 |
|---|------|--------|--------|----------|------|
| P0-1 | 创建`MonitorCollector` - 系统指标采集器 | P0 | 中 | 4h | 无 |
| P0-2 | 实现`ExecutionRing.execute()` - 完整执行环 | P0 | 中 | 6h | P0-1 |
| P0-3 | 实现`ThreeRingClosedLoop.run()` - 闭环串联 | P0 | 高 | 8h | P0-1, P0-2 |
| P0-4 | 添加执行结果反馈通道 | P0 | 低 | 2h | P0-3 |

**验证标准**: `python -m mimicore.evolve.tests.test_three_ring_loop` 通过

---

### Phase 1: 监控环完善 (Monitor Enhancement)
**时间估计**: 2周  
**依赖**: Phase 0

| # | 任务 | 优先级 | 复杂度 | 估计时间 | 依赖 |
|---|------|--------|--------|----------|------|
| P1-1 | 集成Hermes `insights.py` 使用模式分析 | P1 | 高 | 8h | P0 |
| P1-2 | 集成Hermes `rate_limit_tracker.py` 限流监控 | P1 | 中 | 4h | P0 |
| P1-3 | 添加自定义指标收集钩子 | P1 | 中 | 6h | P1-1 |
| P1-4 | 实现指标阈值动态调整 | P2 | 高 | 8h | P1-3 |

**验证标准**: MonitorRing可收集10+种系统指标

---

### Phase 2: 决策环增强 (Decision Enhancement)
**时间估计**: 2周  
**依赖**: Phase 1

| # | 任务 | 优先级 | 复杂度 | 估计时间 | 依赖 |
|---|------|--------|--------|----------|------|
| P2-1 | 集成Hermes `error_classifier.py` 错误分类 | P1 | 高 | 8h | P1 |
| P2-2 | 实现基于历史的策略学习 | P2 | 高 | 12h | P2-1 |
| P2-3 | 添加策略效果评估 | P2 | 中 | 6h | P2-2 |
| P2-4 | 实现决策置信度计算 | P2 | 中 | 4h | P2-3 |

**验证标准**: DecisionRing可处理5+种错误类型，策略匹配准确率>80%

---

### Phase 3: 执行环强化 (Execution Enhancement)
**时间估计**: 2周  
**依赖**: Phase 2

| # | 任务 | 优先级 | 复杂度 | 估计时间 | 依赖 |
|---|------|--------|--------|----------|------|
| P3-1 | 完善沙箱模拟机制 | P1 | 高 | 10h | P2 |
| P3-2 | 实现执行回滚能力 | P1 | 中 | 6h | P3-1 |
| P3-3 | 添加执行超时控制 | P1 | 低 | 2h | P3-1 |
| P3-4 | 实现执行重试策略 | P2 | 中 | 4h | P3-3 |

**验证标准**: AutonomousRepairExecutor修复成功率>85%

---

### Phase 4: 反馈与学习 (Feedback & Learning)
**时间估计**: 2周  
**依赖**: Phase 3

| # | 任务 | 优先级 | 复杂度 | 估计时间 | 依赖 |
|---|------|--------|--------|----------|------|
| P4-1 | 实现轨迹收集器 | P1 | 中 | 6h | P3 |
| P4-2 | 集成Hermes `trajectory_compressor.py` | P1 | 高 | 12h | P4-1 |
| P4-3 | 实现闭环效果评估 | P2 | 中 | 6h | P4-2 |
| P4-4 | 添加自适应阈值调整 | P3 | 高 | 10h | P4-3 |

**验证标准**: 轨迹压缩比>4:1，训练信号保留>90%

---

### Phase 5: 调度与自动化 (Scheduling & Automation)
**时间估计**: 1周  
**依赖**: Phase 4

| # | 任务 | 优先级 | 复杂度 | 估计时间 | 依赖 |
|---|------|--------|--------|----------|------|
| P5-1 | 实现`scheduler.py` - 任务调度器 | P1 | 高 | 10h | P4 |
| P5-2 | 添加周期性自检任务 | P2 | 中 | 6h | P5-1 |
| P5-3 | 实现主动式记忆保存 | P2 | 中 | 6h | P5-1 |

**验证标准**: 可配置`every 1h`等调度策略

---

## 四、优先级矩阵

```
                    高影响
                       │
    ┌──────────────────┼──────────────────┐
    │  P0-3 闭环串联  │  P2-1 错误分类  │
    │  P0-2 执行环    │  P3-1 沙箱模拟  │
    │  P0-1 指标采集  │  P4-2 轨迹压缩  │
    │                 │                  │
────┼─────────────────┼──────────────────┼──────► 高紧急度
    │  P2-4 置信度    │  P1-4 动态阈值  │
    │  P3-3 超时控制  │  P4-4 自适应    │
    │  P5-3 记忆保存  │  P5-2 自检任务  │
    │                 │                  │
    └──────────────────┼──────────────────┘
                       │
                    低影响
```

---

## 五、依赖关系图

```
Phase 0 (1周)
    │
    ├── P0-1 MonitorCollector
    │       │
    │       └── P0-2 ExecutionRing
    │               │
    │               └── P0-3 ThreeRingClosedLoop
    │                       │
    │                       └── P0-4 反馈通道
    │                               │
Phase 1 (2周) ◄──────────────────────┘
    │
    ├── P1-1 insights集成
    ├── P1-2 rate_limit集成
    ├── P1-3 指标钩子
    └── P1-4 动态阈值

Phase 2 (2周) ◄────────────────────────┘
    │
    ├── P2-1 error_classifier
    ├── P2-2 策略学习
    ├── P2-3 效果评估
    └── P2-4 置信度

Phase 3 (2周) ◄────────────────────────┘
    │
    ├── P3-1 沙箱模拟
    ├── P3-2 执行回滚
    ├── P3-3 超时控制
    └── P3-4 重试策略

Phase 4 (2周) ◄────────────────────────┘
    │
    ├── P4-1 轨迹收集
    ├── P4-2 压缩器
    ├── P4-3 效果评估
    └── P4-4 自适应

Phase 5 (1周) ◄────────────────────────┘
    │
    ├── P5-1 调度器
    ├── P5-2 自检任务
    └── P5-3 记忆保存
```

---

## 六、关键里程碑

| 里程碑 | 目标日期 | 验收标准 |
|--------|----------|----------|
| M1: 最小闭环 | +1周 | 三环可串联运行，单次迭代成功 |
| M2: 错误恢复 | +3周 | 自动处理5+种常见错误 |
| M3: 自主修复 | +5周 | 修复成功率>85% |
| M4: 轨迹学习 | +7周 | 轨迹可用于RL训练 |
| M5: 自动化 | +8周 | 无人干预运行稳定 |

---

## 七、风险与缓解

| 风险 | 影响 | 概率 | 缓解策略 |
|------|------|------|----------|
| Hermès集成复杂度 | 高 | 中 | 分阶段集成，每个组件单独测试 |
| 性能开销 | 中 | 高 | 使用轻量级指标，采样而非全量 |
| 决策回路振荡 | 高 | 低 | 添加冷却机制和历史约束 |
| 沙箱安全 | 高 | 低 | 严格资源限制和超时 |

---

## 八、成功指标

| 指标 | 当前值 | 目标值 | 测量方法 |
|------|--------|--------|----------|
| 错误自恢复率 | 0% | >90% | 记录恢复成功/失败 |
| 平均修复时间 | N/A | <30s | 执行时间统计 |
| 策略匹配准确率 | ~60% | >85% | 人工评估样本 |
| 轨迹压缩比 | 1:1 | >4:1 | Token计数对比 |
| 闭环迭代周期 | N/A | <5s | 时间戳测量 |

---

## 九、立即行动

### 下一步 (Next Step)

**今天可以开始的工作**:

1. **P0-1: 创建MonitorCollector**
   - 文件: `mimicore/evolve/monitor_collector.py`
   - 指标: memory_usage, context_length, tool_call_count, error_rate, response_time
   - 接口: `async def collect() -> Dict[str, Any]`

2. **P0-2: 完善ExecutionRing**
   - 文件: `mimicore/evolve/three_ring_architecture.py`
   - 添加: `execute()`, `verify()`, `rollback()` 方法

3. **编写测试**
   - 文件: `mimicore/evolve/tests/test_three_ring_loop.py`
   - 覆盖: 正常流程、异常流程、回滚流程

---

## 十、文件结构

```
mimicore/evolve/
├── __init__.py              # 导出
├── self_evolution.py        # 现有自进化模块
├── three_ring_architecture.py  # 三环架构
├── monitor_collector.py     # [新增] 指标采集器
├── decision_policy.py       # [新增] 决策策略库
├── execution_engine.py       # [新增] 执行引擎
├── feedback_loop.py         # [新增] 反馈闭环
├── trajectory_collector.py   # [新增] 轨迹收集
├── scheduler.py             # [新增] 调度器
└── tests/
    ├── test_monitor.py
    ├── test_decision.py
    ├── test_execution.py
    └── test_three_ring_loop.py
```

---

_修订历史_
- v1.0 (2026-04-28): 初始版本，基于Hermes三环闭环模式分析
