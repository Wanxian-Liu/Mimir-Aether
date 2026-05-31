"""WM Phase0: rule-based WorldModelPredictor spike (WB-B01).

Pure heuristics over ``context_snapshot`` — no LLM API, network, or randomness.
Production wiring is env-gated via ``MIMIR_WM_PREDICTOR`` (default off).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

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
    "recall": ("session_search", "read_file"),
    "code": ("read_file", "run_terminal_cmd"),
    "debug": ("read_file", "run_terminal_cmd", "grep"),
    "ops": ("run_terminal_cmd", "health_check"),
    "chat": (),
    "general": ("read_file",),
}

_DEFAULT_OUTCOME = (
    "No actionable context; respond with clarification or a safe conservative default."
)


@dataclass(frozen=True)
class Prediction:
    next_context_needs: list[str]
    applicable_skills: list[str]
    expected_outcome: str


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

    needs = list(_INTENT_NEEDS.get(intent, _INTENT_NEEDS["general"]))
    skills = list(_INTENT_SKILLS.get(intent, _INTENT_SKILLS["general"]))
    expected = _build_expected_outcome(intent, objective, user_message)
    return Prediction(
        next_context_needs=needs,
        applicable_skills=skills,
        expected_outcome=expected,
    )
