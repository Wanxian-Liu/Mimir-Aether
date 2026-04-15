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
from . import retry_utils
from . import context_engine
from . import context_compressor
from . import memory_manager
from . import context_references
from . import skill_utils
from . import trajectory
from . import title_generator
from . import usage_pricing
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
from .retry_utils import (
    jittered_backoff,
    decorrelated_jittered_backoff,
    RetryManager,
    RetryContext,
    is_retryable_error,
    get_retry_delay,
    with_retry,
)
from .context_engine import (
    ContextEngine,
    ContextEngineRegistry,
    get_engine_registry,
    register_engine,
    create_context_engine,
)
from .context_compressor import (
    ContextCompressorV2,
    ContextCompressor,
    CompressionResult,
    compress_conversation,
    SUMMARY_PREFIX,
)
from .memory_manager import (
    MemoryProvider,
    MemoryManager,
    BuiltinMemoryProvider,
)
from .context_references import (
    ContextReference,
    ContextReferenceResult,
    parse_context_references,
    preprocess_context_references,
    REFERENCE_PATTERN,
)
from .skill_utils import (
    parse_frontmatter,
    skill_matches_platform,
    get_skills_dir,
    get_all_skills_dirs,
    get_disabled_skill_names,
    discover_skills,
    extract_skill_conditions,
    extract_skill_config_vars,
    PLATFORM_MAP,
)
from .trajectory import (
    normalize_scratchpad_tags,
    has_incomplete_scratchpad,
    validate_trajectory,
    save_trajectory,
    load_trajectories,
    count_trajectories,
    get_trajectory_dir,
)
from .title_generator import (
    generate_title,
    generate_simple_title,
    maybe_auto_title,
    auto_title_session,
)
from .usage_pricing import (
    CanonicalUsage,
    BillingRoute,
    PricingEntry,
    CostResult,
    resolve_billing_route,
    get_pricing_entry,
    normalize_usage,
    estimate_usage_cost,
    has_known_pricing,
    format_duration_compact,
    format_token_count_compact,
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
    # Retry Utils
    "jittered_backoff",
    "decorrelated_jittered_backoff",
    "RetryManager",
    "RetryContext",
    "is_retryable_error",
    "get_retry_delay",
    "with_retry",
    # Context Engine
    "ContextEngine",
    "ContextEngineRegistry",
    "get_engine_registry",
    "register_engine",
    "create_context_engine",
    # Context Compressor
    "ContextCompressorV2",
    "ContextCompressor",
    "CompressionResult",
    "compress_conversation",
    "SUMMARY_PREFIX",
    # Memory Manager
    "MemoryProvider",
    "MemoryManager",
    "BuiltinMemoryProvider",
    # Context References
    "ContextReference",
    "ContextReferenceResult",
    "parse_context_references",
    "preprocess_context_references",
    "REFERENCE_PATTERN",
    # Skill Utils
    "parse_frontmatter",
    "skill_matches_platform",
    "get_skills_dir",
    "get_all_skills_dirs",
    "get_disabled_skill_names",
    "discover_skills",
    "extract_skill_conditions",
    "extract_skill_config_vars",
    # Trajectory
    "normalize_scratchpad_tags",
    "has_incomplete_scratchpad",
    "validate_trajectory",
    "save_trajectory",
    "load_trajectories",
    "count_trajectories",
    "get_trajectory_dir",
    # Title Generator
    "generate_title",
    "generate_simple_title",
    "maybe_auto_title",
    "auto_title_session",
    # Usage Pricing
    "CanonicalUsage",
    "BillingRoute",
    "PricingEntry",
    "CostResult",
    "resolve_billing_route",
    "get_pricing_entry",
    "normalize_usage",
    "estimate_usage_cost",
    "has_known_pricing",
    "format_duration_compact",
    "format_token_count_compact",
    # Integrated Modules
    "prompt_builder",
    "model_metadata",
    "anthropic_adapter",
    "credential_pool",
    "smart_model_routing",
    "error_classifier",
    "rate_limit_tracker",
    "prompt_caching",
    "retry_utils",
    "context_engine",
    "context_compressor",
    "memory_manager",
    "context_references",
    "skill_utils",
    "trajectory",
    "title_generator",
    "usage_pricing",
]
