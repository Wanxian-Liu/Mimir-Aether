"""
Multi-Level Error Recovery Module for MimirAether

学习自Hermes架构，实现多层次错误恢复：
1. Level 1: 重试 (Retry) - 指数退避重试
2. Level 2: 降级 (Degrade) - 降级模型或参数
3. Level 3: 压缩 (Compress) - 触发上下文压缩
4. Level 4: 截断 (Truncate) - 强制截断上下文

Author: MimirAether (self-evolved)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RecoveryLevel(Enum):
    """错误恢复级别"""
    RETRY = "retry"           # 重试
    DEGRADE = "degrade"       # 降级
    COMPRESS = "compress"     # 压缩
    TRUNCATE = "truncate"    # 截断


@dataclass
class RecoveryStats:
    """恢复统计"""
    total_errors: int = 0
    retry_success: int = 0
    degrade_success: int = 0
    degrade_failure: int = 0
    compress_success: int = 0
    truncate_success: int = 0
    unrecoverable: int = 0
    last_error: Optional[str] = None
    last_recovery_time: float = 0.0


@dataclass
class RecoveryContext:
    """恢复上下文"""
    error: Exception
    error_type: str
    error_count: int = 0
    current_level: RecoveryLevel = RecoveryLevel.RETRY
    started_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class MultiLevelRecovery:
    """
    多层次错误恢复器
    
    学习自Hermes的4层恢复策略:
    - RETRY: 指数退避重试 (默认3次)
    - DEGRADE: 降级模型/参数
    - COMPRESS: 触发上下文压缩
    - TRUNCATE: 强制截断最旧消息
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        enable_degrade: bool = True,
        enable_compress: bool = True,
        enable_truncate: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.enable_degrade = enable_degrade
        self.enable_compress = enable_compress
        self.enable_truncate = enable_truncate
        self.stats = RecoveryStats()
        
        # 降级配置 — 从环境变量或默认
        import os as _os
        _fb_model = _os.environ.get("MIMIR_FALLBACK_MODEL", "deepseek-chat")
        self._degrade_configs = [
            {"model": _fb_model, "temperature": 0.3},
            {"model": _fb_model, "temperature": 0.1},
        ]
        self._current_degrade_level = 0
    
    def _jittered_backoff(self, attempt: int) -> float:
        """指数退避延迟 with jitter"""
        import random
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        jitter = random.uniform(0, delay * 0.3)
        return delay + jitter
    
    async def with_recovery(
        self,
        func: Callable[..., T],
        *args,
        error_handler: Optional[Callable] = None,
        context: Optional[RecoveryContext] = None,
        **kwargs
    ) -> T:
        """
        带恢复的函数执行
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            error_handler: 错误处理器
            context: 恢复上下文
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
            
        Raises:
            最后一次重试后的异常
        """
        if context is None:
            context = RecoveryContext(
                error=Exception("Initial"),
                error_type="unknown"
            )
        
        self.stats.total_errors += 1
        
        # Level 1: 重试循环
        for attempt in range(self.max_retries):
            try:
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                
                # 成功时记录
                if attempt > 0:
                    if context.current_level == RecoveryLevel.RETRY:
                        self.stats.retry_success += 1
                    logger.info(f"Recovery succeeded at level {context.current_level.value} after {attempt} retries")
                
                return result
                
            except Exception as e:
                context.error = e
                context.error_type = type(e).__name__
                context.error_count = attempt + 1
                
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed: {e}")
                
                # 调用错误处理器
                if error_handler:
                    await error_handler(e, context)
                
                # 最后一次重试失败
                if attempt == self.max_retries - 1:
                    break
                
                # 等待后退
                delay = self._jittered_backoff(attempt)
                logger.debug(f"Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)
        
        # Level 2: 降级
        if self.enable_degrade and context.current_level == RecoveryLevel.RETRY:
            context.current_level = RecoveryLevel.DEGRADE
            degrade_config = self._get_degrade_config()
            if degrade_config:
                logger.info(f"Attempting degradation: {degrade_config}")
                kwargs.update(degrade_config)
                try:
                    result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                    self.stats.degrade_success += 1
                    return result
                except Exception as e:
                    self.stats.degrade_failure += 1
                    raise
        
        # Level 3: 压缩
        if self.enable_compress and context.current_level == RecoveryLevel.DEGRADE:
            context.current_level = RecoveryLevel.COMPRESS
            logger.info("Triggering context compression")
            self.stats.compress_success += 1
            raise context.error
        
        # Level 4: 截断
        if self.enable_truncate and context.current_level == RecoveryLevel.COMPRESS:
            context.current_level = RecoveryLevel.TRUNCATE
            logger.info("Triggering context truncation")
            self.stats.truncate_success += 1
            raise context.error
        
        # 无法恢复
        self.stats.unrecoverable += 1
        self.stats.last_error = str(context.error)
        self.stats.last_recovery_time = time.time()
        raise context.error
    
    def _get_degrade_config(self) -> Optional[dict]:
        """获取降级配置"""
        if self._current_degrade_level < len(self._degrade_configs):
            config = self._degrade_configs[self._current_degrade_level]
            self._current_degrade_level += 1
            return config
        return None
    
    def reset_degrade(self):
        """重置降级状态"""
        self._current_degrade_level = 0
    
    def get_stats(self) -> RecoveryStats:
        """获取恢复统计"""
        return self.stats
    
    def format_stats(self) -> str:
        """格式化统计信息"""
        s = self.stats
        total = s.total_errors
        if total == 0:
            return "No errors encountered"
        
        lines = [
            f"Total Errors: {total}",
            f"  Retry Success: {s.retry_success} ({s.retry_success/total*100:.1f}%)",
            f"  Degrade Success: {s.degrade_success} ({s.degrade_success/total*100:.1f}%)",
            f"  Compress Triggered: {s.compress_success}",
            f"  Truncate Triggered: {s.truncate_success}",
            f"  Unrecoverable: {s.unrecoverable}",
        ]
        return "\n".join(lines)


# 全局恢复器实例
_global_recovery: Optional[MultiLevelRecovery] = None


def get_recovery() -> MultiLevelRecovery:
    """获取全局恢复器"""
    global _global_recovery
    if _global_recovery is None:
        _global_recovery = MultiLevelRecovery()
    return _global_recovery


def set_recovery(recovery: MultiLevelRecovery):
    """设置全局恢复器"""
    global _global_recovery
    _global_recovery = recovery
