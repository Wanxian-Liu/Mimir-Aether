---
name: mimiraether-self_evolution
description: MimirAether 自我进化技能 — 触发条件为用户明确要求自我进化/改进/优化。基于三环闭环架构（MonitorRing→DecisionRing→ExecutionRing），使用 agent 内建模块（monitor_collector / decision_ring / context_compressor）实现知识纠错、根因修复与意图预测。已吸收 three-ring-iteration 的路线图与里程碑。
version: 1.2.0
auto_load: false
---

# Self Evolution Skill

> MimirAether 自我进化技能 | 三环闭环 + agent 内建模块

## 描述

MimirAether 的自我进化核心能力，基于**三环闭环架构**（监控环→决策环→执行环）和**自驱动引擎**（ε-greedy策略选择）实现全自动自我改进。

**核心流程:**
```
收集指标 → 分析差距 → 执行改进 → 验证效果
     ↑                                   |
     └──────────── 反馈循环 ←────────────┘
```

## 触发条件

当用户明确要求自我进化、自我改进、系统优化时触发。

## 核心功能

### 1. collect_metrics() - 收集系统指标

收集 MimirAether 当前运行状态指标。

```python
async def collect_metrics() -> Dict[str, Any]:
    """收集系统指标"""
    metrics = {
        # 基础系统指标
        "memory_usage": psutil.virtual_memory().percent / 100,
        "cpu_usage": psutil.cpu_percent() / 100,
        "context_length": 当前上下文长度比例,
        "session_count": len(active_sessions),

        # 验证失败指标（从 verification 日志读取）
        "verification_failures": self._count_verification_failures(),
        "repeat_tool_calls": self._count_repeat_tool_calls(),
        
        # 进化相关指标
        "cycle_count": three_ring.cycle_count,
        "correction_count": corrector.get_stats().get("total_decisions", 0),
        "success_rate": three_ring.get_stats().get("success_rate", 1.0),
        
        # 性能指标
        "avg_response_time_ms": recent_avg_response_time,
        "error_rate": recent_error_rate,
        
        # 置信度指标
        "avg_confidence": recent_avg_confidence,
        
        "timestamp": time.time()
    }
    return metrics
```

**阈值配置:**
- memory_usage > 0.85 → 异常
- context_length > 0.90 → 异常
- confidence < 0.70 → 异常
- error_rate > 0.05 → 异常

### 2. analyze_gaps() - 分析差距

基于收集的指标，分析需要改进的地方。

```python
async def analyze_gaps(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """分析差距，识别改进方向"""
    gaps = []
    
    # 检测内存压力
    if metrics.get("memory_usage", 0) > 0.85:
        gaps.append({
            "type": "memory_pressure",
            "severity": metrics["memory_usage"] - 0.85,
            "recommendation": "clear_buffer or compact_memory"
        })
    
    # 检测上下文溢出风险
    if metrics.get("context_length", 0) > 0.90:
        gaps.append({
            "type": "context_overflow",
            "severity": metrics["context_length"] - 0.90,
            "recommendation": "truncate_context or compress_history"
        })
    
    # 检测置信度下降
    if metrics.get("avg_confidence", 1.0) < 0.70:
        gaps.append({
            "type": "low_confidence",
            "severity": 0.70 - metrics["avg_confidence"],
            "recommendation": "enable_verification or add_uncertainty_marker"
        })
    
    # 检测成功率下降
    if metrics.get("success_rate", 1.0) < 0.60:
        gaps.append({
            "type": "low_success_rate",
            "severity": 0.60 - metrics["success_rate"],
            "recommendation": "increase_exploration or review_strategies"
        })
    
    # 检测失败原因分类（Kairos 后悔感知模式 — arXiv:2606.16533）
    # 当 collect_metrics 扩展后支持以下分类：
    # "key_not_injected" — API key 注入失败（dream_memory L447）
    # "os_replace_skipped" — 文件替换未执行（_save_persistent）
    # "path_not_found" — 读错了 JSON 嵌套路径
    # "verification_skipped" — 改完后没读盘验证
    failure_types = metrics.get("failure_causes", {})
    known_failures = ["key_not_injected", "os_replace_skipped", "path_not_found", "verification_skipped"]
    for ftype in known_failures:
        count = failure_types.get(ftype, 0)
        if count >= 2:
            gaps.append({
                "type": f"recurring_failure_{ftype}",
                "severity": min(1.0, count * 0.2),
                "recommendation": f"read_before_act — 回退到读盘确认，不继续{ftype}路径"
            })

    # 检测过度验证（同一工具调用 >3 次未改变盘上数据）
    # 指标来源：verification skill 的调用计数器；collect_metrics 需扩展
    repeat_calls = metrics.get("repeat_tool_calls", 0)
    if repeat_calls > 3:
        gaps.append({
            "type": "over_verification",
            "severity": min(1.0, (repeat_calls - 3) * 0.15),
            "recommendation": "read_before_act — 先读盘确认数据是否已变，再决定是否继续验证"
        })
    
    return {
        "gaps": gaps,
        "priority_gap": max(gaps, key=lambda g: g["severity"]) if gaps else None,
        "metrics_snapshot": metrics
    }
```

