# [DORMANT] insights

**沉寂时间**: 2026-07-14T18:58:41.087803+00:00
**原始分类**: productivity
**描述**: MimirAether usage analytics and insights engine - analyzes session data, tracks tool usage patterns, generates cost reports, and provides efficiency recommendations. Based on session_tracker.py data.
**触发阈值**: 60天未触碰

---

## 技能要点

# insights - MimirAether Usage Analytics

Track, analyze, and optimize your MimirAether usage with comprehensive insights derived from session data.

## Overview

The insights engine analyzes data from `session_tracker.py` to provide:
- Cost analysis and budgeting
- Tool usage patterns
- Session efficiency metrics
- Activity trends
- Personalized recommendations

## Python Module

**Source**: `~/.mimiraether/insights.py`

```python
from insights import InsightsEngine

engine = InsightsEngine(db_path="~/.mimiraether/sessions/sessions.db")
```

## Core Features

| Feature | Description |
|---------|-------------|
| Cost Analysis | Track USD spending by session, day, week |
| Tool Usage Stats | Count and frequency of tool calls |
| Session Efficiency | Messages per session, avg session length |
| Activity Trends | Usage over time (daily/weekly/monthly) |
| Recommendations | AI-powered optimization suggestions |

## Usage

### Basic Analysis

```python
from insights import InsightsEngine

engine = InsightsEngine()

# Get cost summary
cost_summary = engine.get_cost_summary(days=30)
print(f"Total cost: ${cost_summary['total_cost_usd']:.4f}")
print(f"Avg per session: ${cost_summary['avg_cost_per_session']:.4f}")

# Get tool usage stats
tool_stats = engine.get_tool_usage_stats(days=30)
for tool, count in tool_stats.most_common(10):
    print(f"  {tool}: {count} calls")

# Get activity trends
trends = engine.get_activity_trends(granularity="daily")
for day, count in trends.items():
    print(f"  {day}: {count} sessions")
```

### Generate Report

```python
# Generate comprehensive report
report = engine.generate_report(days=30)
print(report["summary"])
print(report["cost_breakdown"])
print(report["tool_analysis"])
print(report["recommendations"])

# Export as JSON
import json
print(json.dumps(report, indent=2))
```

### Efficiency Score

```python
# Calculate session efficiency score (0-100)
score = engine.get_efficiency_score()
print(f"Efficiency Score: {score}/100")

# Get

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("insights")` 即可自动唤醒。
