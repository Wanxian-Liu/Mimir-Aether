
"""
MimirAether Monitor Collector - 监控环核心模块

整合:
- MetricsCollector: 指标采集器，收集系统指标
- AnomalyDetector: 异常检测器，识别异常行为
- HealthChecker: 健康检查器，定期检查系统状态
"""

from __future__ import annotations

import logging
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Deque, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ============================================================================
# 枚举和常量
# ============================================================================

class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AnomalyType(Enum):
    """异常类型枚举"""
    TOKEN_SPIKE = "token_spike"
    ERROR_RATE_HIGH = "error_rate_high"
    LATENCY_HIGH = "latency_high"
    RATE_LIMIT_IMMINENT = "rate_limit_imminent"
    SESSION_LEAK = "session_leak"
    MEMORY_PRESSURE = "memory_pressure"
    BUDGET_EXHAUSTED = "budget_exhausted"


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: float
    metric_name: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Anomaly:
    """异常记录"""
    anomaly_type: AnomalyType
    severity: str  # low, medium, high, critical
    message: str
    timestamp: float
    metric_name: str
    current_value: float
    threshold: float
    recommendation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """健康报告"""
    status: HealthStatus
    timestamp: float
    checks: Dict[str, Any] = field(default_factory=dict)
    anomalies: List[Anomaly] = field(default_factory=list)
    summary: str = ""


# ============================================================================
# 指标采集器
# ============================================================================

