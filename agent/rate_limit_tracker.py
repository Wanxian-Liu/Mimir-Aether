"""
MimirAether Rate Limit Tracker

学习自Hermes rate_limit_tracker设计。

核心功能：
- 追踪API速率限制状态
- 解析x-ratelimit-*响应头
- 智能退避计算
- 格式化显示
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class RateLimitBucket:
    """单个速率限制窗口（如每分钟请求数）"""
    
    limit: int = 0           # 总量
    remaining: int = 0       # 剩余
    reset_seconds: float = 0.0  # 距离重置的秒数
    captured_at: float = 0.0    # 记录时间
    
    @property
    def used(self) -> int:
        """已使用数量"""
        return max(0, self.limit - self.remaining)
    
    @property
    def usage_pct(self) -> float:
        """使用百分比"""
        if self.limit <= 0:
            return 0.0
        return (self.used / self.limit) * 100.0
    
    @property
    def remaining_seconds_now(self) -> float:
        """距离重置的剩余秒数"""
        elapsed = time.time() - self.captured_at
        return max(0.0, self.reset_seconds - elapsed)


@dataclass
class RateLimitState:
    """完整的速率限制状态"""
    
    requests_min: RateLimitBucket = field(default_factory=RateLimitBucket)
    requests_hour: RateLimitBucket = field(default_factory=RateLimitBucket)
    tokens_min: RateLimitBucket = field(default_factory=RateLimitBucket)
    tokens_hour: RateLimitBucket = field(default_factory=RateLimitBucket)
    captured_at: float = 0.0
    provider: str = ""
    
    @property
    def has_data(self) -> bool:
        return self.captured_at > 0
    
    @property
    def age_seconds(self) -> float:
        if not self.has_data:
            return float("inf")
        return time.time() - self.captured_at


# ============================================================================
# 解析函数
# ============================================================================

def _safe_int(value: Any, default: int = 0) -> int:
    """安全转换为整数"""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为浮点数"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_rate_limit_headers(
    headers: Mapping[str, str],
    provider: str = "",
) -> Optional[RateLimitState]:
    """
    从响应头解析x-ratelimit-*信息
    
    Returns:
        RateLimitState如果找到速率限制头，否则返回None
    """
    # 转换为小写（HTTP头不区分大小写）
    lowered = {k.lower(): v for k, v in headers.items()}
    
    # 快速检查：至少要有一个速率限制头
    has_any = any(k.startswith("x-ratelimit-") for k in lowered)
    if not has_any:
        return None
    
    now = time.time()
    
    def _bucket(resource: str, suffix: str = "") -> RateLimitBucket:
        # resource="requests", suffix="" -> 每分钟
        # resource="tokens", suffix="-1h" -> 每小时
        tag = f"{resource}{suffix}"
        return RateLimitBucket(
            limit=_safe_int(lowered.get(f"x-ratelimit-limit-{tag}")),
            remaining=_safe_int(lowered.get(f"x-ratelimit-remaining-{tag}")),
            reset_seconds=_safe_float(lowered.get(f"x-ratelimit-reset-{tag}")),
            captured_at=now,
        )
    
    return RateLimitState(
        requests_min=_bucket("requests"),
        requests_hour=_bucket("requests", "-1h"),
        tokens_min=_bucket("tokens"),
        tokens_hour=_bucket("tokens", "-1h"),
        captured_at=now,
        provider=provider,
    )


# ============================================================================
# 格式化显示
# ============================================================================

def _fmt_count(n: int) -> str:
    """人类友好的数字格式: 7999856 -> '8.0M', 33599 -> '33.6K'"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}K"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_seconds(seconds: float) -> str:
    """秒数转换为人类友好格式: 58s, 2m 14s, 58m 57s"""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        m, sec = divmod(s, 60)
        return f"{m}m {sec}s" if sec else f"{m}m"
    h, remainder = divmod(s, 3600)
    m = remainder // 60
    return f"{h}h {m}m" if m else f"{h}h"


def _bar(pct: float, width: int = 20) -> str:
    """ASCII进度条: [████████░░░░░░░░░░░░] 40%"""
    filled = int(pct / 100.0 * width)
    filled = max(0, min(width, filled))
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"


