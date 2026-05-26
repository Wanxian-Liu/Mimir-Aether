"""1c DecisionRing + Compressor policy loader (IQ-EVO-43/44 · Wave 7).

Manages ``decision_compressor_policy.json`` and audit trail. Does **not** touch
skills tree or ``tuned_thresholds.json`` Top-3 keys.
"""

from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from mimir_constants import get_mimir_home

SCHEMA_VERSION = 1

TOP3_KEYS = frozenset(
    {
        "compressor.threshold_percent",
        "degeneration.loop_detection.threshold",
        "tool_quality.degraded_threshold",
    }
)

RING_BOUNDS: Dict[str, Dict[str, Any]] = {
    "max_retries": {"default": 3, "min": 2, "max": 5, "step": 1, "type": "int"},
    "default_backoff_base": {
        "default": 1.0,
        "min": 0.5,
        "max": 2.0,
        "step": 0.25,
        "type": "float",
    },
    "max_backoff": {"default": 60.0, "min": 30.0, "max": 120.0, "step": 5.0, "type": "float"},
    "compress_context_pressure": {
        "default": 0.85,
        "min": 0.70,
        "max": 0.95,
        "step": 0.05,
        "type": "float",
    },
    "truncate_context_pressure": {
        "default": 0.95,
        "min": 0.85,
        "max": 1.0,
        "step": 0.05,
        "type": "float",
    },
    "confidence_floor": {
        "default": 0.5,
        "min": 0.3,
        "max": 0.8,
        "step": 0.05,
        "type": "float",
    },
    "cooldown_scale": {
        "default": 1.0,
        "min": 0.5,
        "max": 2.0,
        "step": 0.1,
        "type": "float",
    },
}

COMPRESSOR_BOUNDS: Dict[str, Dict[str, Any]] = {
    "protect_first_n": {"default": 3, "min": 2, "max": 5, "step": 1, "type": "int"},
    "protect_last_n": {"default": 6, "min": 4, "max": 10, "step": 1, "type": "int"},
    "summary_target_ratio": {
        "default": 0.20,
        "min": 0.10,
        "max": 0.30,
        "step": 0.05,
        "type": "float",
    },
    "summary_failure_cooldown_s": {
        "default": 600,
        "min": 300,
        "max": 900,
        "step": 60,
        "type": "int",
    },
    "preflight_relax_ratio": {
        "default": 0.80,
        "min": 0.70,
        "max": 0.90,
        "step": 0.05,
        "type": "float",
    },
    "tail_token_budget": {
        "default": 4000,
        "min": 2000,
        "max": 8000,
        "step": 500,
        "type": "int",
    },
}

DEFAULT_COMPRESSOR_SECTION = {
    k: spec["default"] for k, spec in COMPRESSOR_BOUNDS.items()
}

def policy_1c_enabled() -> bool:
    return os.environ.get("MIMIR_AUTO_1C_POLICY", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def policy_path() -> Path:
    return get_mimir_home() / "data" / "decision_compressor_policy.json"


def audit_path() -> Path:
    return get_mimir_home() / "data" / "decision_compressor_audit.jsonl"


def _default_policy() -> Dict[str, Any]:
    ring = {k: spec["default"] for k, spec in RING_BOUNDS.items()}
    ring["rule_priority_bias"] = {}
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "ring": ring,
        "compressor": dict(DEFAULT_COMPRESSOR_SECTION),
    }


def _clamp_compressor_key(key: str, value: Union[int, float]) -> Union[int, float]:
    spec = COMPRESSOR_BOUNDS[key]
    lo, hi = spec["min"], spec["max"]
    if spec["type"] == "int":
        return int(max(lo, min(hi, round(value))))
    return float(max(lo, min(hi, round(float(value), 4))))


def _clamp_ring_key(key: str, value: Union[int, float]) -> Union[int, float]:
    spec = RING_BOUNDS[key]
    lo, hi = spec["min"], spec["max"]
    if spec["type"] == "int":
        return int(max(lo, min(hi, round(value))))
    return float(max(lo, min(hi, round(float(value), 4))))


