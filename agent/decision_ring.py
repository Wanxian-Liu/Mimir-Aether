"""
DecisionRing - MimirAether 错误决策环

整合 ErrorClassifier + StrategyMatcher 的决策引擎。
将错误分类→策略匹配→执行决策的完整流程。

核心组件：
- ErrorClassifier: API错误分类
- StrategyMatcher: 策略规则匹配
- DecisionRing: 决策协调器

Author: MimirAether (self-evolved)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .error_classifier import (
    ClassifiedError,
    FailoverReason,
    classify_api_error,
)
from .strategy_matcher import (
    StrategyAction,
    StrategyContext,
    StrategyMatcher,
    StrategyResult,
    get_matcher,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 决策结果
# ============================================================================

@dataclass
class DecisionResult:
    """决策环执行结果"""
    
    # 分类信息
    classified_error: ClassifiedError
    
    # 策略信息
    strategy_result: StrategyResult
    matched_rules: List[str] = field(default_factory=list)
    
    # 建议动作
    suggested_actions: List[StrategyAction] = field(default_factory=list)
    
    # 建议参数
    suggested_provider: Optional[str] = None
    suggested_model: Optional[str] = None
    suggested_credential: Optional[str] = None
    
    # 控制参数
    backoff_seconds: float = 0.0
    should_compress: bool = False
    should_abort: bool = False
    
    # 元数据
    decision_time_ms: float = 0.0
    confidence: float = 1.0
    
    @property
    def should_retry(self) -> bool:
        """是否应该重试"""
        if self.should_abort:
            return False
        return self.classified_error.retryable
    
    @property
    def should_fallback(self) -> bool:
        """是否应该切换provider"""
        return self.classified_error.should_fallback or                StrategyAction.FALLBACK_PROVIDER in self.suggested_actions


@dataclass
class DecisionRingConfig:
    """决策环配置"""
    
    # 策略匹配器
    enable_provider_rules: bool = True
    custom_rules: Optional[List] = None
    
    # 决策选项
    max_retries: int = 3
    default_backoff_base: float = 1.0
    max_backoff: float = 60.0
    
    # 可用资源
    available_credentials: List[str] = field(default_factory=list)
    available_providers: List[str] = field(default_factory=list)
    available_models: List[str] = field(default_factory=list)
    
    # 上下文限制
    max_context_size: int = 200000

    # 1c policy (D4–D8 · IQ-EVO-43); defaults match spike
    compress_context_pressure: float = 0.85
    truncate_context_pressure: float = 0.95
    confidence_floor: float = 0.5
    cooldown_scale: float = 1.0



# ============================================================================
# 决策环核心
# ============================================================================

class DecisionRing:
    """
    错误决策环
    
    协调 ErrorClassifier 和 StrategyMatcher 的完整决策流程。
    
    流程：
    1. 接收API错误和上下文
    2. 错误分类 (ErrorClassifier)
    3. 策略匹配 (StrategyMatcher)
    4. 返回可执行决策
    
    用法:
        ring = DecisionRing(config)
        result = ring.decide(error, attempt=0, context_size=50000)
        
        if result.should_retry:
            time.sleep(result.backoff_seconds)
            # 重试逻辑
        if result.should_fallback:
            switch_provider(result.suggested_provider)
    """
    
    def __init__(self, config: Optional[DecisionRingConfig] = None):
        self.config = config or DecisionRingConfig()
        try:
            from agent.decision_compressor_policy import merge_ring_policy_into_config

            merge_ring_policy_into_config(self.config)
        except Exception:
            pass
        self._matcher = StrategyMatcher(
            custom_rules=self.config.custom_rules,
            enable_provider_rules=self.config.enable_provider_rules,
        )
        self._decision_count = 0
        
        logger.debug(
            f"DecisionRing initialized: "
            f"providers={self.config.available_providers}, "
            f"credentials={len(self.config.available_credentials)}"
        )
    
    def decide(
        self,
        error: Exception,
        *,
        provider: str = "",
        model: str = "",
        attempt: int = 0,
        context_size: int = 0,
        current_credential: str = "",
        current_provider: str = "",
        current_model: str = "",
    ) -> DecisionResult:
        """
        执行完整决策流程
        
        Args:
            error: API异常
            provider: 当前provider
            model: 当前模型
            attempt: 当前尝试次数
            context_size: 当前上下文大小
            current_credential: 当前凭证
            current_provider: 当前provider
            current_model: 当前模型
            
        Returns:
            DecisionResult: 决策结果
        """
        start_time = time.time()
        
        # 1. 错误分类
        classified = classify_api_error(
            error,
            provider=provider,
            model=model,
            context_length=self.config.max_context_size,
        )
        
        # 2. 构建策略上下文
        ctx = StrategyContext(
            error=classified,
            attempt=attempt,
            total_retries=self.config.max_retries,
            available_credentials=self.config.available_credentials or [current_credential],
            available_providers=self.config.available_providers or [provider],
            available_models=self.config.available_models or [model],
            current_provider=current_provider or provider,
            current_model=current_model or model,
            current_credential=current_credential,
            context_size=context_size,
            max_context_size=self.config.max_context_size,
        )
        
        # 3. 策略匹配
        strategy_result = self._matcher.match(classified, ctx)
        
        # 4. 构建决策结果
        backoff = float(strategy_result.backoff_seconds) * float(
            self.config.cooldown_scale
        )
        confidence = max(
            float(self.config.confidence_floor),
            min(1.0, float(strategy_result.confidence)),
        )
        should_compress = strategy_result.should_compress
        if ctx.context_pressure >= self.config.compress_context_pressure:
            should_compress = True

        result = DecisionResult(
            classified_error=classified,
            strategy_result=strategy_result,
            matched_rules=strategy_result.matched_rules,
            suggested_actions=strategy_result.actions,
            suggested_provider=strategy_result.suggested_provider,
            suggested_model=strategy_result.suggested_model,
            suggested_credential=strategy_result.suggested_credential,
            backoff_seconds=backoff,
            should_compress=should_compress,
            should_abort=strategy_result.should_abort,
            decision_time_ms=(time.time() - start_time) * 1000,
            confidence=confidence,
        )

        self._decision_count += 1
        self._log_decision(result, attempt)
        
        return result

    def _log_decision(self, result: DecisionResult, attempt: int) -> None:
        """记录决策日志"""
        logger.info(
            f"Decision[{self._decision_count}]: "
            f"reason={result.classified_error.reason.value}, "
            f"actions={[a.value for a in result.suggested_actions]}, "
            f"attempt={attempt}, "
            f"retry={result.should_retry}, "
            f"fallback={result.should_fallback}, "
            f"backoff={result.backoff_seconds:.1f}s"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取决策统计"""
        return {
            "decisions": self._decision_count,
            "matcher_stats": self._matcher.get_stats(),
            "config": {
                "max_retries": self.config.max_retries,
                "providers": self.config.available_providers,
                "credentials": len(self.config.available_credentials),
            }
        }


