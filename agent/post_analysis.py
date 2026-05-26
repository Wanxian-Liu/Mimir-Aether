"""
Post-Execution Analyzer — LLM-based analysis of execution traces for evolution.

Opt-in: set env MIMIR_AUTO_ANALYSIS=1 to enable automated post-task LLM analysis.
Without it, helpers are available but ``agent.post_close_analysis.schedule_post_close_analysis``
is not invoked from the agent loop.

Learned from OpenSpace skill_engine/analyzer.py:
  - Build structured prompt from execution recording + tool quality data
  - Generate SkillJudgment per tool (keep / fix / deprecate)
  - Surface EvolutionSuggestion entries for downstream processing
  - LLM hallucination correction (skill IDs, tool names)

Integration: Called in the `finally` block after task execution completes.
Results feed into the evolution pipeline (TaskLoop / skill evolver).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class EvolutionSuggestion:
    """One evolution suggestion from post-execution analysis."""
    target: str                       # tool name or skill name
    action: str                       # fix | derive | capture | deprecate
    reason: str = ""
    priority: int = 1                 # 1 (low) - 5 (critical)
    suggested_changes: str = ""       # what to change
    confidence: float = 0.0           # 0-1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "action": self.action,
            "reason": self.reason,
            "priority": self.priority,
            "suggested_changes": self.suggested_changes,
            "confidence": self.confidence,
        }


@dataclass
class ExecutionAnalysis:
    """Result of post-execution analysis."""
    session_id: str = ""
    task_name: str = ""
    overall_rating: float = 0.0       # 0-1 overall execution quality
    tool_issues: List[str] = field(default_factory=list)
    suggestions: List[EvolutionSuggestion] = field(default_factory=list)
    summary: str = ""
    analyzed_at: str = ""

    def __post_init__(self):
        if not self.analyzed_at:
            self.analyzed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_name": self.task_name,
            "overall_rating": self.overall_rating,
            "tool_issues": self.tool_issues,
            "suggestions": [s.to_dict() for s in self.suggestions],
            "summary": self.summary,
            "analyzed_at": self.analyzed_at,
        }

    def has_evolution_suggestions(self) -> bool:
        return len(self.suggestions) > 0

    def top_suggestions(self, n: int = 3) -> List[EvolutionSuggestion]:
        return sorted(self.suggestions, key=lambda s: (s.priority, s.confidence), reverse=True)[:n]


# ── Prompt builder ─────────────────────────────────────────────────────────

# Max chars of execution trace to include in analysis prompt
_MAX_TRACE_CHARS = 50_000
_MAX_ERROR_CHARS = 2000

ANALYSIS_SYSTEM_PROMPT = """You are an execution quality analyst for MimirAether, a self-evolving AI agent.

Analyze the provided execution trace and tool quality data. Your job:

1. **Overall Rating** (0-10): How well did the execution go?
   - Consider: tool failures, efficiency, unnecessary retries, error recovery

2. **Tool Issues**: List any problematic tool behaviors:
   - Repeated failures on same tool
   - Long latency spikes
   - Wrong tool choice for the task
   - Missing error handling

3. **Evolution Suggestions**: For each issue, suggest ONE of:
   - `fix`: Repair the tool's instructions or implementation
   - `derive`: Create an enhanced version
   - `capture`: Record a new reusable pattern
   - `deprecate`: Mark as deprecated if consistently failing

Output ONLY valid JSON:
{
  "overall_rating": <0-10>,
  "tool_issues": ["<issue 1>", ...],
  "suggestions": [
    {
      "target": "<tool_name>",
      "action": "fix|derive|capture|deprecate",
      "reason": "<why>",
      "priority": <1-5>,
      "suggested_changes": "<what to change>",
      "confidence": <0.0-1.0>
    }
  ],
  "summary": "<one-paragraph summary>"
}"""


def build_analysis_prompt(
    trace_text: str,
    tool_quality: Dict[str, Any],
    task_name: str = "",
) -> str:
    """Build the LLM analysis prompt from execution trace and quality data."""
    # Truncate long traces
    if len(trace_text) > _MAX_TRACE_CHARS:
        head = trace_text[:_MAX_TRACE_CHARS // 2]
        tail = trace_text[-_MAX_TRACE_CHARS // 2:]
        trace_text = head + "\n... [truncated] ...\n" + tail

    quality_summary = json.dumps(tool_quality, indent=2, ensure_ascii=False)
    if len(quality_summary) > 5000:
        quality_summary = quality_summary[:5000] + "\n... [truncated]"

    return f"""## Execution Trace ({task_name or 'unnamed'})

{trace_text}

## Tool Quality Data

{quality_summary}

Analyze this execution and return your assessment as JSON."""


# ── Result parser ──────────────────────────────────────────────────────────

def parse_analysis_result(raw_json: str, session_id: str = "", task_name: str = "") -> ExecutionAnalysis:
    """Parse LLM JSON output into an ExecutionAnalysis.
    
    Handles common LLM output issues: markdown fences, trailing commas,
    hallucinated field names.
    """
    # Strip markdown fences
    text = raw_json.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove opening fence
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove closing fence
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract just the JSON object
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            data = json.loads(match.group())
        else:
            # Return empty analysis on parse failure
            return ExecutionAnalysis(
                session_id=session_id,
                task_name=task_name,
                overall_rating=0.0,
                summary=f"Failed to parse analysis result: {raw_json[:200]}",
            )

    suggestions = []
    for s in data.get("suggestions", []):
        suggestions.append(EvolutionSuggestion(
            target=s.get("target", "unknown"),
            action=s.get("action", "fix"),
            reason=s.get("reason", ""),
            priority=max(1, min(5, s.get("priority", 1))),
            suggested_changes=s.get("suggested_changes", ""),
            confidence=max(0.0, min(1.0, s.get("confidence", 0.5))),
        ))

    return ExecutionAnalysis(
        session_id=session_id,
        task_name=task_name,
        overall_rating=data.get("overall_rating", 0.0) / 10.0,  # normalize to 0-1
        tool_issues=data.get("tool_issues", []),
        suggestions=suggestions,
        summary=data.get("summary", ""),
    )