### 3. execute_improvement(plan) - 执行改进

根据分析结果执行具体改进措施。

```python
async def execute_improvement(plan: Dict[str, Any]) -> Dict[str, Any]:
    """执行改进计划"""
    gap = plan.get("priority_gap", {})
    gap_type = gap.get("type", "unknown")
    
    # 使用决策环生成策略候选
    strategies = await self.three_ring.decision.generate_strategies(
        anomaly_type=gap_type, severity=gap.get("severity", 0.5)
    )
    decision = await self.three_ring.decision.select_best_strategy(strategies)
    
    # 执行
    execution = await self.three_ring.execution.execute(decision, {})
    
    # 记录到知识纠错器
    self.corrector.record_outcome(
        decision.strategy, execution.effectiveness_score,
        context={"gap_type": gap_type}
    )
    
    return {
        "strategy_used": decision.strategy,
        "execution_result": execution.__dict__ if hasattr(execution, '__dict__') else execution,
        "effectiveness": execution.effectiveness_score
    }
```

### 4. verify_result() - 验证结果

验证改进效果，判断是否需要继续迭代。

```python
async def verify_result(
    before: Dict[str, Any],
    after: Dict[str, Any],
    execution: ExecutionOutput
) -> Dict[str, Any]:
    """验证改进效果"""
    
    # 比较关键指标
    improvements = {}
    for key in ["memory_usage", "context_length", "avg_confidence", "success_rate"]:
        if key in before and key in after:
            delta = after[key] - before[key]
            # 方向修正（有些指标下降是好的）
            if key in ["memory_usage", "context_length", "error_rate"]:
                delta = -delta  # 这些越低越好
            improvements[key] = {
                "before": before[key],
                "after": after[key],
                "delta": delta,
                "improved": delta > 0
            }
    
    # 综合判定
    improvement_count = sum(1 for v in improvements.values() if v["improved"])
    verification_passed = (
        execution.verification_passed and
        improvement_count >= len(improvements) / 2 and
        execution.effectiveness_score >= 0.7
    )
    
    return {
        "verification_passed": verification_passed,
        "effectiveness_score": execution.effectiveness_score,
        "improvements": improvements,
        "recommendation": "continue" if not verification_passed else "success"
    }
```

## 集成架构

### 三环闭环 (ThreeRingClosedLoop)

```
┌─────────────────────────────────────────────────────────────┐
│                      三环闭环                                │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   监控环     │───▶│   决策环     │───▶│   执行环     │    │
│  │ MonitorRing │    │DecisionRing │    │ExecutionRing│    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│         │                                     │             │
│         │              反馈循环               │             │
│         └─────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

**监控环 (MonitorRing):**
- `observe()` - 观察当前状态
- `detect_anomalies()` - 检测异常
- 可配置阈值: memory_usage, context_length, confidence, error_rate

**决策环 (DecisionRing):**
- `analyze_root_cause()` - 分析根因
- `generate_strategies()` - 生成策略候选
- `select_best_strategy()` - 选择最优策略
- 内置决策库映射异常类型→策略

**执行环 (ExecutionRing):**
- `execute()` - 执行修复
- `verify()` - 验证效果
- 内置18种执行器

### 知识纠错器 (ProactiveKnowledgeCorrector) 与修复执行器

> 真源：`agent/monitor_collector.py`（监控环）及 `agent/decision_ring.py`（决策环）。以下为技能摘要，具体 API 以代码为准。

```python
from agent.monitor_collector import MonitorCollector
from agent.decision_ring import DecisionRing