def _reject_top3_in_patch(patch: Dict[str, Any]) -> Optional[str]:
    for k in patch:
        if k in TOP3_KEYS:
            return k
    ring_patch = patch.get("ring")
    if isinstance(ring_patch, dict):
        for k in ring_patch:
            if k in TOP3_KEYS:
                return k
    return None


def load_policy() -> Dict[str, Any]:
    path = policy_path()
    if not path.is_file():
        return _default_policy()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return _default_policy()
    if not isinstance(raw, dict):
        return _default_policy()
    out = _default_policy()
    ring_in = raw.get("ring")
    if isinstance(ring_in, dict):
        for key in RING_BOUNDS:
            if key in ring_in:
                out["ring"][key] = _clamp_ring_key(key, ring_in[key])
        bias = ring_in.get("rule_priority_bias")
        if isinstance(bias, dict):
            out["ring"]["rule_priority_bias"] = bias
    comp_in = raw.get("compressor")
    if isinstance(comp_in, dict):
        for key in COMPRESSOR_BOUNDS:
            if key in comp_in:
                out["compressor"][key] = _clamp_compressor_key(key, comp_in[key])
    out["schema_version"] = SCHEMA_VERSION
    return out


def save_policy(policy: Dict[str, Any]) -> None:
    path = policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = deepcopy(policy)
    payload["schema_version"] = SCHEMA_VERSION
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    ring = payload.get("ring") or {}
    for key in RING_BOUNDS:
        if key in ring:
            ring[key] = _clamp_ring_key(key, ring[key])
    truncate = float(ring.get("truncate_context_pressure", 0.95))
    compress = float(ring.get("compress_context_pressure", 0.85))
    if truncate <= compress:
        ring["truncate_context_pressure"] = min(
            RING_BOUNDS["truncate_context_pressure"]["max"],
            compress + RING_BOUNDS["truncate_context_pressure"]["step"],
        )
    comp = payload.get("compressor") or {}
    for key in COMPRESSOR_BOUNDS:
        if key in comp:
            comp[key] = _clamp_compressor_key(key, comp[key])
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_ring_section() -> Dict[str, Any]:
    return dict(load_policy().get("ring") or {})


def load_compressor_section() -> Dict[str, Any]:
    return dict(load_policy().get("compressor") or DEFAULT_COMPRESSOR_SECTION)


def compressor_init_kwargs_from_policy() -> Dict[str, Any]:
    """Second-tier compressor knobs for ``MimirContextCompressor`` (1c; not Top-3)."""
    comp = load_compressor_section()
    return {
        "protect_first_n": int(comp.get("protect_first_n", 3)),
        "protect_last_n": int(comp.get("protect_last_n", 6)),
        "summary_target_ratio": float(comp.get("summary_target_ratio", 0.20)),
        "summary_failure_cooldown_s": int(comp.get("summary_failure_cooldown_s", 600)),
        "preflight_relax_ratio": float(comp.get("preflight_relax_ratio", 0.80)),
        "tail_token_budget": int(comp.get("tail_token_budget", 4000)),
    }


def merge_ring_policy_into_config(config: Any) -> None:
    """Apply persisted ring.* values onto ``DecisionRingConfig`` (in-place)."""
    ring = load_ring_section()
    if "max_retries" in ring:
        config.max_retries = int(ring["max_retries"])
    if "default_backoff_base" in ring:
        config.default_backoff_base = float(ring["default_backoff_base"])
    if "max_backoff" in ring:
        config.max_backoff = float(ring["max_backoff"])
    for attr in ("compress_context_pressure", "truncate_context_pressure", "confidence_floor", "cooldown_scale"):
        if attr in ring and hasattr(config, attr):
            setattr(config, attr, float(ring[attr]))


