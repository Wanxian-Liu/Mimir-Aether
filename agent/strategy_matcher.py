"""
Strategy Matcher for MimirAether Decision Ring

将ClassifiedError映射到具体执行策略。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .error_classifier import ClassifiedError, FailoverReason

logger = logging.getLogger(__name__)


class StrategyAction(Enum):
    """策略动作类型"""
    RETRY = "retry"
    RETRY_WITH_BACKOFF = "retry_backoff"
    ROTATE_CREDENTIAL = "rotate_cred"
    FALLBACK_PROVIDER = "fallback_provider"
    COMPRESS_CONTEXT = "compress"
    TRUNCATE_CONTEXT = "truncate"
    REDUCE_PAYLOAD = "reduce_payload"
    DOWNGRADE_MODEL = "downgrade_model"
    REDUCE_MAX_TOKENS = "reduce_max_tokens"
    REDUCE_TEMPERATURE = "reduce_temp"
    RETRY_WITHOUT_THINKING = "no_thinking"
    RETRY_WITHOUT_EXTRA = "no_extra"
    ABORT = "abort"
    WAIT_FOR_RATE_LIMIT = "wait_rate_limit"
    WAIT_FOR_CREDITS = "wait_credits"


@dataclass
class StrategyRule:
    """策略规则"""
    name: str
    condition: Callable[[ClassifiedError, "StrategyContext"], bool]
    actions: List[StrategyAction]
    priority: int = 0
    cooldown: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyContext:
    """策略执行上下文"""
    error: ClassifiedError
    attempt: int = 0
    total_retries: int = 3
    available_credentials: List[str] = field(default_factory=list)
    available_providers: List[str] = field(default_factory=list)
    available_models: List[str] = field(default_factory=list)
    current_provider: str = ""
    current_model: str = ""
    current_credential: str = ""
    context_size: int = 0
    max_context_size: int = 200000
    last_action_time: float = 0.0
    action_history: List[Tuple[float, StrategyAction]] = field(default_factory=list)
    
    @property
    def retry_exhausted(self) -> bool:
        return self.attempt >= self.total_retries
    
    @property
    def has_fallback(self) -> bool:
        return len(self.available_providers) > 1 or len(self.available_credentials) > 1
    
    @property
    def context_pressure(self) -> float:
        if self.max_context_size <= 0:
            return 0.0
        return min(self.context_size / self.max_context_size, 1.0)


@dataclass
class StrategyResult:
    """策略匹配结果"""
    matched_rules: List[str] = field(default_factory=list)
    actions: List[StrategyAction] = field(default_factory=list)
    suggested_provider: Optional[str] = None
    suggested_model: Optional[str] = None
    suggested_credential: Optional[str] = None
    backoff_seconds: float = 0.0
    should_compress: bool = False
    should_abort: bool = False
    confidence: float = 1.0
    
    def add_action(self, action: StrategyAction) -> "StrategyResult":
        if action not in self.actions:
            self.actions.append(action)
        return self


# Provider-specific规则库
OPENAI_SPECIFIC_RULES = [
    StrategyRule(
        name="openai_401_auth",
        condition=lambda e, ctx: e.status_code == 401 and "openai" in (e.provider or "").lower(),
        actions=[StrategyAction.ROTATE_CREDENTIAL, StrategyAction.FALLBACK_PROVIDER],
        priority=100,
    ),
    StrategyRule(
        name="openai_429_tier_guard",
        condition=lambda e, ctx: e.status_code == 429 and "openai" in (e.provider or "").lower() and ("tier" in (e.message or "").lower() or "limit" in (e.message or "").lower()),
        actions=[StrategyAction.ROTATE_CREDENTIAL, StrategyAction.WAIT_FOR_RATE_LIMIT],
        priority=90,
        cooldown=60.0,
    ),
]

ANTHROPIC_SPECIFIC_RULES = [
    StrategyRule(
        name="anthropic_thinking_sig",
        condition=lambda e, ctx: e.reason == FailoverReason.thinking_signature,
        actions=[StrategyAction.RETRY_WITHOUT_THINKING],
        priority=100,
    ),
    StrategyRule(
        name="anthropic_long_context_tier",
        condition=lambda e, ctx: e.reason == FailoverReason.long_context_tier,
        actions=[StrategyAction.COMPRESS_CONTEXT, StrategyAction.WAIT_FOR_RATE_LIMIT],
        priority=95,
        cooldown=30.0,
    ),
    StrategyRule(
        name="anthropic_429_context",
        condition=lambda e, ctx: e.status_code == 429 and "anthropic" in (e.provider or "").lower() and ctx.context_pressure > 0.7,
        actions=[StrategyAction.COMPRESS_CONTEXT, StrategyAction.ROTATE_CREDENTIAL],
        priority=85,
    ),
]

DEEPSEEK_SPECIFIC_RULES = [
    StrategyRule(
        name="deepseek_rate_limit",
        condition=lambda e, ctx: e.reason == FailoverReason.rate_limit and "deepseek" in (e.provider or "").lower(),
        actions=[StrategyAction.ROTATE_CREDENTIAL, StrategyAction.RETRY_WITH_BACKOFF],
        priority=90,
        cooldown=10.0,
    ),
]

GENERIC_RULES = [
    StrategyRule(name="auth_permanent", condition=lambda e, ctx: e.reason == FailoverReason.auth_permanent, actions=[StrategyAction.ABORT], priority=100),
    StrategyRule(name="auth_error", condition=lambda e, ctx: e.is_auth and ctx.has_fallback, actions=[StrategyAction.ROTATE_CREDENTIAL, StrategyAction.FALLBACK_PROVIDER], priority=95),
    StrategyRule(name="billing_error", condition=lambda e, ctx: e.reason == FailoverReason.billing, actions=[StrategyAction.ROTATE_CREDENTIAL, StrategyAction.FALLBACK_PROVIDER, StrategyAction.WAIT_FOR_CREDITS], priority=95),
    StrategyRule(name="rate_limit_with_fallback", condition=lambda e, ctx: e.reason == FailoverReason.rate_limit and ctx.has_fallback, actions=[StrategyAction.ROTATE_CREDENTIAL, StrategyAction.RETRY_WITH_BACKOFF], priority=85, cooldown=5.0),
    StrategyRule(name="rate_limit_no_fallback", condition=lambda e, ctx: e.reason == FailoverReason.rate_limit and not ctx.has_fallback, actions=[StrategyAction.WAIT_FOR_RATE_LIMIT, StrategyAction.RETRY_WITH_BACKOFF], priority=80, cooldown=10.0),
    StrategyRule(name="context_overflow_high", condition=lambda e, ctx: e.reason == FailoverReason.context_overflow and ctx.context_pressure > 0.8, actions=[StrategyAction.COMPRESS_CONTEXT, StrategyAction.TRUNCATE_CONTEXT], priority=90),
    StrategyRule(name="context_overflow_medium", condition=lambda e, ctx: e.reason == FailoverReason.context_overflow and 0.5 < ctx.context_pressure <= 0.8, actions=[StrategyAction.COMPRESS_CONTEXT], priority=85),
    StrategyRule(name="context_overflow_low", condition=lambda e, ctx: e.reason == FailoverReason.context_overflow and ctx.context_pressure <= 0.5, actions=[StrategyAction.TRUNCATE_CONTEXT], priority=80),
    StrategyRule(name="payload_too_large", condition=lambda e, ctx: e.reason == FailoverReason.payload_too_large, actions=[StrategyAction.REDUCE_PAYLOAD, StrategyAction.COMPRESS_CONTEXT], priority=88),
    StrategyRule(name="model_not_found", condition=lambda e, ctx: e.reason == FailoverReason.model_not_found, actions=[StrategyAction.FALLBACK_PROVIDER], priority=95),
    StrategyRule(name="server_overloaded", condition=lambda e, ctx: e.reason in (FailoverReason.overloaded, FailoverReason.server_error), actions=[StrategyAction.RETRY_WITH_BACKOFF, StrategyAction.FALLBACK_PROVIDER], priority=75, cooldown=5.0),
    StrategyRule(name="timeout_error", condition=lambda e, ctx: e.reason == FailoverReason.timeout, actions=[StrategyAction.RETRY], priority=70),
    StrategyRule(name="format_error", condition=lambda e, ctx: e.reason == FailoverReason.format_error, actions=[StrategyAction.REDUCE_PAYLOAD, StrategyAction.ABORT], priority=90),
    StrategyRule(name="unknown_error", condition=lambda e, ctx: e.reason == FailoverReason.unknown, actions=[StrategyAction.RETRY_WITH_BACKOFF], priority=50, cooldown=3.0),
]


class StrategyMatcher:
    """策略匹配器"""
    
    def __init__(self, custom_rules: Optional[List[StrategyRule]] = None, enable_provider_rules: bool = True):
        self._rules: List[StrategyRule] = []
        self._cooldown_tracker: Dict[str, float] = {}
        
        for rule in GENERIC_RULES:
            self.add_rule(rule)
        
        if enable_provider_rules:
            for rule in OPENAI_SPECIFIC_RULES + ANTHROPIC_SPECIFIC_RULES + DEEPSEEK_SPECIFIC_RULES:
                self.add_rule(rule)
        
        if custom_rules:
            for rule in custom_rules:
                self.add_rule(rule)
        
        self._sort_rules()
    
    def add_rule(self, rule: StrategyRule) -> None:
        self._rules.append(rule)
    
    def remove_rule(self, name: str) -> bool:
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules.pop(i)
                return True
        return False
    
    def _sort_rules(self) -> None:
        self._rules.sort(key=lambda r: r.priority, reverse=True)
    
    def _is_in_cooldown(self, rule: StrategyRule, current_time: float) -> bool:
        if rule.cooldown <= 0:
            return False
        return current_time - self._cooldown_tracker.get(rule.name, 0) < rule.cooldown
    
    def match(self, error: ClassifiedError, context: StrategyContext, current_time: float = 0.0) -> StrategyResult:
        import time
        if current_time <= 0:
            current_time = time.time()
        
        result = StrategyResult()
        
        for rule in self._rules:
            if self._is_in_cooldown(rule, current_time):
                continue
            try:
                if rule.condition(error, context):
                    result.matched_rules.append(rule.name)
                    for action in rule.actions:
                        result.add_action(action)
                    if rule.cooldown > 0:
                        self._cooldown_tracker[rule.name] = current_time
                    context.action_history.append((current_time, rule.actions[0] if rule.actions else StrategyAction.RETRY))
            except Exception as e:
                logger.warning(f"Error evaluating rule {rule.name}: {e}")
        
        self._post_process(result, error, context)
        return result
    
    def _post_process(self, result: StrategyResult, error: ClassifiedError, context: StrategyContext) -> None:
        import time
        if StrategyAction.RETRY_WITH_BACKOFF in result.actions:
            if error.reason == FailoverReason.rate_limit:
                result.backoff_seconds = min(30 * (2 ** context.attempt), 300)
            elif error.reason in (FailoverReason.overloaded, FailoverReason.server_error):
                result.backoff_seconds = min(5 * (2 ** context.attempt), 60)
            else:
                result.backoff_seconds = min(2 * (2 ** context.attempt), 30)
        
        result.should_compress = StrategyAction.COMPRESS_CONTEXT in result.actions or StrategyAction.TRUNCATE_CONTEXT in result.actions
        result.should_abort = StrategyAction.ABORT in result.actions
        
        if StrategyAction.FALLBACK_PROVIDER in result.actions and context.available_providers:
            current = context.current_provider.lower()
            for provider in context.available_providers:
                if provider.lower() != current:
                    result.suggested_provider = provider
                    break
        
        if StrategyAction.ROTATE_CREDENTIAL in result.actions and context.available_credentials:
            current = context.current_credential
            for cred in context.available_credentials:
                if cred != current:
                    result.suggested_credential = cred
                    break
        
        context.last_action_time = time.time()
    
    def clear_cooldowns(self) -> None:
        self._cooldown_tracker.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        return {"total_rules": len(self._rules), "active_cooldowns": len(self._cooldown_tracker)}


_default_matcher: Optional[StrategyMatcher] = None

def get_matcher() -> StrategyMatcher:
    """获取默认策略匹配器（单例）"""
    global _default_matcher
    if _default_matcher is None:
        _default_matcher = StrategyMatcher()
    return _default_matcher

def reset_matcher() -> None:
    global _default_matcher
    _default_matcher = None

def classify_and_match(error: Exception, *, provider: str = "", model: str = "", approx_tokens: int = 0, context_length: int = 200000, num_messages: int = 0, attempt: int = 0, total_retries: int = 3, available_credentials: Optional[List[str]] = None, available_providers: Optional[List[str]] = None, available_models: Optional[List[str]] = None, current_provider: str = "", current_model: str = "", current_credential: str = "", context_size: int = 0) -> Tuple[ClassifiedError, StrategyResult]:
    """一步完成错误分类和策略匹配"""
    from .error_classifier import classify_api_error
    
    classified = classify_api_error(error, provider=provider, model=model, approx_tokens=approx_tokens, context_length=context_length, num_messages=num_messages)
    
    ctx = StrategyContext(error=classified, attempt=attempt, total_retries=total_retries, available_credentials=available_credentials or [], available_providers=available_providers or [], available_models=available_models or [], current_provider=current_provider, current_model=current_model, current_credential=current_credential, context_size=context_size, max_context_size=context_length)
    
    return classified, get_matcher().match(classified, ctx)
