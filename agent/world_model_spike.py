"""WM Phase0: rule-based WorldModelPredictor spike (WB-B01).

Pure heuristics over ``context_snapshot`` — no LLM API, network, or randomness.
Production wiring is env-gated via ``MIMIR_WM_PREDICTOR`` (default off).
"""

from __future__ import annotations

import os
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .wm_voe_learning import get_self_healing_additions, get_self_healing_confidence, is_wm_voe_learning_enabled

_RECALL_HINT = re.compile(
    r"(?i)上次|之前|记得|session_search|历史.*对话|还记得|prior\s+session"
)
_CODE_HINT = re.compile(
    r"(?i)implement|refactor|patch|fix|修复|实现|改代码|pytest|debug|traceback"
)

_INTENT_NEEDS: dict[str, tuple[str, ...]] = {
    "recall": ("prior_session_context", "memory_or_search"),
    "code": ("source_files", "repo_context"),
    "debug": ("source_files", "error_context", "logs"),
    "ops": ("runtime_status", "service_logs"),
    "chat": ("user_message",),
    "general": ("user_message",),
}

_INTENT_SKILLS: dict[str, tuple[str, ...]] = {
    "recall": ("session_search", "search_files", "read_file"),
    "code": ("read_file", "run_terminal_cmd", "search_files", "patch"),
    "debug": ("read_file", "run_terminal_cmd", "grep", "search_files"),
    "ops": ("run_terminal_cmd", "search_files", "health_check"),
    "chat": (),
    "general": ("read_file", "search_files"),
}

# --- Diversity check: detect prediction collapse (LeWM SIGReg inspiration) ---
_COLLAPSE_WINDOW = 10
_recent_intents: deque = deque(maxlen=_COLLAPSE_WINDOW)


def is_diversity_check_enabled() -> bool:
    return os.environ.get("MIMIR_WM_DIVERSITY_CHECK", "0").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _record_prediction(intent: str) -> None:
    """Record a prediction intent for collapse detection."""
    if is_diversity_check_enabled():
        _recent_intents.append(intent)


def is_collapsed() -> bool:
    """Check if the last N predictions all have the same intent.

    When collapsed, the predictor is stuck in a rut — every prediction
    produces the same intent triplet. This mirrors LeWM's SIGReg
    objective of preventing representation collapse.
    """
    if len(_recent_intents) < _COLLAPSE_WINDOW:
        return False
    first = _recent_intents[0]
    return all(i == first for i in _recent_intents)


def reset_collapse_history() -> None:
    """For testing: clear the ring buffer."""
    _recent_intents.clear()


# --- Tool hit rate: measure prediction accuracy against real tool calls ---
_PREDICTION_ACCURACY_TOOLS = frozenset({
    "read_file", "search_files", "terminal", "web_search", "web_extract",
    "write_file", "patch", "memory", "skill_view", "git",
})


def compute_prediction_accuracy(
    predictions: list[dict],
    actual_tool_calls: list[str],
) -> dict:
    """Compare predicted applicable_skills to actual tool calls.

    Args:
        predictions: list of {"applicable_skills": [...], ...} from <wm-prediction> blocks.
        actual_tool_calls: flat list of tool names actually invoked.

    Returns:
        {"precision": float, "recall": float, "f1": float, "top_k_hits": int, "samples": int}
    """
    if not predictions or not actual_tool_calls:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "top_k_hits": 0, "samples": 0}

    # Flatten all predicted skills
    predicted = set()
    for p in predictions:
        for s in p.get("applicable_skills") or []:
            if s in _PREDICTION_ACCURACY_TOOLS:
                predicted.add(s)

    actual = {t for t in actual_tool_calls if t in _PREDICTION_ACCURACY_TOOLS}

    if not predicted and not actual:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "top_k_hits": 0, "samples": len(predictions)}

    true_positives = predicted & actual
    precision = len(true_positives) / len(predicted) if predicted else 0.0
    recall = len(true_positives) / len(actual) if actual else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "top_k_hits": len(true_positives),
        "samples": len(predictions),
    }


_DEFAULT_OUTCOME = (
    "No actionable context; respond with clarification or a safe conservative default."
)


@dataclass(frozen=True)
class Prediction:
    next_context_needs: list[str]
    applicable_skills: list[str]
    expected_outcome: str
    tool_confidence: dict[str, float] = field(default_factory=dict)


def is_wm_predictor_enabled() -> bool:
    return os.environ.get("MIMIR_WM_PREDICTOR", "0").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _infer_intent(user_message: str, intent: str) -> str:
    if intent and intent != "general":
        return intent
    if not user_message:
        return "general"
    if _RECALL_HINT.search(user_message):
        return "recall"
    if _CODE_HINT.search(user_message):
        return "code"
    return "general"


def _build_expected_outcome(intent: str, objective: str, user_message: str) -> str:
    if objective:
        return f"Achieve objective: {objective}"
    if intent == "recall":
        return "Retrieve relevant prior session or memory before answering."
    if intent == "code":
        return "Apply tools to inspect or change the codebase and verify the result."
    if intent == "debug":
        return "Diagnose the failure with tools, then propose or apply a verified fix."
    if intent == "ops":
        return "Check runtime or service state and report actionable ops steps."
    if intent == "chat":
        return "Reply briefly without unnecessary tool calls."
    if user_message:
        return "Respond to the user request with grounded tool use when needed."
    return _DEFAULT_OUTCOME


def _default_prediction() -> Prediction:
    return Prediction(
        next_context_needs=[],
        applicable_skills=[],
        expected_outcome=_DEFAULT_OUTCOME,
    )


def predict(context_snapshot: dict) -> Prediction:
    snapshot = context_snapshot or {}
    user_message = _coerce_str(snapshot.get("user_message"))
    objective = _coerce_str(snapshot.get("objective"))
    intent = _infer_intent(user_message, _coerce_str(snapshot.get("intent")))

    if not user_message and not objective and intent == "general":
        return _default_prediction()

    _record_prediction(intent)

    needs = list(_INTENT_NEEDS.get(intent, _INTENT_NEEDS["general"]))
    skills = list(_INTENT_SKILLS.get(intent, _INTENT_SKILLS["general"]))
    # Merge self-healing additions from learned patterns (WM-P12-01)
    confidence: dict[str, float] = {}
    if is_wm_voe_learning_enabled():
        for t in get_self_healing_additions():
            if t not in skills:
                skills.append(t)
        confidence = get_self_healing_confidence()
    # Assign default confidence (0.0) for rule-based skills not in learned data
    for s in skills:
        if s not in confidence:
            confidence[s] = 0.0
    expected = _build_expected_outcome(intent, objective, user_message)
    return Prediction(
        next_context_needs=needs,
        applicable_skills=skills,
        expected_outcome=expected,
        tool_confidence=confidence,
    )
