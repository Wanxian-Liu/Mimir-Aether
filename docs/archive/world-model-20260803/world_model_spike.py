"""WM Phase0: rule-based WorldModelPredictor spike (WB-B01).

Pure heuristics over ``context_snapshot`` — no LLM API, network, or randomness.
Production wiring is env-gated via ``MIMIR_WM_PREDICTOR`` (default off).

ARCHIVED 2026-08-03 → docs/archive/world-model-20260803/ (surprise flow disabled
per WM discussion consensus). BUG-01/06/07/13/14/15 fixed in place so this stays
a CORRECT reference implementation if VoE is ever revived.
"""

from __future__ import annotations

import os
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

# BUG-13 FIX: relative import broke standalone runs. Keep relative import for
# package use, but degrade gracefully when the module is absent (archived).
try:
    from .wm_voe_learning import (
        get_self_healing_additions,
        get_self_healing_confidence,
        is_wm_voe_learning_enabled,
    )
except ImportError:  # pragma: no cover - standalone / archived
    get_self_healing_additions = lambda: set()  # type: ignore[assignment]
    get_self_healing_confidence = lambda: {}  # type: ignore[assignment]
    is_wm_voe_learning_enabled = lambda: False  # type: ignore[assignment]

_RECALL_HINT = re.compile(
    r"(?i)上次|之前|记得|session_search|历史.*对话|还记得|prior\s+session"
)
_CODE_HINT = re.compile(
    r"(?i)implement|refactor|patch|fix|修复|实现|改代码|pytest|debug|traceback"
)
# BUG-14 FIX: add chat hint so _infer_intent can return "chat" (was dead branch).
_CHAT_HINT = re.compile(
    r"(?i)^\s*(嗨|哈喽|你好|hello|hi|hey|在吗|谢谢|晚安|早安|拜拜)\s*[!！。.]?\s*$"
)

_INTENT_NEEDS: dict[str, tuple[str, ...]] = {
    "recall": ("prior_session_context", "memory_or_search"),
    "code": ("source_files", "repo_context"),
    "debug": ("source_files", "error_context", "logs"),
    "ops": ("runtime_status", "service_logs"),
    "chat": ("user_message",),
    "general": ("user_message",),
}

# BUG-01 FIX: tool names must be REAL (terminal/search_files), not invented
# (run_terminal_cmd/grep). This was the #1 noise source: 57% of surprises were
# actual=terminal never matching the prediction set.
_INTENT_SKILLS: dict[str, tuple[str, ...]] = {
    "recall": ("session_search", "search_files", "read_file"),
    "code": ("read_file", "terminal", "search_files", "patch"),
    "debug": ("read_file", "terminal", "search_files"),
    "ops": ("terminal", "search_files", "health_check"),
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
# BUG-07 FIX: use REAL tool names (was run_terminal_cmd, which filtered nothing).
_PREDICTION_ACCURACY_TOOLS = frozenset({
    "read_file", "search_files", "terminal", "web_search", "web_extract",
    "write_file", "patch", "memory", "skill_view", "session_search",
    "execute_code", "process", "cronjob", "browser_navigate",
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

    # BUG-07 FIX: empty-but-nonzero inputs must NOT return 1.0/1.0/1.0 (fake
    # perfect accuracy). Return honest zeros with samples>0.
    if not predicted and not actual:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "top_k_hits": 0, "samples": len(predictions)}

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


# BUG-15 FIX: code hint must take priority over recall hint, otherwise
# "修复上次的 bug" (fix last bug) is misclassified as recall because
# "上次" matches _RECALL_HINT first. Intent is code work, not recall.
def _infer_intent(user_message: str, intent: str) -> str:
    if intent and intent != "general":
        return intent
    if not user_message:
        return "general"
    if _CODE_HINT.search(user_message):
        return "code"
    if _RECALL_HINT.search(user_message):
        return "recall"
    if _CHAT_HINT.search(user_message):
        return "chat"
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

    # BUG-06 FIX: is_collapsed() was dead code (0 call sites). Wire it in: if the
    # predictor is stuck producing the same intent, log it (SIGReg collapse
    # signal). Production impact is nil while env-gated off.
    if is_collapsed():
        _recent_intents.clear()  # reset the rut
        _collapse_logged = True  # noqa: F841 (signal for tests/debuggers)

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