def apply_policy_patch(patch: Dict[str, Any]) -> Dict[str, Any]:
    """Merge patch into policy; reject Top-3 and out-of-range ring/compressor scalars."""
    rejected = _reject_top3_in_patch(patch)
    if rejected:
        return {"ok": False, "rejected": True, "reason": f"top3_key:{rejected}"}

    candidate = deepcopy(load_policy())
    applied: List[str] = []
    ring_patch = patch.get("ring")
    if isinstance(ring_patch, dict):
        for key, val in ring_patch.items():
            if key == "rule_priority_bias":
                if isinstance(val, dict):
                    candidate["ring"]["rule_priority_bias"] = val
                    applied.append(f"ring.{key}")
                continue
            if key not in RING_BOUNDS:
                return {"ok": False, "rejected": True, "reason": f"unknown_ring_key:{key}"}
            clamped = _clamp_ring_key(key, val)
            if clamped != val:
                return {"ok": False, "rejected": True, "reason": f"out_of_range:{key}"}
            candidate["ring"][key] = clamped
            applied.append(f"ring.{key}")

    comp_patch = patch.get("compressor")
    if isinstance(comp_patch, dict):
        for key, val in comp_patch.items():
            if key not in COMPRESSOR_BOUNDS:
                return {"ok": False, "rejected": True, "reason": f"unknown_compressor_key:{key}"}
            clamped = _clamp_compressor_key(key, val)
            if clamped != val:
                return {"ok": False, "rejected": True, "reason": f"out_of_range:{key}"}
            candidate["compressor"][key] = clamped
            applied.append(f"compressor.{key}")

    if not applied:
        return {"ok": False, "rejected": True, "reason": "empty_patch"}

    save_policy(candidate)
    return {"ok": True, "rejected": False, "applied": applied}


def _append_audit(entry: Dict[str, Any]) -> None:
    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _tune_wrote_threshold_percent(pipeline_result: Dict[str, Any]) -> bool:
    changes = pipeline_result.get("tune_changes") or []
    if not isinstance(changes, list):
        return False
    for entry in changes:
        if isinstance(entry, dict) and entry.get("key") == "compressor.threshold_percent":
            return True
    return False


def _compressor_nudge_is_aggressive(key: str, cur: Union[int, float], new_val: Union[int, float]) -> bool:
    if key == "protect_first_n" and new_val < cur:
        return True
    if key == "protect_last_n" and new_val < cur:
        return True
    if key == "summary_target_ratio" and new_val > cur:
        return True
    if key == "preflight_relax_ratio" and new_val < cur:
        return True
    if key == "tail_token_budget" and new_val < cur:
        return True
    return False


def _pick_compressor_nudge(
    policy: Dict[str, Any],
    pipeline_result: Dict[str, Any],
) -> Optional[Tuple[str, Union[int, float]]]:
    errors = pipeline_result.get("errors") or []
    degraded = pipeline_result.get("degraded_tools") or []
    error_count = len(errors) if isinstance(errors, list) else 0
    degraded_count = len(degraded) if isinstance(degraded, list) else 0
    comp = policy["compressor"]
    block_aggressive = _tune_wrote_threshold_percent(pipeline_result)

    candidates: List[Tuple[str, Union[int, float], int]] = []

    if error_count >= 2:
        key = "protect_first_n"
        cur = int(comp[key])
        new_val = _clamp_compressor_key(key, cur + 1)
        if new_val > cur:
            pri = 0 if not (block_aggressive and _compressor_nudge_is_aggressive(key, cur, new_val)) else -1
            if pri >= 0:
                candidates.append((key, new_val, pri))

    if degraded_count >= 2:
        key = "protect_last_n"
        cur = int(comp[key])
        new_val = _clamp_compressor_key(key, cur + 1)
        if new_val > cur:
            pri = 1 if not (block_aggressive and _compressor_nudge_is_aggressive(key, cur, new_val)) else -1
            if pri >= 0:
                candidates.append((key, new_val, pri))

    if error_count >= 3 and not block_aggressive:
        key = "summary_target_ratio"
        cur = float(comp[key])
        new_val = _clamp_compressor_key(key, cur + 0.05)
        if new_val > cur:
            candidates.append((key, new_val, 2))

    if error_count >= 4 and not block_aggressive:
        key = "preflight_relax_ratio"
        cur = float(comp[key])
        new_val = _clamp_compressor_key(key, cur - 0.05)
        if new_val < cur:
            candidates.append((key, new_val, 3))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[2])
    key, new_val, _ = candidates[0]
    return key, new_val