# ============================================================================
# 便捷函数
# ============================================================================

_default_ring: Optional[DecisionRing] = None


def get_decision_ring(
    providers: Optional[List[str]] = None,
    credentials: Optional[List[str]] = None,
    models: Optional[List[str]] = None,
) -> DecisionRing:
    """获取默认决策环（单例）"""
    global _default_ring
    if _default_ring is None:
        config = DecisionRingConfig(
            available_providers=providers or [],
            available_credentials=credentials or [],
            available_models=models or [],
        )
        _default_ring = DecisionRing(config)
    return _default_ring


def reset_decision_ring() -> None:
    """重置默认决策环"""
    global _default_ring
    _default_ring = None


def decide_error(
    error: Exception,
    *,
    provider: str = "",
    model: str = "",
    attempt: int = 0,
    context_size: int = 0,
    available_credentials: Optional[List[str]] = None,
    available_providers: Optional[List[str]] = None,
    available_models: Optional[List[str]] = None,
    max_retries: int = 3,
) -> DecisionResult:
    """
    便捷函数：一步完成错误决策。
    
    Args:
        error: API异常
        provider: 当前provider
        model: 当前模型
        attempt: 当前尝试次数
        context_size: 当前上下文大小
        available_credentials: 可用凭证列表
        available_providers: 可用provider列表
        available_models: 可用模型列表
        max_retries: 最大重试次数
        
    Returns:
        DecisionResult: 决策结果
    """
    ring = get_decision_ring(
        providers=available_providers,
        credentials=available_credentials,
        models=available_models,
    )
    ring.config.max_retries = max_retries
    
    return ring.decide(
        error,
        provider=provider,
        model=model,
        attempt=attempt,
        context_size=context_size,
    )
