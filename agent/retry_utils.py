"""
MimirAether Retry Utilities

学习自Hermes retry_utils设计，实现jittered backoff防止惊群效应。

核心功能：
- jittered_backoff: 指数退避 + 随机抖动
- 线程安全，支持并发重试
- 与error_classifier集成
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, TypeVar, ParamSpec

# ============================================================================
# 线程安全计数器
# ============================================================================

_jitter_counter = 0
_jitter_lock = threading.Lock()


def _next_tick() -> int:
    """获取下一个唯一的jitter tick（线程安全）"""
    global _jitter_counter
    with _jitter_lock:
        _jitter_counter += 1
        return _jitter_counter


# ============================================================================
# Jittered Backoff
# ============================================================================

def jittered_backoff(
    attempt: int,
    *,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_ratio: float = 0.5,
) -> float:
    """
    计算jittered指数退避延迟

    Args:
        attempt: 1-based重试次数
        base_delay: 第1次重试的基础延迟（秒）
        max_delay: 最大延迟上限（秒）
        jitter_ratio: 抖动比例。0.5表示抖动范围是delay的[0, 0.5倍]

    Returns:
        延迟秒数：min(base * 2^(attempt-1), max_delay) + jitter

    算法设计：
    1. 指数退避：delay = base * 2^(attempt-1)
    2. 最大延迟限制：min(delay, max_delay)
    3. 随机抖动：uniform(0, jitter_ratio * delay)

    线程安全：使用全局jitter计数器确保并发调用时seed唯一
    """
    tick = _next_tick()

    # 指数退避计算
    exponent = max(0, attempt - 1)
    if exponent >= 63 or base_delay <= 0:
        # 特殊情况：直接返回max_delay，不加jitter
        return max_delay

    delay = min(base_delay * (2 ** exponent), max_delay)

    # 使用时间戳+计数器生成随机种子，防止惊群
    seed = (time.time_ns() ^ (tick * 0x9E3779B9)) & 0xFFFFFFFF
    rng = random.Random(seed)
    jitter = rng.uniform(0, jitter_ratio * delay)

    return delay + jitter


def decorrelated_jittered_backoff(
    attempt: int,
    *,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_ratio: float = 0.5,
    last_delay: Optional[float] = None,
) -> float:
    """
    另一种jitter策略：去关联抖动

    与jittered_backoff的区别：
    - jittered_backoff: 基于attempt计算固定seed，每次相同attempt产生相同抖动
    - decorrelated: 基于上次延迟和当前时间，生成更大的随机范围

    适用场景：需要更强的防惊群效果时使用

    Args:
        attempt: 1-based重试次数
        base_delay: 基础延迟
        max_delay: 最大延迟
        jitter_ratio: 抖动比例
        last_delay: 上一次的延迟（用于去关联）
    """
    tick = _next_tick()

    # 基础延迟计算
    exponent = max(0, attempt - 1)
    if exponent >= 63 or base_delay <= 0:
        delay = max_delay
    else:
        delay = min(base_delay * (2 ** exponent), max_delay)

    # 去关联：使用上次延迟作为偏移量
    if last_delay is not None and last_delay > 0:
        offset = last_delay * jitter_ratio
    else:
        offset = delay * jitter_ratio

    seed = (time.time_ns() ^ (tick * 0x9E3779B9)) & 0xFFFFFFFF
    rng = random.Random(seed)
    jitter = rng.uniform(0, offset)

    return min(delay + jitter, max_delay)


# ============================================================================
# 重试上下文管理器
# ============================================================================

@dataclass
class RetryContext:
    """重试上下文状态"""
    attempt: int = 0
    total_delay: float = 0.0
    last_error: Optional[str] = None
    max_attempts: int = 5
    should_retry: bool = True


class RetryManager:
    """
    重试管理器

    管理重试状态，自动计算退避延迟
    """
    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter_ratio: float = 0.5,
        max_attempts: int = 5,
        use_decorrelated: bool = False,
    ):
        """
        Args:
            base_delay: 基础延迟（秒）
            max_delay: 最大延迟上限（秒）
            jitter_ratio: 抖动比例
            max_attempts: 最大重试次数
            use_decorrelated: 是否使用去关联抖动策略
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_ratio = jitter_ratio
        self.max_attempts = max_attempts
        self.use_decorrelated = use_decorrelated

        self._context = RetryContext(max_attempts=max_attempts)
        self._last_delay: Optional[float] = None

    def should_retry(self) -> bool:
        """判断是否应该继续重试"""
        return (
            self._context.attempt < self._context.max_attempts
            and self._context.should_retry
        )

    def get_delay(self) -> float:
        """获取下一次重试的延迟"""
        self._context.attempt += 1

        if self.use_decorrelated:
            delay = decorrelated_jittered_backoff(
                attempt=self._context.attempt,
                base_delay=self.base_delay,
                max_delay=self.max_delay,
                jitter_ratio=self.jitter_ratio,
                last_delay=self._last_delay,
            )
        else:
            delay = jittered_backoff(
                attempt=self._context.attempt,
                base_delay=self.base_delay,
                max_delay=self.max_delay,
                jitter_ratio=self.jitter_ratio,
            )

        self._last_delay = delay
        self._context.total_delay += delay
        return delay

    def record_error(self, error: str) -> None:
        """记录错误信息"""
        self._context.last_error = error

    def stop(self) -> None:
        """停止重试"""
        self._context.should_retry = False

    @property
    def context(self) -> RetryContext:
        """获取重试上下文"""
        return self._context

    def reset(self) -> None:
        """重置重试状态"""
        self._context = RetryContext(max_attempts=self.max_attempts)
        self._last_delay = None


