# [DORMANT] mimiraether-self_evolution

**沉寂时间**: 2026-07-31T08:41:50.173791+00:00
**原始分类**: mimiraether
**描述**: MimirAether 自我进化技能 — 触发条件为用户明确要求自我进化/改进/优化。基于三环闭环架构（MonitorRing→DecisionRing→ExecutionRing），使用 agent 内建模块（monitor_collector / decision_ring / context_compressor）实现知识纠错、根因修复与意图预测。已吸收 three-ring-iteration 的路线图与里程碑。
**触发阈值**: 60天未触碰

---

## 技能要点

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
            "type":

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-self_evolution")` 即可自动唤醒。