def _bucket_line(label: str, bucket: RateLimitBucket, label_width: int = 14) -> str:
    """格式化单个bucket为一行"""
    if bucket.limit <= 0:
        return f"  {label:<{label_width}}  (no data)"
    
    pct = bucket.usage_pct
    used = _fmt_count(bucket.used)
    limit = _fmt_count(bucket.limit)
    remaining = _fmt_count(bucket.remaining)
    reset = _fmt_seconds(bucket.remaining_seconds_now)
    
    bar = _bar(pct)
    return f"  {label:<{label_width}} {bar} {pct:5.1f}%  {used}/{limit} used  ({remaining} left, resets in {reset})"


def format_rate_limit_display(state: RateLimitState) -> str:
    """格式化速率限制状态用于显示"""
    if not state.has_data:
        return "No rate limit data yet — make an API request first."
    
    age = state.age_seconds
    if age < 5:
        freshness = "just now"
    elif age < 60:
        freshness = f"{int(age)}s ago"
    else:
        freshness = f"{_fmt_seconds(age)} ago"
    
    provider_label = state.provider.title() if state.provider else "Provider"
    
    lines = [
        f"{provider_label} Rate Limits (captured {freshness}):",
        "",
        _bucket_line("Requests/min", state.requests_min),
        _bucket_line("Requests/hour", state.requests_hour),
        _bucket_line("Tokens/min", state.tokens_min),
        _bucket_line("Tokens/hour", state.tokens_hour),
    ]
    
    return "\n".join(lines)


def format_rate_limit_compact(state: RateLimitState) -> str:
    """单行紧凑摘要，用于状态栏/网关消息（Hermès兼容）"""
    if not state.has_data:
        return "No rate limit data."

    rm = state.requests_min
    tm = state.tokens_min
    rh = state.requests_hour
    th = state.tokens_hour

    parts = []
    if rm.limit > 0:
        parts.append(f"RPM: {rm.remaining}/{rm.limit}")
    if rh.limit > 0:
        parts.append(f"RPH: {_fmt_count(rh.remaining)}/{_fmt_count(rh.limit)} (resets {_fmt_seconds(rh.remaining_seconds_now)})")
    if tm.limit > 0:
        parts.append(f"TPM: {_fmt_count(tm.remaining)}/{_fmt_count(tm.limit)}")
    if th.limit > 0:
        parts.append(f"TPH: {_fmt_count(th.remaining)}/{_fmt_count(th.limit)} (resets {_fmt_seconds(th.remaining_seconds_now)})")

    return "; ".join(parts) if parts else "No rate limit data."


# ============================================================================
# 速率限制追踪器
# ============================================================================

