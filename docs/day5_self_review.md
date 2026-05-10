# Day 5 自查报告

## 1. 三个模块及连接关系
- **session_aggregator** (scripts/session_aggregator.py): 4980B, 151行
  - 功能：读取 raw_session_logs.jsonl，做三层聚合（token级/step窗口级/episode级），输出3个 jsonl 文件
  - 输入路径: data/raw_session_logs.jsonl
  - 输出路径: data/step_aggregation.jsonl, data/step_window.jsonl, data/episode_aggregation.jsonl

- **feedback_orchestrator** (mimicore/evolve/feedback/feedback_orchestrator.py): 10044B, 315行
  - 功能：读取聚合后的三层数据（json 格式），基于规则做三层独立决策
  - 输入路径: mimicore/evolve/feedback/aggregator_outputs/{token,step,episode}_level.json
  - 输出路径: mimicore/evolve/feedback/decisions/decision_log.json

- **diversity_executor** (mimicore/evolve/diversity_executor.py): 21714B, 689行
  - 功能：读取 decision_log.json 中的触发信号，用熵正则化采样选择策略（retry/switch/downgrade）
  - 输入路径: mimicore/evolve/feedback/decisions/decision_log.json
  - 输出：ExecutionRecord（内存 + 日志）

**连接关系**（数据流）:
```
raw_session_logs.jsonl
  → session_aggregator (三层聚合)
    → {step,step_window,episode}_aggregation.jsonl
      → feedback_orchestrator (读取 jsonl 但期望 json)
        → decision_log.json
          → diversity_executor (熵采样执行)
```

## 2. 未连接/不一致的地方

1. **数据格式不匹配（严重）**:
   - session_aggregator 输出的是 **jsonl**（每行一个json对象），但 feedback_orchestrator 的 `load_all_levels()` 调用 `load_json()`（即 `json.load()`），期望的是 **json 数组/对象**。两者直接无法对接。
   - aggregator 输出的字段名（如 `level`, `session_id`, `error_rate`）与 orchestrator 期望的字段名（如 `step_id`, `tokens`, `rolling_windows`, `episode_id`, `tool_distribution`）完全不匹配。

2. **路径不一致**:
   - session_aggregator 的输出在 `data/` 目录下
   - feedback_orchestrator 的输入在 `mimicore/evolve/feedback/aggregator_outputs/` 目录下
   - 没有任何桥梁代码将 aggregator 输出搬运/转换到 orchestrator 输入目录

3. **数据模型脱节**:
   - session_aggregator 输出的是时序聚合指标（avg_duration, error_rate, tool_distribution 等）
   - feedback_orchestrator 期望的是带 `step_id`, `tokens[].error`, `rolling_windows[].trend`, `episodes[].episode_id` 的嵌套结构
   - 两个模块对"token/step/episode"的定义不同：aggregator 的 token=一行日志, step=50行滑动窗口, episode=按 session_id 分组；orchestrator 的 token=带 confidence 的 token 级数据, step=带 trend 的滚动窗口, episode=带 episode_id 的独立会话

4. **diversity_executor 的默认路径**:
   - `_default_log_path()` 硬编码为 `mimicore/evolve/feedback/decisions/decision_log.json`，这个路径在 orchestrator 中存在，但如果直接运行 executor 而 orchestrator 未运行过，路径不存在且无回退

5. **缺少端到端集成入口**:
   - 没有统一的脚本/入口串联三个模块
   - 每个模块可以独立运行，但无法一键完成 aggregator → orchestrator → executor 全流程

## 3. 真实运行还缺什么

1. **数据格式适配器/桥梁**:
   - 需要一个转换层：aggregator 的 jsonl 输出 → orchestrator 期望的 json 格式
   - 字段映射：`session_id` → `episode_id`, `error_rate` → 各层期望的 error 字段, `tool_distribution` → 嵌套 dict

2. **真实数据**:
   - 目前没有 `data/raw_session_logs.jsonl` 文件
   - orchestrator 和 executor 在没有输入数据时只能走模拟/默认路径

3. **错误处理**:
   - aggregator: 无异常处理，文件不存在直接 crash
   - orchestrator: `load_json()` 无异常处理，文件不存在直接 crash
   - executor: 有基本异常处理，但 `_simulate_execution()` 使用 random，不可复现

4. **日志/监控**:
   - aggregator 用 print 输出，orchestrator 用 print + json 文件，executor 用 logging
   - 三个模块的日志风格不一致，不利于统一监控

5. **测试**:
   - 三个模块均无单元测试
   - executor 的 `_simulate_execution()` 用 random 难以测试

6. **配置集中管理**:
   - 路径散落在各模块中硬编码
   - 没有统一的 config 或环境变量入口

7. **回退机制**:
   - 如果某层聚合失败，下游没有优雅降级
   - executor 在无信号时生成模拟信号，可能掩盖配置问题

## 4. 自评分(1-10)

**评分：5/10**

**得分项（+）**:
- 三层架构清晰，关注点分离：聚合 → 决策 → 执行
- 每个模块内部设计合理（熵正则化采样、三层独立决策、滑动窗口聚合）
- diversity_executor 代码质量较高（dataclass、类型注解、设计模式清晰）
- 有模块级 demo/入口，可独立运行验证

**扣分项（-）**:
- **数据格式不匹配（-2）**: aggregator 输出 jsonl，orchestrator 期望 json，字段名完全不一致。这是最严重的断裂。
- **路径硬编码无集中管理（-1）**: 三个模块各用各的路径，无统一配置
- **无端到端集成（-1）**: 没有一键运行脚本
- **无测试（-0.5）**: 三个模块均无单元测试
- **无真实数据（-0.5）**: 依赖模拟数据运行

**改进优先级**:
1. 创建数据格式适配器（jsonl → json + 字段映射）
2. 统一路径配置（config.yaml 或环境变量）
3. 添加端到端运行脚本
4. 添加单元测试（至少 aggregator + orchestrator）
