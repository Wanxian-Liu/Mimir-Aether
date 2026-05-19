"""
Tool Quality Tracker — Per-tool execution quality tracking with SQLite persistence.

Learned from OpenSpace grounding/core/quality/ (manager.py + types.py + store.py):
  - Track per-tool success rate, latency, and LLM-flagged issues
  - Persistent SQLite with exponential-backoff retry
  - Quality-aware ranking (penalize tools with recent failures)
  - Rolling window of recent executions (last 20)
  - Incremental evolution trigger (every N global executions)

Design: Zero external deps beyond Python stdlib sqlite3.
Persistence to <MIMIR_AETHER_HOME>/data/tool_quality.db
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _get_db_path() -> Path:
    home = os.getenv("MIMIR_AETHER_HOME", os.path.expanduser("~/.mimiraether"))
    data_dir = Path(home) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "tool_quality.db"


# ── Data types ──────────────────────────────────────────────────────────────

@dataclass
class ExecutionRecord:
    """One execution record."""
    timestamp: str
    success: bool
    duration_ms: float = 0.0
    error_message: str = ""


@dataclass
class ToolQualityRecord:
    """Per-tool quality record."""
    tool_key: str
    tool_name: str
    total_calls: int = 0
    success_count: int = 0
    total_duration_ms: float = 0.0
    recent_executions: List[ExecutionRecord] = field(default_factory=list)
    llm_flagged_count: int = 0
    first_seen: str = ""
    last_updated: str = ""

    MAX_RECENT: int = 20  # Rolling window size

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.first_seen:
            self.first_seen = now
        if not self.last_updated:
            self.last_updated = now

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.success_count / self.total_calls

    @property
    def recent_success_rate(self) -> float:
        if not self.recent_executions:
            return 1.0
        recent_success = sum(1 for r in self.recent_executions if r.success)
        return recent_success / len(self.recent_executions)

    @property
    def avg_duration_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_duration_ms / self.total_calls

    @property
    def quality_score(self) -> float:
        """Composite quality score (0-1), used for tool ranking.

        Weighted: 60% recent success rate + 30% overall success rate + 10% penalty
        per LLM flag (max -0.3).
        """
        base = 0.6 * self.recent_success_rate + 0.4 * self.success_rate
        penalty = min(0.3, self.llm_flagged_count * 0.05)
        return max(0.0, base - penalty)

    def add_execution(self, rec: ExecutionRecord) -> None:
        self.total_calls += 1
        self.total_duration_ms += rec.duration_ms
        if rec.success:
            self.success_count += 1
        self.recent_executions.append(rec)
        if len(self.recent_executions) > self.MAX_RECENT:
            self.recent_executions = self.recent_executions[-self.MAX_RECENT:]
        self.last_updated = datetime.now(timezone.utc).isoformat()


# ── SQLite persistence ──────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_quality (
    tool_key   TEXT PRIMARY KEY,
    tool_name  TEXT NOT NULL,
    total_calls INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    total_duration_ms REAL DEFAULT 0.0,
    recent_executions TEXT DEFAULT '[]',
    llm_flagged_count INTEGER DEFAULT 0,
    first_seen  TEXT NOT NULL,
    last_updated TEXT NOT NULL
);
"""


