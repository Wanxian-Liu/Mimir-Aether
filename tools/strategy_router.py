"""
Strategy Router — Pre-validation & Auto-routing for Behavioral Strategies

Augments ``tools/strategy.py`` with two capabilities:

1. **Pre-validation** — check whether a strategy can be applied given current
   constraints (token budget, task nature, context pressure).
2. **Auto-routing** — select the best strategy based on task features without
   requiring manual user intervention.

Design:
- ``TaskFeature`` captures what we know about the current task
- ``ValidationResult`` is the output of pre-validation (applicable + warnings + score)
- ``route_strategy()`` auto-selects; ``pre_validate()`` checks fit
- Registered as the ``route_strategy`` tool (action='auto' or 'validate')
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports from sibling strategy module (lazy to avoid circular issues)
# ---------------------------------------------------------------------------

def _get_strategies():
    """Lazy import to avoid circular dependencies at module load."""
    from tools.strategy import (
        _BUILTIN_STRATEGIES,
        _current_strategy,
        get_strategy,
        set_strategy,
        list_strategies,
    )
    return _BUILTIN_STRATEGIES, _current_strategy, get_strategy, set_strategy, list_strategies


# ---------------------------------------------------------------------------
# Task Feature Model
# ---------------------------------------------------------------------------

class TaskDomain(str, Enum):
    """Broad domain of the task — influences strategy suitability."""
    GENERAL = "general"
    CODE = "code"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    DIAGNOSTIC = "diagnostic"


class TaskComplexity(str, Enum):
    """How complex / multi-step the task is."""
    TRIVIAL = "trivial"       # one-shot, well-defined
    MODERATE = "moderate"     # a few steps, some ambiguity
    COMPLEX = "complex"       # multi-step, deep reasoning needed


class TaskUrgency(str, Enum):
    """How time-sensitive the task is."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass
class TaskFeature:
    """Observable features of the current task.

    Filled by the caller (agent loop, user interaction, or tool handler).
    Only ``complexity`` is required; everything else has sensible defaults.
    """

    complexity: TaskComplexity = TaskComplexity.MODERATE
    domain: TaskDomain = TaskDomain.GENERAL
    urgency: TaskUrgency = TaskUrgency.NORMAL
    is_open_ended: bool = False
    is_multi_turn: bool = False

    # Context-pressure indicators (optional, improves routing accuracy)
    context_pressure: float = 0.0   # 0..1, how full the context window is
    tokens_remaining: Optional[int] = None
    error_context: bool = False      # True if we are recovering from an error

    def to_dict(self) -> dict:
        return {
            "complexity": self.complexity.value,
            "domain": self.domain.value,
            "urgency": self.urgency.value,
            "is_open_ended": self.is_open_ended,
            "is_multi_turn": self.is_multi_turn,
            "context_pressure": round(self.context_pressure, 2),
            "tokens_remaining": self.tokens_remaining,
            "error_context": self.error_context,
        }


