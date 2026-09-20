"""Bounded threshold tuning from feedback (IQ-EVO Wave 5 · 1b)."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from mimir_constants import get_mimir_home

from .experience_buffer import summarize_recent_experience
from .tuned_thresholds import get_tuned_float, get_tuned_int, set_override

logger = logging.getLogger(__name__)


def auto_tuner_enabled() -> bool:
    return os.environ.get("MIMIR_AUTO_TUNER", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _audit_path() -> Path:
    path = Path(get_mimir_home()) / "data" / "tune_audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _append_audit(entry: Dict[str, Any]) -> None:
    try:
        with open(_audit_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def run_tune_after_pipeline_close(
    pipeline_result: Dict[str, Any],
    *,
    session_id: str = "",
) -> List[Dict[str, Any]]:
    """Apply at most one bounded nudge per key when signals warrant it."""
    if not auto_tuner_enabled():
        return []

    summary = summarize_recent_experience()
    # ── 量具存活闸（IQ 批1③ · 2026-09-20 · 消费端补口）─────────────────────
    # 闸只「标注」不够 —— 消费端必须真的分支。缺口来源：commit 9346128 建了
    # instrument_status / scorable，但生产消费端 0 处读取它（三臂探针实测：
    # scorable 仅出现在 producer + 其测试，共 2 文件）⇒ 本函数仍会拿**停摆
    # 35 天**的旧计数去写 compressor.threshold_percent / loop_detection /
    # tool_quality 的 override。
    # 口径：非 live（absent / stale）或键缺失 ⇒ 计数不得作为调参证据，早退。
    # fail-closed：拿不到「可计入」证明时**不调参**（并在日志里发声，不静默）。
    if not summary.get("scorable", False):
        logger.warning(
            "[INSTRUMENT-GATE] auto_tuner 跳过本轮调参：量具不可计入 "
            "(instrument_status=%s, reason=%s) —— 不得用 absent/stale 量具的计数写 override",
            summary.get("instrument_status", "unknown"),
            (summary.get("n_a_reason") or (summary.get("instrument") or {}).get("reason") or ""),
        )
        return []
    degraded = pipeline_result.get("degraded_tools") or []
    errors = pipeline_result.get("errors") or []
    error_count = len(errors) if isinstance(errors, list) else 0
    degraded_count = len(degraded) if isinstance(degraded, list) else 0

    changes: List[Dict[str, Any]] = []

    # More tool failures → compress slightly earlier (lower threshold_percent).
    if summary.get("tool_failure_count", 0) >= 3 or error_count >= 2:
        key = "compressor.threshold_percent"
        cur = get_tuned_float(key)
        new_val = cur - 0.05
        if new_val < cur:
            entry = set_override(
                key,
                new_val,
                reason=f"tool_failures={summary.get('tool_failure_count')} errors={error_count}",
            )
            entry["session_id"] = session_id
            changes.append(entry)
            _append_audit(entry)

    # Repeated failures → more sensitive loop detection (lower repeat threshold).
    if summary.get("tool_failure_count", 0) >= 5:
        key = "degeneration.loop_detection.threshold"
        cur = get_tuned_int(key)
        if cur > 2:
            entry = set_override(
                key,
                cur - 1,
                reason=f"tool_failures={summary.get('tool_failure_count')}",
            )
            entry["session_id"] = session_id
            changes.append(entry)
            _append_audit(entry)

    # Many degraded tools → surface more in prompt (lower quality bar).
    if degraded_count >= 2 or summary.get("pipeline_close_count", 0) >= 2:
        key = "tool_quality.degraded_threshold"
        cur = get_tuned_float(key)
        new_val = cur - 0.05
        if new_val < cur:
            entry = set_override(
                key,
                new_val,
                reason=f"degraded={degraded_count} pipeline_closes={summary.get('pipeline_close_count')}",
            )
            entry["session_id"] = session_id
            changes.append(entry)
            _append_audit(entry)

    return changes
