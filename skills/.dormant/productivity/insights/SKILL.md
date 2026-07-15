---
name: insights
description: MimirAether usage analytics and insights engine - analyzes session data, tracks tool usage patterns, generates cost reports, and provides efficiency recommendations. Based on session_tracker.py data.
version: 1.0.0
author: MimirAether
license: MIT
metadata:
  hermes:
    tags: [Insights, Analytics, Cost-Analysis, Usage-Patterns, Reporting]
    homepage: ~/.mimiraether/insights.py
---

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

# Get detailed metrics
metrics = engine.get_efficiency_metrics()
print(f"  - Avg tokens per message: {metrics['avg_tokens_per_message']}")
print(f"  - Tool call ratio: {metrics['tool_call_ratio']}")
print(f"  - Session completion rate: {metrics['completion_rate']}")
```

### Cost Alerts

```python
# Check if you're approaching budget limits
alerts = engine.check_cost_alerts(daily_limit=5.0, weekly_limit=25.0)
for alert in alerts:
    print(f"[{alert['severity']}] {alert['message']}")
```

## Data Source

The insights engine reads from `session_tracker.py` SQLite database:

```
~/.mimiraether/sessions/sessions.db

Tables:
- sessions: session_id, created_at, updated_at, metadata, is_active, 
           input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
           total_tokens, estimated_cost_usd, last_prompt_tokens, memory_flushed
- session_events: id, session_id, event_type, event_data, timestamp
```

## Cost Pricing

Uses GPT-4o mini pricing (adjustable):

| Token Type | Price per 1M |
|-----------|--------------|
| Input | $0.15 |
| Output | $0.60 |
| Cache Read | $0.01 |
| Cache Write | $0.11 |

## CLI Usage

```bash
# Basic report (last 7 days)
python insights.py

# Report for specific period
python insights.py --days 30
python insights.py --days 7 --format json

# Check budget alerts
python insights.py --alerts --daily-limit 5 --weekly-limit 25

# Export data
python insights.py --export report.json
```

## Report Format

```markdown
# MimirAether Usage Report
**Period**: 2026-04-01 to 2026-04-28

## Summary
- Total Sessions: 45
- Total Tokens: 1.2M
- Total Cost: $3.45
- Avg Session Length: 28 messages

## Cost Breakdown
| Day | Sessions | Tokens | Cost |
|-----|----------|--------|------|
| Apr 1 | 3 | 45K | $0.12 |
| Apr 2 | 5 | 78K | $0.21 |

## Top Tools
1. terminal: 156 calls
2. read_file: 89 calls
3. write_file: 67 calls

## Recommendations
- Consider batching terminal commands to reduce overhead
- Your sessions are shorter than average - try more complex tasks!
```

## Requirements

- Python 3.8+
- `session_tracker.py` database at `~/.mimiraether/sessions/sessions.db`
- No additional dependencies (uses stdlib)

## Notes

- Insights are generated on-demand (no caching by default)
- Use `--cache` flag to cache results for faster subsequent runs
- Budget alerts require configured limits
- Export formats: `text`, `json`, `markdown`

---

*Insights Engine V1.0.0 · MimirAether · 2026-04-28*