def _pick_ring_nudge(
    policy: Dict[str, Any],
    pipeline_result: Dict[str, Any],
) -> Optional[Tuple[str, Union[int, float]]]:
    errors = pipeline_result.get("errors") or []
    degraded = pipeline_result.get("degraded_tools") or []
    error_count = len(errors) if isinstance(errors, list) else 0
    degraded_count = len(degraded) if isinstance(degraded, list) else 0
    ring = policy["ring"]

    if error_count >= 2:
        key = "max_retries"
        cur = int(ring[key])
        new_val = _clamp_ring_key(key, cur - 1)
        if new_val < cur:
            return key, new_val
    if degraded_count >= 2:
        key = "compress_context_pressure"
        cur = float(ring[key])
        new_val = _clamp_ring_key(key, cur - 0.05)
        if new_val < cur:
            return key, new_val
    return None


def run_1c_policy_after_pipeline_close(
    pipeline_result: Dict[str, Any],
    *,
    session_id: str = "",
    task_name: str = "",
) -> List[Dict[str, Any]]:
    """Up to 1×D* + 1×C* nudge per close when ``MIMIR_AUTO_1C_POLICY=1`` (≤2 total)."""
    if not policy_1c_enabled():
        return []

    policy = load_policy()
    patch: Dict[str, Any] = {}
    entries: List[Dict[str, Any]] = []

    ring_nudge = _pick_ring_nudge(policy, pipeline_result)
    if ring_nudge:
        rk, rv = ring_nudge
        patch["ring"] = {rk: rv}

    comp_nudge = _pick_compressor_nudge(policy, pipeline_result)
    if comp_nudge:
        ck, cv = comp_nudge
        patch.setdefault("compressor", {})[ck] = cv

    if not patch:
        _append_audit(
            {
                "ts": time.time(),
                "session_id": session_id,
                "task_name": (task_name or "")[:80],
                "applied": [],
                "skipped": "no_signal",
            }
        )
        return []

    result = apply_policy_patch(patch)
    for section, keys in (("ring", patch.get("ring") or {}), ("compressor", patch.get("compressor") or {})):
        for key, val in (keys.items() if isinstance(keys, dict) else []):
            entry = {
                "ts": time.time(),
                "session_id": session_id,
                "task_name": (task_name or "")[:80],
                "key": f"{section}.{key}",
                "value": val,
                "ok": result.get("ok"),
                "rejected": result.get("rejected", False),
                "reason": result.get("reason", ""),
            }
            entries.append(entry)
            _append_audit(entry)

    if result.get("ok"):
        return entries
    return []


def post_analysis_will_run(pipeline_result: Dict[str, Any]) -> bool:
    from agent.post_close_analysis import _env_truthy, _pipeline_has_analysis_signal

    return _env_truthy("MIMIR_AUTO_ANALYSIS") and _pipeline_has_analysis_signal(
        pipeline_result
    )


def run_tune_and_1c_after_post_analysis(
    pipeline_result: Dict[str, Any],
    *,
    session_id: str = "",
    task_name: str = "",
) -> Dict[str, Any]:
    """B-4: after async post_analysis — tune (1b) then 1c ring nudge."""
    out: Dict[str, Any] = {"tune_changes": [], "policy_1c_changes": []}
    try:
        from agent.auto_tuner import run_tune_after_pipeline_close

        out["tune_changes"] = run_tune_after_pipeline_close(
            pipeline_result,
            session_id=session_id,
        )
        pipeline_result["tune_changes"] = out["tune_changes"]
    except Exception:
        pass
    try:
        out["policy_1c_changes"] = run_1c_policy_after_pipeline_close(
            pipeline_result,
            session_id=session_id,
            task_name=task_name,
        )
    except Exception:
        pass
    return out
