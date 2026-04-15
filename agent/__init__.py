# MimirAether - Agent Core

from .core_loop import MimirAetherAgent, Message, MessageRole, ToolResult, ToolRegistry, IterationBudget
from .turn_loop import TurnManager, Turn, TurnStatus
from .subagent import SubAgentPool, SubAgentTask, SubAgentStatus, TaskDecomposer, TaskDecomposition
from .context_compressor import ContextCompressor, CompressionResult, compress_conversation, SUMMARY_PREFIX
from .insights import InsightsEngine, InsightsReport, SessionInsights, MetricType, UsageRecord, get_insights

# 新集成模块
from . import prompt_builder
from . import model_metadata
from . import anthropic_adapter
from . import credential_pool
from . import smart_model_routing
from . import error_classifier
from . import rate_limit_tracker
from . import prompt_caching
from .smart_model_routing import (
    choose_cheap_model_route,
    resolve_turn_route,
    DEFAULT_ROUTING_CONFIG,
)
from .credential_pool import (
    CredentialPool,
    PooledCredential,
    CredentialPoolRegistry,
    get_default_registry,
    create_credential,
)
from .error_classifier import (
    FailoverReason,
    ClassifiedError,
    classify_api_error,
)
from .rate_limit_tracker import (
    RateLimitTracker,
    RateLimitState,
    RateLimitBucket,
    parse_rate_limit_headers,
    format_rate_limit_display,
)
from .prompt_caching import (
    apply_anthropic_cache_control,
    apply_openai_cache,
    estimate_caching_savings,
    calculate_caching_benefit,
    CacheBudgetManager,
)

__all__ = [
    # Core
    "MimirAetherAgent",
    "Message",
    "MessageRole",
    "ToolResult",
    "ToolRegistry",
    "IterationBudget",
    # Turn Management
    "TurnManager",
    "Turn",
    "TurnStatus",
    # SubAgent
    "SubAgentPool",
    "SubAgentTask",
    "SubAgentStatus",
    "TaskDecomposer",
    "TaskDecomposition",
    # Context Compression
    "ContextCompressor",
    "CompressionResult",
    "compress_conversation",
    "SUMMARY_PREFIX",
    # Insights
    "InsightsEngine",
    "InsightsReport",
    "SessionInsights",
    "MetricType",
    "UsageRecord",
    "get_insights",
    # Credential Pool
    "CredentialPool",
    "PooledCredential",
    "CredentialPoolRegistry",
    "get_default_registry",
    "create_credential",
    # Smart Model Routing
    "choose_cheap_model_route",
    "resolve_turn_route",
    "DEFAULT_ROUTING_CONFIG",
    # Error Classifier
    "FailoverReason",
    "ClassifiedError",
    "classify_api_error",
    # Rate Limit Tracker
    "RateLimitTracker",
    "RateLimitState",
    "RateLimitBucket",
    "parse_rate_limit_headers",
    "format_rate_limit_display",
    # Prompt Caching
    "apply_anthropic_cache_control",
    "apply_openai_cache",
    "estimate_caching_savings",
    "calculate_caching_benefit",
    "CacheBudgetManager",
    # Integrated Modules
    "prompt_builder",
    "model_metadata",
    "anthropic_adapter",
    "credential_pool",
    "smart_model_routing",
    "error_classifier",
    "rate_limit_tracker",
    "prompt_caching",
]
