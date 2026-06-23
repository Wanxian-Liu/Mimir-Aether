"""WM Phase0/1.1: VoE surprise → JSONL audit + learned recall index.

Phase0: append-only JSONL under ``data/wm_phase0/`` (WB-B02).
Phase1.1: structured index under ``data/wm_phase11/`` (WM-P11-01).

Default off via ``MIMIR_WM_VOE_LEARNING``; write failures log warning only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from mimir_constants import get_mimir_home

logger = logging.getLogger(__name__)

_SURPRISE_LABEL_RE = re.compile(r"SURPRISE_DETECTED:\s*(.+?)\s*—")


def is_wm_voe_learning_enabled() -> bool:
    return os.environ.get("MIMIR_WM_VOE_LEARNING", "0").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def is_wm_voe_replan_ctx_enabled() -> bool:
    return os.environ.get("MIMIR_WM_VOE_REPLAN_CTX", "0").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def is_wm_voe_recall_enabled() -> bool:
    return os.environ.get("MIMIR_WM_VOE_RECALL", "0").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def default_surprise_events_path() -> Path:
    return get_mimir_home() / "data" / "wm_phase0" / "surprise_events.jsonl"


def default_learned_surprises_path() -> Path:
    return get_mimir_home() / "data" / "wm_phase11" / "learned_surprises.json"


def normalize_pair(expected: str, actual: str) -> str:
    exp = (expected or "").strip().lower()
    act = (actual or "").strip().lower()
    return f"{exp}|{act}"


def surprise_label_from_guard_message(guard_message: str) -> str:
    match = _SURPRISE_LABEL_RE.search(guard_message or "")
    if match:
        return match.group(1).strip()
    return "unknown"


def _empty_learned_index() -> dict[str, Any]:
    return {"schema_version": 1, "entries": {}}


def _load_learned_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_learned_index()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
            return _empty_learned_index()
        data.setdefault("schema_version", 1)
        return data
    except Exception as exc:
        logger.warning("WM VoE learned index load failed: %s", exc)
        return _empty_learned_index()


def _learning_hint(expected: str, actual: str, surprise_label: str) -> str:
    return (
        f"Prior VoE ({surprise_label}): expected '{expected}' "
        f"but got '{actual}'; do not repeat same assumption."
    )


def format_wm_learning_context(
    expected: str,
    actual: str,
    surprise_label: str,
) -> str:
    """Replan-facing VoE learning summary (WM-P11-02)."""
    return _learning_hint(expected, actual, surprise_label)


_pending_wm_learning_context: str = ""


def set_pending_wm_learning_context(text: str) -> None:
    """Queue VoE learning text for the next model call (WM-P11-OPS)."""
    global _pending_wm_learning_context
    _pending_wm_learning_context = (text or "").strip()


def pop_wm_learning_context_block_for_prompt() -> str:
    """Consume pending VoE context once; empty when replan ctx env is off."""
    global _pending_wm_learning_context
    if not is_wm_voe_replan_ctx_enabled():
        _pending_wm_learning_context = ""
        return ""
    block = _pending_wm_learning_context
    _pending_wm_learning_context = ""
    if not block:
        return ""
    return f"<wm-voe-learning>\n{block}\n</wm-voe-learning>"


def reset_pending_wm_learning_context_for_test() -> None:
    """Test helper."""
    global _pending_wm_learning_context
    _pending_wm_learning_context = ""


def lookup_learned_surprise(
    expected: str,
    actual: str,
    path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    target = path or default_learned_surprises_path()
    key = normalize_pair(expected, actual)
    entry = _load_learned_index(target).get("entries", {}).get(key)
    if not entry:
        return None
    return dict(entry)


def record_surprise_learning(
    expected: str,
    actual: str,
    surprise_label: str,
    path: Optional[Path] = None,
) -> None:
    """Upsert one learned VoE pair into the recall index. No-op when learning disabled."""
    if not is_wm_voe_learning_enabled():
        return

    target = path or default_learned_surprises_path()
    key = normalize_pair(expected, actual)
    now = time.time()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        index = _load_learned_index(target)
        entries = index.setdefault("entries", {})
        existing = entries.get(key)
        if existing:
            existing["last_seen"] = now
            existing["hit_count"] = int(existing.get("hit_count", 1)) + 1
        else:
            entries[key] = {
                "expected": expected,
                "actual": actual,
                "surprise_label": surprise_label,
                "first_seen": now,
                "last_seen": now,
                "hit_count": 1,
                "learning_hint": _learning_hint(expected, actual, surprise_label),
            }
        target.write_text(
            json.dumps(index, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("WM VoE learned index record failed: %s", exc)


def append_surprise_event(
    expected: str,
    actual: str,
    surprise_label: str,
    context_snapshot: dict,
    guard_message: str,
    path: Optional[Path] = None,
    learned_path: Optional[Path] = None,
) -> None:
    """Append one VoE surprise event. No-op when learning is disabled.

    Confidence-gated: if the expected tool has high confidence from self-healing
    history (above HIGH_CONF_THRESHOLD), skip the surprise — the model already
    learned this pattern. Moderate confidence (above MOD_CONF_THRESHOLD) still
    writes but with a reduced-severity label.
    """
    if not is_wm_voe_learning_enabled():
        return

    confidence = get_self_healing_confidence()
    expected_tool = expected.strip()
    tool_conf = confidence.get(expected_tool, 0.0)
    if tool_conf >= _HIGH_CONF_THRESHOLD:
        logger.debug(
            "WM VoE skip surprise: %s confidence=%.3f >= threshold=%.2f",
            expected_tool, tool_conf, _HIGH_CONF_THRESHOLD,
        )
        return
    if tool_conf >= _MOD_CONF_THRESHOLD:
        surprise_label = f"low_severity:{surprise_label}"

    target = path or default_surprise_events_path()
    event = {
        "schema_version": 1,
        "event_type": "voe_surprise",
        "timestamp": time.time(),
        "expected": expected,
        "actual": actual,
        "surprise_label": surprise_label,
        "context_snapshot": dict(context_snapshot or {}),
        "guard_message": guard_message,
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("WM VoE learning append failed: %s", exc)
        return

    record_surprise_learning(
        expected,
        actual,
        surprise_label,
        path=learned_path,
    )

    auto_update_predictions(learned_path)


# --- Self-healing: auto-update WM prediction rules (WM-P12-01) ---

AUTO_UPDATE_THRESHOLD = int(os.environ.get("MIMIR_WM_AUTO_UPDATE_THRESHOLD", "10"))
_self_healing_additions: set[str] = set()
_self_healing_confidence: dict[str, float] = {}  # tool → data-driven confidence (hit/total)
_self_healing_last_update: float = 0.0
_SELF_HEAL_UPDATE_COOLDOWN = 300.0  # 5 min between reads
_HIGH_CONF_THRESHOLD = 0.5  # confidence ≥50% → skip writing surprise (self-healed)
_MOD_CONF_THRESHOLD = 0.10  # confidence ≥10% → write with low_severity label

# Tools from test/benchmark noise, never add to predictions
_SELF_HEAL_EXCLUDE = frozenset({
    "echo", "crash_tool", "nonexistent", "calc", "orphan_tool",
    "tool_b", "noop_tool", "read_file", "session_search",
})

# Map actual tool names to _INTENT_SKILLS-compatible names
_SELF_HEAL_TOOL_MAP: dict[str, str] = {
    "terminal": "run_terminal_cmd",
}


def auto_update_predictions(path: Path | None = None) -> None:
    """Read learned_surprises.json and extract tools with hit_count >= threshold.

    Updates the global _self_healing_additions set, which is read by
    get_self_healing_additions() and merged into predictions in world_model_spike.
    Rate-limited to once per SELF_HEAL_UPDATE_COOLDOWN seconds.
    """
    global _self_healing_additions, _self_healing_confidence, _self_healing_last_update

    now = time.time()
    if now - _self_healing_last_update < _SELF_HEAL_UPDATE_COOLDOWN:
        return
    _self_healing_additions = set()
    _self_healing_confidence = {}

    target = path or default_learned_surprises_path()
    index = _load_learned_index(target)
    entries = index.get("entries", {})

    additions: set[str] = set()
    tool_confidences: dict[str, float] = {}
    total_events = sum(e.get("hit_count", 0) for e in entries.values()) or 1
    for key, entry in entries.items():
        hit_count = entry.get("hit_count", 0)
        if hit_count < AUTO_UPDATE_THRESHOLD:
            continue
        actual_str = entry.get("actual", "")
        for tool in actual_str.split(","):
            tool = tool.strip()
            if not tool or tool in _SELF_HEAL_EXCLUDE:
                continue
            tool = _SELF_HEAL_TOOL_MAP.get(tool, tool)
            additions.add(tool)
            # Track max hit_count for this mapped tool for confidence
            tool_confidences[tool] = max(tool_confidences.get(tool, 0), hit_count)

    _self_healing_additions = additions
    _self_healing_confidence = {
        t: round(h / total_events, 3)
        for t, h in tool_confidences.items()
    }
    _self_healing_last_update = now

    if additions:
        logger.info(
            "WM self-heal: auto-added %s (confidence=%s) from %d learned patterns (threshold=%d)",
            sorted(additions), _self_healing_confidence, len(entries), AUTO_UPDATE_THRESHOLD,
        )


def get_self_healing_additions() -> set[str]:
    """Return current self-healing tool additions (merged into predict())."""
    return set(_self_healing_additions)


def get_self_healing_confidence() -> dict[str, float]:
    """Return confidence scores for self-healed tools (0.0-1.0, hit_count/total_events)."""
    return dict(_self_healing_confidence)