collector = MonitorCollector()
ring = DecisionRing()

# 纠错器：根据根因分析修正知识
correction = ring.decide(RootCauseAnalysis(...))

# 修复执行器：执行修复并验证
result = await ring.execute_and_verify(fix_plan)
```

**内置策略:**
| 策略 | 标签 | 基础评分 |
|------|------|---------|
| read_before_act | over_verification | 0.9 |
| clear_buffer | memory | 0.7 |
| compact_memory | memory | 0.65 |
| compress_history | context | 0.8 |
| truncate_context | context | 0.75 |
| enable_verification | quality | 0.85 |
| optimize_query | performance | 0.8 |
| expand_search | retrieval | 0.7 |
| add_uncertainty_marker | confidence | 0.6 |
| parallel_execute | performance | 0.75 |
| use_fallback | fallback | 0.8 |

## 使用方式

### 完整自我进化循环

```python
async def run_self_evolution_cycle():
    """执行一次完整的自我进化循环"""
    
    # 1. 收集指标
    metrics = await collect_metrics()
    
    # 2. 分析差距
    gap_analysis = await analyze_gaps(metrics)
    
    if not gap_analysis["gaps"]:
        return {"status": "no_improvement_needed", "metrics": metrics}
    
    # 3. 执行改进
    improvement = await execute_improvement(gap_analysis)
    
    # 4. 收集新指标
    new_metrics = await collect_metrics()
    
    # 5. 验证结果
    verification = await verify_result(metrics, new_metrics, 
                                       improvement["execution_result"])
    
    return {
        "status": "completed" if verification["verification_passed"] else "needs_retry",
        "gap_analyzed": gap_analysis["priority_gap"],
        "improvement": improvement,
        "verification": verification,
        "metrics_before": metrics,
        "metrics_after": new_metrics
    }
```

### 使用三环闭环引擎

```python
from agent.decision_ring import DecisionRing

# 初始化
ring = DecisionRing()

# 运行闭环周期
result = await ring.run_cycle(context={"task": "self_evolution"})
```

### 查看引擎状态

```python
# 获取三环闭环统计
stats = three_ring.get_stats()
print(f"周期数: {stats['cycle_count']}")
print(f"成功率: {stats['success_rate']:.2%}")

# 获取知识纠错器状态
from agent.decision_ring import get_decision_ring
ring = get_decision_ring()
stats = ring.stats
print(f"总决策: {stats['total_decisions']}")
print(f"成功率: {stats['success_rate']:.2%}")
```

## 实现代码模板

```python
"""
MimirAether Self Evolution Skill
集成三环闭环 + 自驱动引擎
"""

import sys
import time
import asyncio
from pathlib import Path

# 添加项目路径（运行时解析，支持 MIMIR_AETHER_HOME / HERMES_HOME 覆盖）
from mimir_constants import get_mimir_home
PROJECT_ROOT = get_mimir_home()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.monitor_collector import MonitorCollector
from agent.decision_ring import DecisionRing


