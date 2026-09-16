"""Bounded runtime threshold overrides (IQ-EVO Wave 5 · 1b)."""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

from mimir_constants import get_mimir_home

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# RS12（2026-09-13）：被静默夹紧的 (key, requested) 只记一次 INFO，避免每次读盘重复刷日志。
# 有界：最多 256 个签名；超出后不再新增签名（日志降级为"不重复记"，不阻断功能）。
_CLAMP_LOGGED: set = set()
_CLAMP_LOGGED_MAX = 256

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
    # W-①（2026-09-12 · 刘哥批授权）——prompt 提示块的「最小样本」门槛。
    # 此前该键**未注册**：tool_quality.prompt_min_sample() 调 get_tuned_float()
    # 必抛 KeyError（被吞）→ 注释宣称的 env>tuned>20 中间环节是**死链**，
    # 实际生效链只有 env>20。现注册为有界键：default 20（与 _DEFAULT_PROMPT_MIN_SAMPLE
    # 同值）、min 8（R3 分布数据的同解区间下界：真实工具 sub-threshold 全部
    # ≤7 次调用，≥20 次调用者全部 ≥0.3 质量分）、max 100。
    "tool_quality.prompt_min_sample": {
        "default": 20,
        "min": 8,
        "max": 100,
        "step": 1,
        "type": "int",
    },
    # B9（2026-09-13 · 阈值按有效窗口定）：一等公民上限。
    # 语义：threshold_tokens = min(configured, cap, floor(0.75 x context_length))。
    # **键缺失（overrides 未置位）⇒ 上限不生效**——resolve_effective_window_cap()
    # 读的是 load_overrides() 的显式置位，不是本 default，故 default 只作文档锚点
    # （1M = 1M 窗口模型下不夹紧），避免「配置没动、阈值却变了」。
    "compressor.effective_window_tokens": {
        "default": 1048576,
        "min": 8000,
        "max": 1048576,
        "step": 1000,
        "type": "int",
    },
    # 2026-09-16 刘哥令（阈值 12万->30万 实验）：**会话卫生层**触发阈值（ACTUAL tokens）。
    # 此前是 agent_route_mixin.py 里的裸常量 200_000 ⇒ 它比 agent 层 30万 更早拦下会话，
    # 使 agent 层那条线不可达。注册为有界键后：每轮读盘 ⇒ 调阈值**不需重启**。
    # default 保留历史值 200_000（键被移除即回退到旧行为，不做隐性变更）。
    "compressor.hygiene_token_threshold": {
        "default": 200_000,
        "min": 20_000,
        "max": 1_048_576,
        "step": 10_000,
        "type": "int",
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
        clamped: Union[int, float] = int(max(lo, min(hi, round(value))))
    else:
        clamped = float(max(lo, min(hi, round(float(value), 4))))
    # RS12（2026-09-13）：夹紧必须留痕。此前 `compressor.threshold_percent: 0.12`
    # （低于 min=0.35）被静默夹到 0.35 —— 文件里写 0.12、运行时拿 0.35，
    # 属「声明 ≠ 生效」的第 3 例（前两例：窗口 50/200 双值、B9 env 架空 tuned）。
    # 判据：日志出现 [TUNED-CLAMP] 即说明该键的配置值不可达。
    if clamped != value:
        _sig = (key, value)
        if _sig not in _CLAMP_LOGGED:
            if len(_CLAMP_LOGGED) < _CLAMP_LOGGED_MAX:
                _CLAMP_LOGGED.add(_sig)
            logger.info(
                "[TUNED-CLAMP] %s requested=%s clamped=%s bounds=[%s, %s]",
                key, value, clamped, lo, hi,
            )
    return clamped


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