# ---------------------------------------------------------------------------
# Validation Result
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Output of ``pre_validate()``."""

    strategy_name: str
    applicable: bool
    score: float                         # 0..1  fit score
    warnings: list[str] = field(default_factory=list)
    recommendation: str = ""             # human-readable guidance

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy_name,
            "applicable": self.applicable,
            "score": round(self.score, 2),
            "warnings": self.warnings,
            "recommendation": self.recommendation,
        }


# ---------------------------------------------------------------------------
# Pre-validation rules
# ---------------------------------------------------------------------------

def _validate_concise(ctx: TaskFeature) -> ValidationResult:
    """Concise strategy: almost always applicable. Drops score when task is
    complex and multi-turn (short responses can lose important context)."""
    warnings = []
    score = 1.0
    if ctx.complexity == TaskComplexity.COMPLEX:
        warnings.append("Task is complex; concise responses may omit critical detail.")
        score = 0.5
    if ctx.is_multi_turn:
        warnings.append("Multi-turn tasks benefit from more context retention.")
        score = max(score - 0.1, 0.0)
    return ValidationResult(
        strategy_name="concise", applicable=True, score=score,
        warnings=warnings,
        recommendation="Good for quick answers and low-context-pressure situations.",
    )


def _validate_thorough(ctx: TaskFeature) -> ValidationResult:
    """Thorough strategy: great for complex tasks but expensive in tokens."""
    warnings = []
    score = 0.8
    if ctx.context_pressure > 0.75:
        warnings.append("Context window is under pressure; thorough responses may cause overflow.")
        score = 0.3
    if ctx.urgency == TaskUrgency.HIGH:
        warnings.append("Urgency is high; thorough responses may be too slow.")
        score = 0.4
    if ctx.complexity == TaskComplexity.TRIVIAL:
        warnings.append("Task is trivial; thorough strategy may be overkill.")
        score = 0.5
    return ValidationResult(
        strategy_name="thorough", applicable=True, score=score,
        warnings=warnings,
        recommendation="Ideal for complex, multi-step tasks with ample context budget.",
    )


def _validate_creative(ctx: TaskFeature) -> ValidationResult:
    """Creative strategy: best for open-ended / generative tasks, poor for
    fact-critical or diagnostic work."""
    warnings = []
    score = 0.6
    if ctx.is_open_ended or ctx.domain == TaskDomain.CREATIVE:
        score = 0.95
    if ctx.domain == TaskDomain.DIAGNOSTIC:
        warnings.append("Diagnostic tasks need precision; creative approaches may mislead.")
        score = 0.3
    if ctx.domain == TaskDomain.CODE:
        warnings.append("Code tasks benefit from systematic over lateral thinking.")
        score = 0.4
    if ctx.error_context:
        warnings.append("Error recovery needs deterministic, not creative, responses.")
        score = 0.2
    return ValidationResult(
        strategy_name="creative", applicable=True, score=score,
        warnings=warnings,
        recommendation="Best for brainstorming, open-ended exploration, and generative tasks.",
    )


def _validate_analytical(ctx: TaskFeature) -> ValidationResult:
    """Analytical strategy: excellent for debugging and structured problems,
    but needs sufficient context budget for step-by-step reasoning."""
    warnings = []
    score = 0.7
    if ctx.domain in (TaskDomain.ANALYTICAL, TaskDomain.DIAGNOSTIC, TaskDomain.CODE):
        score = 0.95
    if ctx.complexity == TaskComplexity.COMPLEX:
        score = min(score + 0.05, 1.0)  # slight boost
    if ctx.is_open_ended:
        warnings.append("Open-ended tasks may not benefit from strict analytical framing.")
        score = 0.4
    if ctx.context_pressure > 0.7:
        warnings.append("Analytical reasoning consumes tokens; high context pressure is risky.")
        score = max(score - 0.2, 0.0)
    return ValidationResult(
        strategy_name="analytical", applicable=True, score=score,
        warnings=warnings,
        recommendation="Ideal for debugging, code review, and systematic problem decomposition.",
    )


_VALIDATORS = {
    "concise": _validate_concise,
    "thorough": _validate_thorough,
    "creative": _validate_creative,
    "analytical": _validate_analytical,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def pre_validate(strategy_name: str, context: TaskFeature) -> ValidationResult:
    """Check whether *strategy_name* can be applied to *context*.

    Returns a ``ValidationResult`` with applicability, score, and warnings.
    Unknown strategy names return a failing result.
    """
    validator = _VALIDATORS.get(strategy_name)
    if validator is None:
        return ValidationResult(
            strategy_name=strategy_name,
            applicable=False,
            score=0.0,
            warnings=[f"Unknown strategy: '{strategy_name}'"],
            recommendation="Use one of: concise, thorough, creative, analytical.",
        )
    return validator(context)


def route_strategy(context: TaskFeature) -> tuple[str, ValidationResult]:
    """Auto-select the best behavioral strategy for *context*.

    Returns ``(strategy_name, best_validation)``.
    """
    best_name = "thorough"  # safe default
    best_score = -1.0
    best_validation: Optional[ValidationResult] = None

    for name in _VALIDATORS:
        vr = pre_validate(name, context)
        if vr.score > best_score:
            best_score = vr.score
            best_name = name
            best_validation = vr

    # Persist the selection in the in-memory strategy state
    _, _, _, set_strategy_fn, _ = _get_strategies()
    set_strategy_fn(best_name)

    return best_name, best_validation


# ---------------------------------------------------------------------------
# Tool Schema & Handler
# ---------------------------------------------------------------------------

ROUTE_STRATEGY_SCHEMA = {
    "name": "route_strategy",
    "description": (
        "Pre-validate or auto-route the agent's behavioral strategy. "
        "Use action='auto' to select the best strategy based on task features. "
        "Use action='validate' to check how well a specific strategy fits the current context."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["auto", "validate"],
                "description": "'auto' selects the best strategy; 'validate' checks a specific one.",
            },
            "name": {
                "type": "string",
                "description": "Strategy name to validate (required for action='validate'). One of: concise, thorough, creative, analytical.",
            },
            "complexity": {
                "type": "string",
                "enum": ["trivial", "moderate", "complex"],
                "description": "Task complexity (default: moderate).",
            },
            "domain": {
                "type": "string",
                "enum": ["general", "code", "creative", "analytical", "diagnostic"],
                "description": "Task domain (default: general).",
            },
            "urgency": {
                "type": "string",
                "enum": ["low", "normal", "high"],
                "description": "Task urgency (default: normal).",
            },
            "is_open_ended": {
                "type": "boolean",
                "description": "Is the task open-ended / creative?",
            },
            "is_multi_turn": {
                "type": "boolean",
                "description": "Is this a multi-turn conversation?",
            },
            "context_pressure": {
                "type": "number",
                "description": "0.0-1.0, how full the context window is.",
            },
            "error_context": {
                "type": "boolean",
                "description": "Are we in an error recovery context?",
            },
        },
        "required": ["action"],
    },
}


def _parse_context(args: dict) -> TaskFeature:
    """Build a TaskFeature from tool arguments."""
    complexity_map = {"trivial": TaskComplexity.TRIVIAL, "moderate": TaskComplexity.MODERATE, "complex": TaskComplexity.COMPLEX}
    domain_map = {"general": TaskDomain.GENERAL, "code": TaskDomain.CODE, "creative": TaskDomain.CREATIVE, "analytical": TaskDomain.ANALYTICAL, "diagnostic": TaskDomain.DIAGNOSTIC}
    urgency_map = {"low": TaskUrgency.LOW, "normal": TaskUrgency.NORMAL, "high": TaskUrgency.HIGH}

    return TaskFeature(
        complexity=complexity_map.get(args.get("complexity", "moderate"), TaskComplexity.MODERATE),
        domain=domain_map.get(args.get("domain", "general"), TaskDomain.GENERAL),
        urgency=urgency_map.get(args.get("urgency", "normal"), TaskUrgency.NORMAL),
        is_open_ended=bool(args.get("is_open_ended", False)),
        is_multi_turn=bool(args.get("is_multi_turn", False)),
        context_pressure=float(args.get("context_pressure", 0.0)),
        tokens_remaining=args.get("tokens_remaining"),
        error_context=bool(args.get("error_context", False)),
    )


def route_strategy_tool(args: dict, **kw) -> str:
    """Handle ``route_strategy`` tool calls."""
    action = args.get("action", "auto")

    if action == "auto":
        ctx = _parse_context(args)
        best_name, best_vr = route_strategy(ctx)
        return tool_result({
            "action": "auto",
            "selected": best_name,
            "score": round(best_vr.score, 2),
            "warnings": best_vr.warnings,
            "recommendation": best_vr.recommendation,
            "context": ctx.to_dict(),
        })

    if action == "validate":
        name = args.get("name", "").strip().lower()
        if not name:
            return tool_error("'name' is required when action='validate'")
        ctx = _parse_context(args)
        vr = pre_validate(name, ctx)
        return tool_result({
            "action": "validate",
            "validation": vr.to_dict(),
            "context": ctx.to_dict(),
        })

    return tool_error(f"Unknown action: {action}")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="route_strategy",
    toolset="core",
    schema=ROUTE_STRATEGY_SCHEMA,
    handler=route_strategy_tool,
    description="Pre-validate or auto-route the agent's behavioral strategy based on task features",
    emoji="🧭",
)