class RateLimitTracker:
    """
    速率限制追踪器
    
    追踪各provider的速率限制状态，实现智能退避
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._states: Dict[str, RateLimitState] = {}
        self._backoff_count: Dict[str, int] = {}
        self._base_backoff: float = 1.0
        self._max_backoff: float = 60.0
    
    def update_from_response(
        self,
        provider: str,
        headers: Mapping[str, str],
    ) -> Optional[RateLimitState]:
        """
        从API响应更新速率限制状态
        
        Args:
            provider: provider名称
            headers: API响应头
            
        Returns:
            RateLimitState如果找到速率限制信息
        """
        state = parse_rate_limit_headers(headers, provider)
        with self._lock:
            if state:
                self._states[provider] = state
                self._backoff_count.pop(provider, None)
        return state
    
    def should_wait(self, provider: str) -> bool:
        """
        判断是否应该等待（避免触发限流）
        
        检查当前使用率，如果超过80%则应该等待
        """
        with self._lock:
            state = self._states.get(provider)
            if not state or not state.has_data:
                return False
            
            for bucket in [state.requests_min, state.requests_hour, 
                           state.tokens_min, state.tokens_hour]:
                if bucket.limit > 0:
                    usage_pct = bucket.usage_pct
                    if usage_pct >= 80:
                        return True
        return False
    
    def get_wait_time(self, provider: str) -> float:
        """
        获取应等待的秒数
        
        基于当前速率限制状态和退避计数计算
        """
        with self._lock:
            state = self._states.get(provider)
            backoff_count = self._backoff_count.get(provider, 0)
            backoff = min(self._base_backoff * (2 ** backoff_count), self._max_backoff)
            
            if not state or not state.has_data:
                return backoff
            
            min_wait = float('inf')
            for bucket in [state.requests_min, state.requests_hour,
                           state.tokens_min, state.tokens_hour]:
                if bucket.reset_seconds > 0:
                    remaining = bucket.remaining_seconds_now
                    if remaining > 0 and remaining < min_wait:
                        min_wait = remaining
            
            if min_wait == float('inf'):
                min_wait = 0.0
            
            return max(min_wait, backoff)
    
    def record_hit(self, provider: str, status_code: int) -> None:
        """
        记录一次限流命中
        
        当收到429时调用，增加退避计数
        """
        if status_code == 429:
            with self._lock:
                count = self._backoff_count.get(provider, 0) + 1
                self._backoff_count[provider] = count
    
    def get_state(self, provider: str) -> Optional[RateLimitState]:
        """获取指定provider的速率限制状态"""
        with self._lock:
            return self._states.get(provider)
    
    def clear(self, provider: str = None) -> None:
        """清除速率限制状态"""
        with self._lock:
            if provider:
                self._states.pop(provider, None)
                self._backoff_count.pop(provider, None)
            else:
                self._states.clear()
                self._backoff_count.clear()


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Rate Limit Tracker 测试")
    print("=" * 60)
    
    # 测试1: 解析速率限制头
    print("\n[测试1] 解析速率限制头")
    headers = {
        "x-ratelimit-limit-requests": "60",
        "x-ratelimit-remaining-requests": "45",
        "x-ratelimit-reset-requests": "30",
        "x-ratelimit-limit-tokens": "100000",
        "x-ratelimit-remaining-tokens": "85000",
        "x-ratelimit-reset-tokens": "45",
    }
    state = parse_rate_limit_headers(headers, "openai")
    if state:
        print(f"  provider: {state.provider}")
        print(f"  requests_min: limit={state.requests_min.limit}, remaining={state.requests_min.remaining}")
        print(f"  tokens_min: limit={state.tokens_min.limit}, remaining={state.tokens_min.remaining}")
        print(f"  usage_pct: {state.tokens_min.usage_pct:.1f}%")
        print("  ✅ 通过")
    else:
        print("  ❌ 解析失败")
    
    # 测试2: 格式化显示
    print("\n[测试2] 格式化显示")
    if state:
        display = format_rate_limit_display(state)
        print(display)
        print("  ✅ 通过")
    
    # 测试3: RateLimitTracker
    print("\n[测试3] RateLimitTracker")
    tracker = RateLimitTracker()
    
    # 更新状态
    tracker.update_from_response("openai", headers)
    
    # 检查是否应等待
    should_wait = tracker.should_wait("openai")
    print(f"  should_wait (45/60 remaining): {should_wait}")
    
    # 模拟高使用率
    high_usage_headers = {
        "x-ratelimit-limit-requests": "60",
        "x-ratelimit-remaining-requests": "5",
        "x-ratelimit-reset-requests": "30",
        "x-ratelimit-limit-tokens": "100000",
        "x-ratelimit-remaining-tokens": "5000",
        "x-ratelimit-reset-tokens": "45",
    }
    tracker.update_from_response("openai", high_usage_headers)
    should_wait_high = tracker.should_wait("openai")
    print(f"  should_wait (5/60 remaining): {should_wait_high}")
    assert should_wait_high == True, "高使用率时应等待"
    print("  ✅ 通过")
    
    # 测试4: 退避计数
    print("\n[测试4] 退避计数")
    tracker.record_hit("openai", 429)  # 第一次429
    tracker.record_hit("openai", 429)  # 第二次429
    wait_time = tracker.get_wait_time("openai")
    print(f"  wait_time after 2 hits: {wait_time:.1f}s")
    assert wait_time >= 4.0, "2次命中后应该等待至少4秒"
    print("  ✅ 通过")
    
    # 测试5: 清除状态
    print("\n[测试5] 清除状态")
    tracker.clear("openai")
    state_after_clear = tracker.get_state("openai")
    print(f"  state after clear: {state_after_clear}")
    assert state_after_clear is None, "清除后状态应为None"
    print("  ✅ 通过")
    
    # 测试6: 无速率限制头
    print("\n[测试6] 无速率限制头")
    empty_headers = {"content-type": "application/json"}
    no_limit_state = parse_rate_limit_headers(empty_headers, "test")
    print(f"  result: {no_limit_state}")
    assert no_limit_state is None, "无速率限制头时应返回None"
    print("  ✅ 通过")
    
    # 测试7: display无数据
    print("\n[测试7] 无数据显示")
    empty_tracker = RateLimitTracker()
    display_empty = format_rate_limit_display(RateLimitState())
    print(f"  display: {display_empty}")
    assert "No rate limit data" in display_empty
    print("  ✅ 通过")
    
    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)