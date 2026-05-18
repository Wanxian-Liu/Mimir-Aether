"""
Degeneration Guard — 对话退化检测引擎

来源: LeWM (2603.19312) §3.1 SIGReg + §5.2 VoE
配置: data/degeneration_guard.json

检测信号:
  - loop_detection:      同一工具 ≥3次/5轮 无进展
  - information_density:  最近N轮新信息占比 <40%
  - context_quality:      压缩后关键信息保留率 <50%
  - surprise_gate:        执行结果语义矛盾
  - recovery_loop:        同一任务恢复触发 ≥3次 (→ degeneration-guard 通道)

集成: evaluator-optimizer 的 evaluate 步骤前预检
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 信号类型
# ═══════════════════════════════════════════════════════════════════════════════

class DegenerationSignal(Enum):
    CLEAN = "clean"
    LOOP_DETECTED = "loop_detected"               # ⚠️
    LOW_INFORMATION_DENSITY = "low_information"    # ⚠️
    CONTEXT_QUALITY_DROP = "context_quality_drop"  # ⚠️
    SURPRISE_DETECTED = "surprise_detected"        # 🔴
    RECOVERY_LOOP = "recovery_loop"                # 🔴


@dataclass
class DegenerationReport:
    """退化检测报告"""
    signal: DegenerationSignal = DegenerationSignal.CLEAN
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def is_clean(self) -> bool:
        return self.signal == DegenerationSignal.CLEAN

    @property
    def needs_replan(self) -> bool:
        return self.signal in (
            DegenerationSignal.SURPRISE_DETECTED,
            DegenerationSignal.RECOVERY_LOOP,
        )

    @property
    def needs_warning(self) -> bool:
        return self.signal in (
            DegenerationSignal.LOOP_DETECTED,
            DegenerationSignal.LOW_INFORMATION_DENSITY,
            DegenerationSignal.CONTEXT_QUALITY_DROP,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 跟踪数据结构
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TurnRecord:
    """单轮工具调用记录"""
    turn_index: int
    tools_called: List[str] = field(default_factory=list)
    files_touched: Set[str] = field(default_factory=set)
    new_concepts: Set[str] = field(default_factory=set)
    has_new_info: bool = False
    timestamp: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════════════════
# 配置加载
# ═══════════════════════════════════════════════════════════════════════════════

def _load_guard_config() -> dict:
    """从 data/degeneration_guard.json 加载配置"""
    # 尝试多个路径 (repo root vs runtime home)
    search_paths = [
        Path(__file__).parent.parent / "data" / "degeneration_guard.json",
    ]
    # 也尝试 runtime home
    runtime_home = os.environ.get("MIMIR_AETHER_HOME", os.environ.get("MIMIRAETHER_HOME", ""))
    if runtime_home:
        search_paths.append(Path(runtime_home) / "data" / "degeneration_guard.json")

    for p in search_paths:
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception as e:
                logger.warning("Failed to load degeneration_guard.json from %s: %s", p, e)

    logger.warning("degeneration_guard.json not found, using defaults")
    return {}


_DEFAULT_CONFIG = {
    "degeneration_signals": {
        "loop_detection": {
            "threshold": 3,
            "window_turns": 5,
            "action": "warn",
        },
        "information_density": {
            "info_density_min": 0.4,
            "window_turns": 5,
            "action": "warn",
        },
        "context_quality": {
            "min_retention_rate": 0.50,
            "action": "compress_trigger",
        },
        "surprise_gate": {
            "deviation_threshold": "high",
            "action": "replan",
        },
        "recovery_loop": {
            "threshold": 3,
            "different_errors_min": 2,
            "action": "replan",
        },
    },
}


def _get_config_section(key: str) -> dict:
    config = _load_guard_config()
    signals = config.get("degeneration_signals", {}) or _DEFAULT_CONFIG["degeneration_signals"]
    return signals.get(key, _DEFAULT_CONFIG["degeneration_signals"].get(key, {}))


# ═══════════════════════════════════════════════════════════════════════════════
# Degeneration Guard 主类
# ═══════════════════════════════════════════════════════════════════════════════

class DegenerationGuard:
    """
    对话退化检测器

    用法:
        guard = DegenerationGuard()
        guard.record_turn(tools=["read_file", "search_files"], files={...})
        report = guard.run_checks()
        if report.needs_replan:
            ...  # 触发重规划
    """

    def __init__(self):
        self.turns: List[TurnRecord] = []
        self._turn_counter = 0
        self._external_signals: List[Dict[str, Any]] = []
        self._last_compression_context: Dict[str, Any] = {}
        self._config = _load_guard_config()

    # ── 记录 ──────────────────────────────────────────────────────────────

    def record_turn(
        self,
        tools: List[str],
        files_touched: Optional[Set[str]] = None,
        new_concepts: Optional[Set[str]] = None,
        has_new_info: bool = True,
    ) -> None:
        """记录一轮工具调用"""
        self._turn_counter += 1
        turn = TurnRecord(
            turn_index=self._turn_counter,
            tools_called=list(tools) if tools else [],
            files_touched=files_touched or set(),
            new_concepts=new_concepts or set(),
            has_new_info=has_new_info,
        )
        self.turns.append(turn)

    def record_signal(self, signal_name: str, data: Dict[str, Any]) -> None:
        """记录外部信号 (由 recovery_loop / surprise 等模块调用)"""
        self._external_signals.append({
            "signal": signal_name,
            "data": data,
            "timestamp": time.time(),
        })
        logger.debug("DegenerationGuard recorded signal: %s", signal_name)

    def record_compression(
        self,
        pre_message_count: int,
        post_message_count: int,
        key_info_retained: float,
    ) -> None:
        """记录上下文压缩事件"""
        self._last_compression_context = {
            "pre_count": pre_message_count,
            "post_count": post_message_count,
            "retention_rate": key_info_retained,
            "timestamp": time.time(),
        }

    # ── 检测 ──────────────────────────────────────────────────────────────

    def detect_loop(self, window: int = None) -> Optional[str]:
        """
        循环检测: 同一工具 ≥3次/5轮 无进展

        Returns:
            告警消息或 None
        """
        cfg = _get_config_section("loop_detection")
        window = window or cfg.get("window_turns", 5)
        threshold = cfg.get("threshold", 3)

        if len(self.turns) < threshold:
            return None

        recent = self.turns[-window:]
        # 统计最近 window 轮中每个工具的调用次数
        tool_counts: Dict[str, int] = {}
        files_touched_total = set()

        for turn in recent:
            for tool in turn.tools_called:
                tool_counts[tool] = tool_counts.get(tool, 0) + 1
            files_touched_total |= turn.files_touched

        for tool, count in tool_counts.items():
            if count >= threshold and len(files_touched_total) == 0:
                msg = (
                    f"⚠️ LOOP_DETECTED: tool '{tool}' called {count}x "
                    f"in {len(recent)} turns with no file progress. "
                    f"Suggestion: change approach or request user input."
                )
                logger.warning(msg)
                return msg

        return None

    def detect_low_information(self, window: int = None) -> Optional[str]:
        """
        信息密度检测: 最近 window 轮中新信息占比 < info_density_min

        Returns:
            告警消息或 None
        """
        cfg = _get_config_section("information_density")
        window = window or cfg.get("window_turns", 5)
        min_density = cfg.get("info_density_min", 0.4)

        if len(self.turns) < window:
            return None

        recent = self.turns[-window:]
        new_info_turns = sum(1 for t in recent if t.has_new_info)
        density = new_info_turns / len(recent)

        if density < min_density:
            msg = (
                f"⚠️ LOW_INFORMATION_DENSITY: {density:.0%} of recent {len(recent)} turns "
                f"contain new information (threshold: {min_density:.0%}). "
                f"Suggestion: execute MVA (Minimum Viable Action) or request feedback."
            )
            logger.warning(msg)
            return msg

        return None

    def detect_context_quality_drop(self) -> Optional[str]:
        """
        上下文质量检测: 压缩后关键信息保留率 < min_retention_rate

        Returns:
            告警消息或 None
        """
        cfg = _get_config_section("context_quality")
        min_rate = cfg.get("min_retention_rate", 0.50)

        if not self._last_compression_context:
            return None

        rate = self._last_compression_context.get("retention_rate", 1.0)
        if rate < min_rate:
            msg = (
                f"⚠️ CONTEXT_QUALITY_DROP: retention rate {rate:.0%} < "
                f"threshold {min_rate:.0%}. Triggering context reorganization."
            )
            logger.warning(msg)
            return msg

        return None

    def detect_surprise(self, expected: str, actual: str) -> Optional[str]:
        """
        Surprise 门控: 区分表面偏差与语义偏差 (VoE 类比)

        只对语义级矛盾触发重规划（表面格式差异忽略）。

        Args:
            expected: 预期结果描述
            actual:   实际结果描述

        Returns:
            告警消息 (🔴) 或 None
        """
        cfg = _get_config_section("surprise_gate")

        # 简化检查: 比较关键词矛盾
        # 实际使用中由 LLM 辅助判断语义矛盾
        expected_lower = expected.lower()
        actual_lower = actual.lower()

        # 关键对立词检测
        contradictions = [
            # (expected_pattern, actual_pattern, label)
            (r"\bfound\b", r"\bnot\s*found\b", "existence mismatch"),
            (r"\bexists\b", r"\bdoesn't\s*exist\b", "existence mismatch"),
            (r"\bsuccess\b", r"\bfail", "outcome reversal"),
            (r"\bpass", r"\bfail", "outcome reversal"),
        ]

        for exp_pat, act_pat, label in contradictions:
            if (re.search(exp_pat, expected_lower, re.IGNORECASE) and
                    re.search(act_pat, actual_lower, re.IGNORECASE)):
                msg = (
                    f"🔴 SURPRISE_DETECTED: {label} — "
                    f"expected '{expected[:80]}' but got '{actual[:80]}'. Replanning."
                )
                logger.warning(msg)
                return msg

        return None

    def detect_recovery_loop(self) -> Optional[str]:
        """
        恢复循环检测: 检查来自 recovery 的外部信号

        Returns:
            "replan" 或 None
        """
        cfg = _get_config_section("recovery_loop")
        threshold = cfg.get("threshold", 3)

        recent_signals = [
            s for s in self._external_signals
            if s["signal"] == "recovery_loop" and
            s["timestamp"] > time.time() - 300
        ]

        if len(recent_signals) >= 1:
            # 信号本身已经包含了判断逻辑 (ToolRecovery.recovery_loop_check)
            data = recent_signals[-1]["data"]
            if data.get("count", 0) >= threshold:
                return data.get("message", "🔴 RECOVERY_LOOP triggered")

        return None

    # ═══════════════════════════════════════════════════════════════════════
    # 综合检查
    # ═══════════════════════════════════════════════════════════════════════

    def run_checks(
        self,
        expected_vs_actual: Optional[tuple[str, str]] = None,
    ) -> DegenerationReport:
        """
        运行所有退化检测。

        Args:
            expected_vs_actual: 可选的 (expected, actual) 用于 surprise_gate

        Returns:
            DegenerationReport 包含检测结果
        """
        report = DegenerationReport()

        # 按严重程度从高到低检查
        checks = []

        # 🔴 级别
        recovery_msg = self.detect_recovery_loop()
        if recovery_msg:
            report.signal = DegenerationSignal.RECOVERY_LOOP
            report.warnings.append(recovery_msg)
            report.details["recovery_loop"] = recovery_msg
            return report  # 🔴 立即返回，最高优先级

        if expected_vs_actual:
            surprise_msg = self.detect_surprise(*expected_vs_actual)
            if surprise_msg:
                report.signal = DegenerationSignal.SURPRISE_DETECTED
                report.warnings.append(surprise_msg)
                report.details["surprise"] = surprise_msg
                return report  # 🔴 立即返回

        # ⚠️ 级别
        loop_msg = self.detect_loop()
        if loop_msg:
            report.signal = DegenerationSignal.LOOP_DETECTED
            report.warnings.append(loop_msg)
            report.details["loop"] = loop_msg

        info_msg = self.detect_low_information()
        if info_msg:
            if report.signal == DegenerationSignal.CLEAN:
                report.signal = DegenerationSignal.LOW_INFORMATION_DENSITY
            report.warnings.append(info_msg)
            report.details["low_info"] = info_msg

        quality_msg = self.detect_context_quality_drop()
        if quality_msg:
            if report.signal == DegenerationSignal.CLEAN:
                report.signal = DegenerationSignal.CONTEXT_QUALITY_DROP
            report.warnings.append(quality_msg)
            report.details["context_quality"] = quality_msg

        # 汇总
        report.details["turn_count"] = self._turn_counter
        report.details["total_warnings"] = len(report.warnings)

        return report

    def reset(self) -> None:
        """重置状态（新任务开始时调用）"""
        self.turns.clear()
        self._turn_counter = 0
        self._external_signals.clear()
        self._last_compression_context.clear()
        logger.debug("DegenerationGuard reset")

    def get_summary(self) -> str:
        """获取状态摘要"""
        return (
            f"DegenerationGuard: {self._turn_counter} turns tracked, "
            f"{len(self._external_signals)} external signals"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════════

_global_guard: Optional[DegenerationGuard] = None


def get_guard() -> DegenerationGuard:
    """获取全局退化检测器"""
    global _global_guard
    if _global_guard is None:
        _global_guard = DegenerationGuard()
    return _global_guard


def reset_guard() -> None:
    """重置全局退化检测器"""
    global _global_guard
    if _global_guard is not None:
        _global_guard.reset()
