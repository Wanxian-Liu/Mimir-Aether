# [DORMANT] session-tracker

**沉寂时间**: 2026-07-14T18:58:41.128675+00:00
**原始分类**: productivity
**描述**: Track conversation session state with SQLite - manage sessions, record events, and monitor token usage and cost. Based on the session_tracker.py module from MimirAether.
**触发阈值**: 60天未触碰

---

## 技能要点

# session-tracker

Track conversation session state, events, and token usage using SQLite. Provides persistent session management with cost estimation.

## Python Module

**Source**: `~/.mimiraether/session_tracker.py`

```python
from session_tracker import SessionTracker

tracker = SessionTracker()  # Uses ~/.mimiraether/sessions/sessions.db
```

## Core Features

- **Session Management**: Create, end, query active sessions
- **Event Recording**: Log arbitrary events with timestamps and metadata
- **Token Tracking**: Track input/output tokens per session
- **Cost Estimation**: Calculate USD costs based on OpenAI GPT-4o mini pricing

## Token Pricing (USD per 1M tokens)

| Type | Price |
|------|-------|
| Input | $0.15 |
| Output | $0.60 |
| Cache Read | $0.01 |
| Cache Write | $0.11 |

## Usage

### Basic Session Operations

```python
from session_tracker import SessionTracker

tracker = SessionTracker()

# Create a session
session_id = "my_session_001"
tracker.create_session(session_id, {"user": "alice", "purpose": "analysis"})

# Record an event
tracker.record_event(session_id, "task_started", {"task": "data_analysis"})

# Get session info
session = tracker.get_session(session_id)
print(f"Created: {session['created_at']}")

# List active sessions
for s in tracker.get_active_sessions():
    print(f"  {s['session_id']} - {s['total_tokens']} tokens")

# End session
tracker.end_session(session_id)
```

### Token and Cost Tracking

```python
# Update token stats (call after each LLM interaction)
tracker.update_token_stats(
    session_id,
    input_tokens=5000,
    output_tokens=1500
)

# Get session statistics
stats = tracker.get_session_stats(session_id)
print(f"Total tokens: {stats['total_tokens']}")
print(f"Estimated cost: ${stats['estimated_cost_usd']:.6f}")
print(f"Token breakdown: {stats['token_breakdown']}")

# Get top 10 most expensive sessions
ranking = tracker.get_cost_ranking(limit=10)
for item in ranking:
    print(f"  {item['session_id']}: ${item['estim

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("session-tracker")` 即可自动唤醒。