class SelfEvolutionSkill:
    """MimirAether 自我进化技能"""
    
    def __init__(self):
        self.collector = MonitorCollector()
        self.ring = DecisionRing()
        self._initialized = True
    
    def _count_verification_failures(self) -> dict:
        \"\"\"从 verification_results.jsonl 读取验证失败统计\"\"\"
        import json
        from pathlib import Path
        log_path = Path(get_mimir_home()) / "data" / "verification_results.jsonl"
        if not log_path.exists():
            return {"total": 0, "by_type": {}}
        failures = {"total": 0, "by_type": {}}
        with open(log_path) as f:
            for line in f:
                entry = json.loads(line)
                if not entry.get("passed", True):
                    failures["total"] += 1
                    ftype = entry.get("failure_type", "unknown")
                    failures["by_type"][ftype] = failures["by_type"].get(ftype, 0) + 1
        return failures
    
    def _count_repeat_tool_calls(self) -> int:
        \"\"\"从 verification_results.jsonl 读取同一工具反复调用次数\"\"\"
        import json
        from pathlib import Path
        log_path = Path(get_mimir_home()) / "data" / "verification_results.jsonl"
        if not log_path.exists():
            return 0
        calls = {}
        with open(log_path) as f:
            for line in f:
                entry = json.loads(line)
                tool = entry.get("tool", "unknown")
                if tool not in calls:
                    calls[tool] = []
                calls[tool].append(entry.get("timestamp", ""))
        # 返回同一工具调用次数的最大值
        return max((len(v) for v in calls.values()), default=0)
    
    def _estimate_verification_reliability(self) -> dict:
        """ProEval P1: 量化性能估计 — 用历史验证数据建立贝叶斯估计

        不复制 GP，用频率统计计算：
        - reliability_score: 0-1（近期验证成功率，指数权重）
        - sample_quality: "high"/"medium"/"low"（基于验证样本量）
        - confidence_interval: str（基于近期 95% 区间的粗糙估计）
        """
        from pathlib import Path
        from mimir_constants import get_mimir_home
        log_path = Path(get_mimir_home()) / "data" / "verification_results.jsonl"
        if not log_path.exists():
            return {
                "reliability_score": 0.5,
                "sample_quality": "low",
                "confidence_interval": "n/a (no data)",
                "total_samples": 0
            }
        import json
        recent = []
        with open(log_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    recent.append(entry)
                except json.JSONDecodeError:
                    continue
        if not recent:
            return {
                "reliability_score": 0.5,
                "sample_quality": "low",
                "confidence_interval": "n/a (no data)",
                "total_samples": 0
            }
        # 取最近 max(20, all) 条加权计算
        window = min(len(recent), 20)
        samples = recent[-window:]
        weights = [0.5 + 0.5 * (i / window) for i in range(window)]  # 越近越重
        total_weight = sum(weights)
        passed = sum(
            weights[i] for i, s in enumerate(samples)
            if s.get("passed", True)
        )
        reliability = passed / total_weight if total_weight > 0 else 0.5
        # 样本量分级
        if window >= 20:
            quality = "high"
        elif window >= 10:
            quality = "medium"
        else:
            quality = "low"
        # 粗糙置信区间：n 越大区间越窄
        n = window
        margin = 0.5 / (n ** 0.5 + 1)  # 随 n 增大收敛
        lower = max(0, reliability - margin)
        upper = min(1, reliability + margin)
        return {
            "reliability_score": round(reliability, 3),
            "sample_quality": quality,
            "confidence_interval": f"{lower:.3f}–{upper:.3f}",
            "total_samples": len(recent)
        }

    async def collect_metrics(self) -> dict:
        """收集系统指标"""
        metrics = await self.collector.observe()
        # ProEval P1: 追加量化性能估计
        metrics["verification"] = self._count_verification_failures()
        metrics["repeat_tool_calls"] = self._count_repeat_tool_calls()
        metrics["reliability"] = self._estimate_verification_reliability()
        return metrics

    async def analyze_gaps(self, metrics: dict) -> dict:
        """分析差距"""
        anomalies = await self.collector.detect_anomalies(metrics)

        if not anomalies:
            return {"gaps": [], "priority_gap": None}

        root_cause = await self.ring.analyze_root_cause(anomalies)
        strategies = await self.ring.generate_strategies(root_cause)
        
        return {
            "root_cause": root_cause,
            "strategies": strategies,
            "anomaly_count": len(anomalies)
        }
    
    async def execute_improvement(self, plan: dict) -> dict:
        """执行改进"""
        strategies = plan.get("strategies", [])
        if not strategies:
            return {"status": "no_strategy"}
        
        # 选择最佳策略
        decision = await self.ring.select_best_strategy(strategies)
        execution = await self.ring.execute(decision, {})
        self.ring.record_outcome(
            decision.strategy,
            execution.effectiveness_score
        )
        
        return {
            "decision": decision.__dict__,
            "execution": execution.__dict__
        }
    
    async def verify_result(self, before: dict, after: dict, execution) -> dict:
        """验证结果"""
        verified = await self.ring.verify(execution, {})
        return {
            "verification_passed": verified,
            "effectiveness": execution.effectiveness_score
        }
    
    async def run_cycle(self) -> dict:
        """执行完整进化周期"""
        metrics_before = await self.collect_metrics()
        gap_analysis = await self.analyze_gaps(metrics_before)
        
        if not gap_analysis.get("gaps"):
            return {"status": "healthy", "metrics": metrics_before}
        
        improvement = await self.execute_improvement(gap_analysis)
        metrics_after = await self.collect_metrics()
        
        execution = improvement["execution"]
        verification = await self.verify_result(
            metrics_before, metrics_after, execution
        )
        
        return {
            "status": "completed" if verification["verification_passed"] else "retry_needed",
            "before": metrics_before,
            "after": metrics_after,
            "gap_analysis": gap_analysis,
            "improvement": improvement,
            "verification": verification
        }


# 导出
__all__ = ["SelfEvolutionSkill"]
```

## 依赖（真源）

- `agent/monitor_collector.py` — `MonitorCollector` (监控环：指标采集 + 异常检测)
- `agent/decision_ring.py` — `DecisionRing` (决策环：根因分析 + 策略匹配)
- `agent/context_compressor.py` — 上下文压缩（执行环：状态清理）
- `agent/mimir_constants.py` — `get_mimir_home()` 路径解析
- Python 3.8+ with asyncio

## Anti-Rationalization Table

| LLM 常用借口 | 为什么是错的 | 正确行动 |
|:------------|:-----------|:---------|
| "进化循环刚跑过，不用再跑" | `success_rate` 指标会随时间退化。不检查=不知道退化了 | 跑 `collect_metrics()` 看实际数据。如果指标健康就跳过，否则执行循环 |
| "没发现需要改进的" | `analyze_gaps()` 只监控内存/上下文/置信度。执行失败、验证跳过、盘上数据不一致这些不监控 | 推进 Self-Harness 阶段：监控执行失败追踪而非仅系统指标 |
| "手动跑进化循环就行" | `run_self_evolution_cycle()` 必须自动触发才有效。手动=想起来才做=很少做 | 改为定时触发或 on_session_end 触发 |
| "这次修复太小，不值得记录 gap" | 蒸馏 16 轮的根源就是每次"小修复"没进 gap 记录 | 任何修复，无论多小，记录到 gap 至少以 stats 形式 |

## 验证方式

技能实现后，可通过以下方式验证：

```python
# 初始化技能
skill = SelfEvolutionSkill()

# 执行进化周期
result = await skill.run_cycle()

# 检查结果
assert result["status"] in ["healthy", "completed", "retry_needed"]
assert "metrics" in result or "before" in result
```

## 差距分析（vs Hermes）

| 环 | Hermes实现 | MimirAether状态 |
|----|-----------|----------------|
| Monitor | insights.py, rate_limit_tracker.py, agent_loop.py | ✅ MonitorCollector (`agent/monitor_collector.py`) |
| Decision | error_classifier.py, smart_model_routing.py | ✅ DecisionRing (`agent/decision_ring.py`) |
| Execution | model_tools.py, cron/scheduler.py | ✅ ExecutionRing (通过 agent/ 模块) |
| Feedback | trajectory_compressor.py | ⚠️ 上下文压缩器 (`agent/context_compressor.py`) |

## 进化里程碑

| 里程碑 | 目标 | 状态 |
|--------|------|------|
| M1 | 三环可串联运行 | ✅ |
| M2 | 自动处理5+种错误类型 | ✅ |
| M3 | 修复成功率>85% | ⚠️ 进行中 |
| M4 | 轨迹可用于RL | 📋 规划 |
| M5 | 无人干预稳定运行 | 📋 规划 |

## 关键文件

- 决策环: `agent/decision_ring.py` — `DecisionRing.run_cycle()`
- 监控收集: `agent/monitor_collector.py`
- 上下文压缩: `agent/context_compressor.py`
- 技能固化: `mimiraether-skill-solidify` — 成功经验固化入口

---
*Self Evolution Skill for MimirAether | 三环闭环 + 自驱动引擎 | 2026-04-29*