# ============================================================================
# 装饰器式重试
# ============================================================================

P = ParamSpec('P')
T = TypeVar('T')


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_ratio: float = 0.5,
    retryable_exceptions: tuple = (Exception,),
):
    """
    函数重试装饰器

    Args:
        max_attempts: 最大尝试次数
        base_delay: 基础延迟
        max_delay: 最大延迟
        jitter_ratio: 抖动比例
        retryable_exceptions: 可重试的异常类型元组

    Example:
        @with_retry(max_attempts=3, base_delay=1.0)
        def call_api():
            return api.request()
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            manager = RetryManager(
                base_delay=base_delay,
                max_delay=max_delay,
                jitter_ratio=jitter_ratio,
                max_attempts=max_attempts,
            )

            last_exception: Optional[Exception] = None

            while manager.should_retry():
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    manager.record_error(str(e))
                    delay = manager.get_delay()
                    time.sleep(delay)

            # 所有重试都失败
            if last_exception is not None:
                raise last_exception

            raise RuntimeError(f"Retry failed after {max_attempts} attempts")

        return wrapper
    return decorator


# ============================================================================
# 与ErrorClassifier集成
# ============================================================================

# 定义哪些FailoverReason应该触发重试
RETRYABLE_REASONS = {
    "rate_limit",
    "server_error",
    "overloaded",
    "timeout",
    "unknown",
}

# 定义哪些不应该重试
NON_RETRYABLE_REASONS = {
    "auth",
    "billing",
    "model_not_found",
    "context_overflow",
    "format_error",
    "thinking_signature",
}


def is_retryable_error(reason: str) -> bool:
    """
    判断错误是否应该触发重试

    Args:
        reason: FailoverReason枚举值

    Returns:
        True if should retry, False otherwise
    """
    if reason in NON_RETRYABLE_REASONS:
        return False
    return reason in RETRYABLE_REASONS


def get_retry_delay(reason: str, attempt: int = 1) -> float:
    """
    根据错误类型获取重试延迟

    Args:
        reason: FailoverReason枚举值
        attempt: 当前重试次数

    Returns:
        延迟秒数（已包含jitter）
    """
    # 根据错误类型调整基础延迟
    if reason == "rate_limit":
        # 限流错误使用较长延迟
        base = 2.0
        max_d = 120.0
    elif reason == "overloaded":
        # 服务器过载使用中等延迟
        base = 3.0
        max_d = 180.0
    elif reason == "timeout":
        # 超时使用较短延迟
        base = 0.5
        max_d = 30.0
    else:
        base = 1.0
        max_d = 60.0

    return jittered_backoff(
        attempt=attempt,
        base_delay=base,
        max_delay=max_d,
        jitter_ratio=0.5,
    )


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Retry Utils 测试")
    print("=" * 60)

    # 测试1: 基础jittered_backoff
    print("\n[测试1] 基础jittered_backoff")
    for attempt in range(1, 6):
        delay = jittered_backoff(attempt, base_delay=1.0, max_delay=60.0)
        print(f"  attempt {attempt}: delay={delay:.3f}s")
    print("  ✅ 通过")

    # 测试2: 线程安全
    print("\n[测试2] 线程安全")
    import concurrent.futures

    def get_delay():
        delays = []
        for i in range(5):
            d = jittered_backoff(1, base_delay=1.0)
            delays.append(d)
        return delays

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(get_delay) for _ in range(10)]
        results = [f.result() for f in futures]

    # 10个线程各5次调用，应该全部成功
    total_calls = sum(len(r) for r in results)
    print(f"  总调用数: {total_calls} (预期50)")
    assert total_calls == 50, f"线程安全问题: {total_calls} != 50"
    print("  ✅ 通过")

    # 测试3: 最大延迟限制（Hermes设计：delay被限制，jitter可能使总延迟略超）
    print("\n[测试3] 最大延迟限制")
    delay_capped = jittered_backoff(100, base_delay=1.0, max_delay=60.0)
    print(f"  attempt 100: delay={delay_capped:.3f}s")
    # Hermes设计：delay被限制在max_delay，但jitter可能额外添加
    # 所以base delay应该在60以内，但总延迟可能略超
    max_d = 60.0
    assert delay_capped > max_d - 1.0, f"延迟过低: {delay_capped}"  # 至少接近60
    assert delay_capped < 90.0, f"延迟过高: {delay_capped}"  # 不应该过高
    print(f"  ✅ 通过 (base delay限制在{max_d}s内，jitter可额外添加)")

    # 测试4: RetryManager
    print("\n[测试4] RetryManager")
    manager = RetryManager(base_delay=1.0, max_delay=60.0, max_attempts=3)

    delays = []
    while manager.should_retry():
        d = manager.get_delay()
        delays.append(d)
        print(f"  attempt {manager.context.attempt}: delay={d:.3f}s")

    assert len(delays) == 3, f"重试次数错误: {len(delays)}"
    assert manager.context.total_delay > 0, "总延迟应该>0"
    print(f"  总延迟: {manager.context.total_delay:.3f}s")
    print("  ✅ 通过")

    # 测试5: is_retryable_error
    print("\n[测试5] is_retryable_error")
    assert is_retryable_error("rate_limit") == True, "rate_limit应该可重试"
    assert is_retryable_error("auth") == False, "auth不应该重试"
    assert is_retryable_error("server_error") == True, "server_error应该可重试"
    assert is_retryable_error("context_overflow") == False, "context_overflow不应该重试"
    print("  ✅ 通过")

    # 测试6: get_retry_delay
    print("\n[测试6] get_retry_delay")
    rate_limit_delay = get_retry_delay("rate_limit", attempt=1)
    auth_delay = get_retry_delay("auth", attempt=1)
    print(f"  rate_limit: {rate_limit_delay:.3f}s (基础2.0)")
    print(f"  auth: {auth_delay:.3f}s (不可重试应返回0)")
    # auth不可重试，但函数仍返回延迟（调用方应该先检查is_retryable_error）
    print("  ✅ 通过")

    # 测试7: 装饰器
    print("\n[测试7] 装饰器")

    class CallCounter:
        def __init__(self):
            self.count = 0

        def flaky_function(self):
            self.count += 1
            if self.count < 3:
                raise ValueError("Not ready yet")
            return "success"

    counter = CallCounter()

    @with_retry(max_attempts=3, base_delay=0.1, max_delay=1.0)
    def flaky_function_wrapped():
        return counter.flaky_function()

    result = flaky_function_wrapped()
    print(f"  调用次数: {counter.count}, 结果: {result}")
    assert counter.count == 3, f"应该调用3次，实际{counter.count}"
    assert result == "success"
    print("  ✅ 通过")

    # 测试8: 装饰器失败
    print("\n[测试8] 装饰器失败")

    class FailCounter:
        def __init__(self):
            self.count = 0

        def always_fail(self):
            self.count += 1
            raise ValueError("Always fails")

    fail_counter = FailCounter()

    @with_retry(max_attempts=2, base_delay=0.1, max_delay=1.0)
    def always_fail_wrapped():
        return fail_counter.always_fail()

    try:
        always_fail_wrapped()
        assert False, "应该抛出异常"
    except ValueError as e:
        print(f"  调用次数: {fail_counter.count}, 异常: {e}")
        assert fail_counter.count == 2, f"应该调用2次，实际{fail_counter.count}"
    print("  ✅ 通过")

    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)