class MetricsCollector:
    """收集和存储时序指标数据，支持滑动窗口聚合"""

    DEFAULT_TTL_SECONDS = 3600

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._metrics: Dict[str, Deque[MetricPoint]] = {}
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._lock = threading.RLock()

    def record(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录一个指标点"""
        with self._lock:
            if metric_name not in self._metrics:
                self._metrics[metric_name] = deque()
            point = MetricPoint(
                timestamp=time.time(),
                metric_name=metric_name,
                value=value,
                tags=tags or {},
                metadata=metadata or {},
            )
            self._metrics[metric_name].append(point)
            self._cleanup_old(metric_name)

    def increment(self, metric_name: str, delta: float = 1.0) -> None:
        """递增计数器"""
        with self._lock:
            self._counters[metric_name] = self._counters.get(metric_name, 0) + delta

    def gauge(self, metric_name: str, value: float) -> None:
        """设置仪表值"""
        with self._lock:
            self._gauges[metric_name] = value

    def get_recent(self, metric_name: str, seconds: int = 300) -> List[MetricPoint]:
        """获取最近N秒的指标数据"""
        with self._lock:
            cutoff = time.time() - seconds
            if metric_name not in self._metrics:
                return []
            return [
                p for p in self._metrics[metric_name]
                if p.timestamp >= cutoff
            ]

    def get_avg(self, metric_name: str, seconds: int = 300) -> float:
        """获取最近N秒的平均值"""
        points = self.get_recent(metric_name, seconds)
        if not points:
            return 0.0
        return sum(p.value for p in points) / len(points)

    def get_max(self, metric_name: str, seconds: int = 300) -> float:
        """获取最近N秒的最大值"""
        points = self.get_recent(metric_name, seconds)
        if not points:
            return 0.0
        return max(p.value for p in points)

    def get_rate(self, metric_name: str, seconds: int = 60) -> float:
        """获取最近N秒的速率"""
        points = self.get_recent(metric_name, seconds)
        if len(points) < 2:
            return 0.0
        time_span = points[-1].timestamp - points[0].timestamp
        if time_span <= 0:
            return 0.0
        return sum(p.value for p in points) / time_span

    def get_counter(self, metric_name: str) -> float:
        """获取计数器当前值"""
        with self._lock:
            return self._counters.get(metric_name, 0.0)

    def get_gauge(self, metric_name: str) -> float:
        """获取仪表当前值"""
        with self._lock:
            return self._gauges.get(metric_name, 0.0)

    def _cleanup_old(self, metric_name: str) -> None:
        cutoff = time.time() - self._ttl
        queue = self._metrics[metric_name]
        while queue and queue[0].timestamp < cutoff:
            queue.popleft()

    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标的摘要"""
        with self._lock:
            return {
                "metric_count": sum(len(q) for q in self._metrics.values()),
                "unique_metrics": list(self._metrics.keys()),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
            }

    def reset(self) -> None:
        """重置所有指标"""
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()


# ============================================================================
# 异常检测器
# ============================================================================

@dataclass
class AnomalyThreshold:
    """异常检测阈值配置"""
    metric_name: str
    threshold_type: str = "value"
    threshold_value: float = 0.0
    comparison: str = "gt"
    window_seconds: int = 300
    severity: str = "medium"
    cooldown_seconds: int = 60


class AnomalyDetector:
    """基于配置的阈值检测异常行为"""

    DEFAULT_THRESHOLDS: List[AnomalyThreshold] = []

    def __init__(
        self,
        thresholds: Optional[List[AnomalyThreshold]] = None,
        custom_rules: Optional[List[Callable]] = None,
    ):
        self._thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()
        self._custom_rules = custom_rules or []
        self._cooldowns: Dict[str, float] = {}
        self._lock = threading.RLock()

    def detect(self, metrics: MetricsCollector) -> List[Anomaly]:
        """检测异常"""
        anomalies: List[Anomaly] = []
        now = time.time()

        with self._lock:
            for threshold in self._thresholds:
                cooldown_key = f"{threshold.metric_name}:{threshold.severity}"
                last_triggered = self._cooldowns.get(cooldown_key, 0)
                if now - last_triggered < threshold.cooldown_seconds:
                    continue

                value = metrics.get_avg(threshold.metric_name, threshold.window_seconds)
                if self._compare(value, threshold.comparison, threshold.threshold_value):
                    anomaly = self._create_anomaly(threshold, value, now)
                    anomalies.append(anomaly)
                    self._cooldowns[cooldown_key] = now

            for rule in self._custom_rules:
                try:
                    anomaly = rule(metrics)
                    if anomaly:
                        anomalies.append(anomaly)
                except Exception as e:
                    logger.warning(f"Custom anomaly rule failed: {e}")

        return anomalies

    @staticmethod
    def _compare(value: float, comparison: str, threshold: float) -> bool:
        if comparison == "gt":
            return value > threshold
        elif comparison == "lt":
            return value < threshold
        elif comparison == "gte":
            return value >= threshold
        elif comparison == "lte":
            return value <= threshold
        elif comparison == "eq":
            return abs(value - threshold) < 1e-6
        return False

    @staticmethod
    def _create_anomaly(threshold: AnomalyThreshold, current_value: float, now: float) -> Anomaly:
        return Anomaly(
            anomaly_type=AnomalyType.ERROR_RATE_HIGH,
            severity=threshold.severity,
            message=f"{threshold.metric_name} = {current_value:.2f} (threshold: {threshold.threshold_value})",
            timestamp=now,
            metric_name=threshold.metric_name,
            current_value=current_value,
            threshold=threshold.threshold_value,
        )


# ============================================================================
# 健康检查器
# ============================================================================

@dataclass
class HealthCheck:
    """健康检查项"""
    name: str
    check_fn: Callable[[None], Tuple[bool, str]]
    required: bool = True


class HealthChecker:
    """执行定期健康检查"""

    def __init__(self):
        self._checks: List[HealthCheck] = []
        self._last_results: Dict[str, Tuple[bool, str]] = {}
        self._lock = threading.RLock()

    def register(self, name: str, check_fn: Callable[[None], Tuple[bool, str]], required: bool = True) -> None:
        """注册健康检查项"""
        with self._lock:
            self._checks.append(HealthCheck(name=name, check_fn=check_fn, required=required))

    def check_all(self) -> HealthReport:
        """执行所有健康检查"""
        checks_results: Dict[str, Any] = {}
        anomalies: List[Anomaly] = []
        now = time.time()

        with self._lock:
            for check in self._checks:
                try:
                    is_healthy, message = check.check_fn()
                    checks_results[check.name] = {
                        "healthy": is_healthy,
                        "message": message,
                        "required": check.required,
                    }
                    if not is_healthy and check.required:
                        anomalies.append(Anomaly(
                            anomaly_type=AnomalyType.ERROR_RATE_HIGH,
                            severity="high",
                            message=f"Health check failed: {check.name} - {message}",
                            timestamp=now,
                            metric_name=check.name,
                            current_value=0.0,
                            threshold=0.0,
                        ))
                    self._last_results[check.name] = (is_healthy, message)
                except Exception as e:
                    checks_results[check.name] = {
                        "healthy": False,
                        "message": f"Check error: {str(e)}",
                        "required": check.required,
                    }
                    self._last_results[check.name] = (False, str(e))

        status = self._compute_status(checks_results)
        return HealthReport(
            status=status,
            timestamp=now,
            checks=checks_results,
            anomalies=anomalies,
            summary=f"Health: {status.value} | {len(anomalies)} anomalies | {len(checks_results)} checks",
        )

    @staticmethod
    def _compute_status(results: Dict[str, Any]) -> HealthStatus:
        if not results:
            return HealthStatus.UNKNOWN
        required_unhealthy = 0
        for c in results.values():
            if not c.get("healthy", True) and c.get("required", True):
                required_unhealthy += 1
        if required_unhealthy > 0:
            return HealthStatus.CRITICAL
        return HealthStatus.HEALTHY


# ============================================================================
# 监控环 - 整合所有组件
# ============================================================================

class MonitorCollector:
    """监控环核心: 指标采集 + 异常检测 + 健康检查"""

    def __init__(self, name: str = "default"):
        self.name = name
        self.metrics = MetricsCollector()
        self.detector = AnomalyDetector()
        self.health = HealthChecker()

    def observe(self) -> Dict[str, Any]:
        """采集当前快照"""
        return {
            "name": self.name,
            "timestamp": time.time(),
            "metrics": self.metrics.get_all_metrics(),
            "status": self.status,
        }

    def detect_anomalies(self, snapshot: Optional[Dict[str, Any]] = None) -> List[Anomaly]:
        """检测异常"""
        return self.detector.detect(self.metrics)

    @property
    def status(self) -> str:
        """当前状态"""
        return "healthy"

    def quick_check(self) -> HealthReport:
        """快速健康检查（不需要注册额外的check）"""
        anomalies = self.detect_anomalies()
        now = time.time()
        severity = "critical" if len(anomalies) > 0 else "healthy"
        return HealthReport(
            status=HealthStatus.CRITICAL if anomalies else HealthStatus.HEALTHY,
            timestamp=now,
            checks={"monitor_collector": {"healthy": len(anomalies) == 0, "message": f"{len(anomalies)} anomalies"}},
            anomalies=anomalies,
            summary=f"[{severity}] {len(anomalies)} anomalies detected",
        )


# ============================================================================
# 全局单例
# ============================================================================

_global_collector: Optional[MonitorCollector] = None
_lock = threading.RLock()


def get_monitor() -> MonitorCollector:
    """获取全局 MonitorCollector 单例"""
    global _global_collector
    if _global_collector is None:
        with _lock:
            if _global_collector is None:
                _global_collector = MonitorCollector("mimir_aether")
    return _global_collector


def reset_monitor() -> None:
    """重置全局监控器（用于测试）"""
    global _global_collector
    with _lock:
        _global_collector = None
