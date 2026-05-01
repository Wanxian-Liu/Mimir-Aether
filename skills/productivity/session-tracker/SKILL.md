---
name: session-tracker
description: Track conversation session state with SQLite - manage sessions, record events, and monitor token usage and cost. Based on the session_tracker.py module from MimirAether.
version: 1.0.0
author: MimirAether
license: MIT
metadata:
  hermes:
    tags: [Session, SQLite, Token-Tracking, Cost-Analysis, Events]
    homepage: ~/.mimiraether/session_tracker.py
---

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
    print(f"  {item['session_id']}: ${item['estimated_cost_usd']:.6f}")
```

### Event History

```python
# Record memory flush events
tracker.record_memory_flush(session_id)

# Get all events for a session
events = tracker.get_session_events(session_id)
for event in events:
    print(f"[{event['timestamp']}] {event['event_type']}: {event['event_data']}")
```

### Context Manager Support

```python
with SessionTracker() as tracker:
    tracker.create_session("temp_session")
    tracker.record_event("temp_session", "test")
    # Auto-cleanup on exit
```

## Database Schema

**Table: sessions**
| Column | Type | Description |
|--------|------|-------------|
| session_id | TEXT PK | Unique session identifier |
| created_at | TEXT | ISO timestamp |
| updated_at | TEXT | ISO timestamp |
| metadata | TEXT | JSON metadata |
| is_active | INTEGER | 1=active, 0=ended |
| input_tokens | INTEGER | Cumulative input tokens |
| output_tokens | INTEGER | Cumulative output tokens |
| cache_read_tokens | INTEGER | Cache read tokens |
| cache_write_tokens | INTEGER | Cache write tokens |
| total_tokens | INTEGER | Sum of all tokens |
| estimated_cost_usd | REAL | Calculated USD cost |
| last_prompt_tokens | INTEGER | Last prompt's input tokens |
| memory_flushed | INTEGER | Memory compression count |

**Table: session_events**
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment ID |
| session_id | TEXT FK | Reference to sessions |
| event_type | TEXT | Event type string |
| event_data | TEXT | JSON event data |
| timestamp | TEXT | ISO timestamp |

## CLI Usage

```bash
python ~/.mimiraether/session_tracker.py
```

## Notes

- Database auto-migrates on init — safe to use across versions
- Default database path: `~/.mimiraether/sessions/sessions.db`
- All timestamps in UTC ISO format
- Token costs are estimates based on GPT-4o mini pricing
