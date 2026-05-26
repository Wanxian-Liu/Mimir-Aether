"""Bounded runtime threshold overrides (IQ-EVO Wave 5 · 1b)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

from mimir_constants import get_mimir_home

_lock = threading.Lock()

# Top-3 from docs/phase0/hardcoded-thresholds.md (🔴)
_REGISTRY: Dict[str, Dict[str, Union[int, float]]] = {
    "compressor.threshold_percent": {
        "default": 0.50,
        "min": 0.35,
        "max": 0.70,
        "step": 0.05,
        "type": "float",
    },
    "degeneration.loop_detection.threshold": {
        "default": 3,
        "min": 2,
        "max": 5,
        "step": 1,
        "type": "int",
    },
    "tool_quality.degraded_threshold": {
        "default": 0.50,
        "min": 0.30,
        "max": 0.70,
        "step": 0.05,
        "type": "float",
    },
}


def _overrides_path() -> Path:
    path = Path(get_mimir_home()) / "data" / "tuned_thresholds.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def registry_keys() -> list[str]:
    return list(_REGISTRY.keys())


def _clamp(key: str, value: Union[int, float]) -> Union[int, float]:
    spec = _REGISTRY[key]
    lo, hi = spec["min"], spec["max"]
    if spec["type"] == "int":
        return int(max(lo, min(hi, round(value))))
    return float(max(lo, min(hi, round(float(value), 4))))


def load_overrides() -> Dict[str, Union[int, float]]:
    path = _overrides_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        overrides = raw.get("overrides") if isinstance(raw, dict) else {}
        if not isinstance(overrides, dict):
            return {}
        out: Dict[str, Union[int, float]] = {}
        for key, val in overrides.items():
            if key in _REGISTRY:
                out[key] = _clamp(key, val)
        return out
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def get_tuned_value(key: str) -> Union[int, float]:
    """Return override if set, else registry default."""
    if key not in _REGISTRY:
        raise KeyError(key)
    spec = _REGISTRY[key]
    overrides = load_overrides()
    if key in overrides:
        return overrides[key]
    return spec["default"]  # type: ignore[return-value]


def get_tuned_float(key: str) -> float:
    return float(get_tuned_value(key))


def get_tuned_int(key: str) -> int:
    return int(get_tuned_value(key))


def set_override(key: str, value: Union[int, float], *, reason: str = "") -> Dict[str, Any]:
    """Persist one bounded override; returns audit entry."""
    if key not in _REGISTRY:
        raise KeyError(key)
    clamped = _clamp(key, value)
    with _lock:
        path = _overrides_path()
        payload: Dict[str, Any] = {"updated_at": time.time(), "overrides": {}}
        if path.is_file():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    payload["overrides"] = dict(existing.get("overrides") or {})
            except (OSError, json.JSONDecodeError):
                pass
        payload["overrides"][key] = clamped
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    entry = {
        "ts": time.time(),
        "key": key,
        "value": clamped,
        "reason": (reason or "")[:200],
    }
    return entry


def reset_overrides_for_tests() -> None:
    """Test helper — remove runtime override file."""
    with _lock:
        path = _overrides_path()
        if path.is_file():
            path.unlink()