def _db_retry(max_retries: int = 5, initial_delay: float = 0.1, backoff: float = 2.0):
    """Retry decorator for transient SQLite errors (database is locked, etc.)."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(delay)
                    delay *= backoff
            return None
        return wrapper
    return decorator


class ToolQualityStore:
    """SQLite-backed persistent store for tool quality records."""

    def __init__(self, db_path: Path = None):
        self._db_path = db_path or _get_db_path()
        self._lock = threading.Lock()
        self._init_db()

    @_db_retry()
    def _init_db(self) -> None:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
            conn.commit()

    @_db_retry()
    def load_all(self) -> Dict[str, ToolQualityRecord]:
        records: Dict[str, ToolQualityRecord] = {}
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            rows = conn.execute("SELECT * FROM tool_quality").fetchall()
        for row in rows:
            recent = [ExecutionRecord(**r) for r in json.loads(row[5])]
            rec = ToolQualityRecord(
                tool_key=row[0],
                tool_name=row[1],
                total_calls=row[2],
                success_count=row[3],
                total_duration_ms=row[4],
                recent_executions=recent,
                llm_flagged_count=row[6],
                first_seen=row[7],
                last_updated=row[8],
            )
            records[rec.tool_key] = rec
        return records

    @_db_retry()
    def save(self, record: ToolQualityRecord) -> None:
        recent_json = json.dumps(
            [{"timestamp": r.timestamp, "success": r.success,
              "duration_ms": r.duration_ms, "error_message": r.error_message}
             for r in record.recent_executions],
            ensure_ascii=False,
        )
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO tool_quality
                   (tool_key, tool_name, total_calls, success_count,
                    total_duration_ms, recent_executions, llm_flagged_count,
                    first_seen, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (record.tool_key, record.tool_name, record.total_calls,
                 record.success_count, record.total_duration_ms, recent_json,
                 record.llm_flagged_count, record.first_seen, record.last_updated),
            )
            conn.commit()


# ── Quality Manager ─────────────────────────────────────────────────────────

class ToolQualityManager:
    """Tracks per-tool quality and provides quality-aware ranking.

    Usage::

        qm = ToolQualityManager()
        qm.record("web_search", success=True, duration_ms=120.0)
        qm.record("web_search", success=False, error="timeout", duration_ms=5000.0)

        # Get quality-aware tool ranking
        for tool_name, score in qm.rank_tools():
            print(f"{tool_name}: quality={score:.2f}")

        # Check if tools need evolution
        if qm.should_evolve():
            degraded = qm.get_degraded_tools()
    """

    def __init__(
        self,
        *,
        db_path: Path = None,
        enable_persistence: bool = True,
        evolve_interval: int = 10,
    ):
        self._records: Dict[str, ToolQualityRecord] = {}
        self._global_count: int = 0
        self._evolve_interval = evolve_interval
        self._last_evolve_at: int = 0

        self._store = ToolQualityStore(db_path=db_path) if enable_persistence else None
        if self._store:
            self._records = self._store.load_all()
            self._global_count = sum(r.total_calls for r in self._records.values())
            self._last_evolve_at = (self._global_count // evolve_interval) * evolve_interval

    def _make_key(self, tool_name: str) -> str:
        return tool_name

    def record(
        self,
        tool_name: str,
        *,
        success: bool = True,
        error_message: str = "",
        duration_ms: float = 0.0,
    ) -> None:
        """Record one tool execution."""
        key = self._make_key(tool_name)
        if key not in self._records:
            self._records[key] = ToolQualityRecord(tool_key=key, tool_name=tool_name)

        rec = ExecutionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            success=success,
            duration_ms=duration_ms,
            error_message=error_message[:500],
        )
        self._records[key].add_execution(rec)
        self._global_count += 1

        if self._store:
            self._store.save(self._records[key])

    def flag_llm_issue(self, tool_name: str) -> None:
        """Mark a tool as flagged by LLM analysis."""
        key = self._make_key(tool_name)
        if key in self._records:
            self._records[key].llm_flagged_count += 1
            if self._store:
                self._store.save(self._records[key])

    def should_evolve(self) -> bool:
        """Check if enough executions have passed to trigger evolution."""
        threshold = (self._global_count // self._evolve_interval) * self._evolve_interval
        if threshold > self._last_evolve_at:
            self._last_evolve_at = threshold
            return True
        return False

    def get_degraded_tools(self, threshold: float = 0.5) -> List[Tuple[str, float]]:
        """Return tools below the quality threshold for evolution attention."""
        degraded = []
        for key, rec in self._records.items():
            if rec.total_calls >= 3 and rec.quality_score < threshold:
                degraded.append((rec.tool_name, rec.quality_score))
        return sorted(degraded, key=lambda x: x[1])

    def rank_tools(self) -> List[Tuple[str, float]]:
        """Return all tools ranked by quality score (highest first)."""
        ranked = [(r.tool_name, r.quality_score) for r in self._records.values()]
        return sorted(ranked, key=lambda x: x[1], reverse=True)

    def get_report(self) -> Dict[str, Any]:
        """Generate a quality report."""
        tools = []
        for rec in self._records.values():
            tools.append({
                "tool": rec.tool_name,
                "calls": rec.total_calls,
                "success_rate": round(rec.success_rate, 3),
                "recent_rate": round(rec.recent_success_rate, 3),
                "quality_score": round(rec.quality_score, 3),
                "avg_ms": round(rec.avg_duration_ms, 1),
                "llm_flags": rec.llm_flagged_count,
            })
        return {
            "total_executions": self._global_count,
            "tools_tracked": len(self._records),
            "tools": sorted(tools, key=lambda t: t["quality_score"]),
        }
