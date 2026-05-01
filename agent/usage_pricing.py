"""
MimirAether Usage Pricing - 用量与计费

学习自Hermes usage_pricing.py设计。

核心功能：
- CanonicalUsage: 规范化用量数据
- PricingEntry: 定价条目
- CostResult: 成本计算结果
- 官方定价快照
- 用量成本估算
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Literal, Optional, Tuple

# ============================================================================
# 常量
# ============================================================================

DEFAULT_PRICING = {"input": 0.0, "output": 0.0}
_ZERO = Decimal("0")
_ONE_MILLION = Decimal("1000000")

CostStatus = Literal["actual", "estimated", "included", "unknown"]
CostSource = Literal[
    "provider_cost_api",
    "provider_generation_api",
    "provider_models_api",
    "official_docs_snapshot",
    "user_override",
    "custom_contract",
    "none",
]


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class CanonicalUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    request_count: int = 1
    raw_usage: Optional[dict] = None

    @property
    def prompt_tokens(self) -> int:
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.output_tokens


@dataclass(frozen=True)
class BillingRoute:
    provider: str
    model: str
    base_url: str = ""
    billing_mode: str = "unknown"


@dataclass(frozen=True)
class PricingEntry:
    input_cost_per_million: Optional[Decimal] = None
    output_cost_per_million: Optional[Decimal] = None
    cache_read_cost_per_million: Optional[Decimal] = None
    cache_write_cost_per_million: Optional[Decimal] = None
    request_cost: Optional[Decimal] = None
    source: CostSource = "none"
    source_url: Optional[str] = None
    pricing_version: Optional[str] = None
    fetched_at: Optional[datetime] = None


@dataclass(frozen=True)
class CostResult:
    amount_usd: Optional[Decimal]
    status: CostStatus
    source: CostSource
    label: str
    fetched_at: Optional[datetime] = None
    pricing_version: Optional[str] = None
    notes: Tuple[str, ...] = ()


_UTC_NOW = lambda: datetime.now(timezone.utc)


# ============================================================================
# 官方定价快照
# ============================================================================

_OFFICIAL_DOCS_PRICING: Dict[Tuple[str, str], PricingEntry] = {
    # Anthropic
    ("anthropic", "claude-opus-4-20250514"): PricingEntry(
        input_cost_per_million=Decimal("15.00"),
        output_cost_per_million=Decimal("75.00"),
        cache_read_cost_per_million=Decimal("1.50"),
        cache_write_cost_per_million=Decimal("18.75"),
        source="official_docs_snapshot",
        source_url="https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching",
        pricing_version="anthropic-prompt-caching-2026-03-16",
    ),
    ("anthropic", "claude-sonnet-4-20250514"): PricingEntry(
        input_cost_per_million=Decimal("3.00"),
        output_cost_per_million=Decimal("15.00"),
        cache_read_cost_per_million=Decimal("0.30"),
        cache_write_cost_per_million=Decimal("3.75"),
        source="official_docs_snapshot",
        source_url="https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching",
        pricing_version="anthropic-prompt-caching-2026-03-16",
    ),
    ("anthropic", "claude-3-5-sonnet-20241022"): PricingEntry(
        input_cost_per_million=Decimal("3.00"),
        output_cost_per_million=Decimal("15.00"),
        cache_read_cost_per_million=Decimal("0.30"),
        cache_write_cost_per_million=Decimal("3.75"),
        source="official_docs_snapshot",
        source_url="https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching",
        pricing_version="anthropic-pricing-2026-03-16",
    ),
    ("anthropic", "claude-3-5-haiku-20241022"): PricingEntry(
        input_cost_per_million=Decimal("0.80"),
        output_cost_per_million=Decimal("4.00"),
        cache_read_cost_per_million=Decimal("0.08"),
        cache_write_cost_per_million=Decimal("1.00"),
        source="official_docs_snapshot",
        source_url="https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching",
        pricing_version="anthropic-pricing-2026-03-16",
    ),
    # OpenAI
    ("openai", "gpt-4o"): PricingEntry(
        input_cost_per_million=Decimal("2.50"),
        output_cost_per_million=Decimal("10.00"),
        cache_read_cost_per_million=Decimal("1.25"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="openai-pricing-2026-03-16",
    ),
    ("openai", "gpt-4o-mini"): PricingEntry(
        input_cost_per_million=Decimal("0.15"),
        output_cost_per_million=Decimal("0.60"),
        cache_read_cost_per_million=Decimal("0.075"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="openai-pricing-2026-03-16",
    ),
    ("openai", "o3"): PricingEntry(
        input_cost_per_million=Decimal("10.00"),
        output_cost_per_million=Decimal("40.00"),
        cache_read_cost_per_million=Decimal("2.50"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="openai-pricing-2026-03-16",
    ),
    # DeepSeek
    ("deepseek", "deepseek-chat"): PricingEntry(
        input_cost_per_million=Decimal("0.14"),
        output_cost_per_million=Decimal("0.28"),
        source="official_docs_snapshot",
        source_url="https://api-docs.deepseek.com/quick_start/pricing",
        pricing_version="deepseek-pricing-2026-03-16",
    ),
    ("deepseek", "deepseek-reasoner"): PricingEntry(
        input_cost_per_million=Decimal("0.55"),
        output_cost_per_million=Decimal("2.19"),
        source="official_docs_snapshot",
        source_url="https://api-docs.deepseek.com/quick_start/pricing",
        pricing_version="deepseek-pricing-2026-03-16",
    ),
    # Google Gemini
    ("google", "gemini-2.5-flash"): PricingEntry(
        input_cost_per_million=Decimal("0.15"),
        output_cost_per_million=Decimal("0.60"),
        source="official_docs_snapshot",
        source_url="https://ai.google.dev/pricing",
        pricing_version="google-pricing-2026-03-16",
    ),
}


# ============================================================================
# 工具函数
# ============================================================================

def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    """从对象或字典获取值"""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ============================================================================
# 路由解析
# ============================================================================

def resolve_billing_route(
    model_name: str,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
) -> BillingRoute:
    provider_name = (provider or "").strip().lower()
    base = (base_url or "").strip().lower()
    model = (model_name or "").strip()

    if not provider_name and "/" in model:
        inferred_provider, bare_model = model.split("/", 1)
        if inferred_provider in {"anthropic", "openai", "google", "deepseek"}:
            provider_name = inferred_provider
            model = bare_model
    # 也支持 "provider-model" 格式（如 deepseek-reasoner）
    elif not provider_name and "-" in model:
        potential_provider = model.split("-")[0]
        if potential_provider in {"anthropic", "openai", "google", "deepseek"}:
            provider_name = potential_provider

    if provider_name == "openai-codex":
        return BillingRoute(provider="openai-codex", model=model, base_url=base_url or "", billing_mode="subscription_included")
    if provider_name == "openrouter" or "openrouter.ai" in base:
        return BillingRoute(provider="openrouter", model=model, base_url=base_url or "", billing_mode="official_models_api")
    if provider_name == "anthropic":
        return BillingRoute(provider="anthropic", model=model.split("/")[-1], base_url=base_url or "", billing_mode="official_docs_snapshot")
    if provider_name == "openai":
        return BillingRoute(provider="openai", model=model.split("/")[-1], base_url=base_url or "", billing_mode="official_docs_snapshot")
    if provider_name in {"custom", "local"} or (base and "localhost" in base):
        return BillingRoute(provider=provider_name or "custom", model=model, base_url=base_url or "", billing_mode="unknown")
    return BillingRoute(provider=provider_name or "unknown", model=model.split("/")[-1] if model else "", base_url=base_url or "", billing_mode="unknown")


def _lookup_official_docs_pricing(route: BillingRoute) -> Optional[PricingEntry]:
    return _OFFICIAL_DOCS_PRICING.get((route.provider, route.model.lower()))


# ============================================================================
# 定价获取
# ============================================================================

def get_pricing_entry(
    model_name: str,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Optional[PricingEntry]:
    route = resolve_billing_route(model_name, provider=provider, base_url=base_url)

    if route.billing_mode == "subscription_included":
        return PricingEntry(
            input_cost_per_million=_ZERO,
            output_cost_per_million=_ZERO,
            cache_read_cost_per_million=_ZERO,
            cache_write_cost_per_million=_ZERO,
            source="none",
            pricing_version="included-route",
        )

    if route.provider in {"custom", "local"} or not route.provider:
        return None

    return _lookup_official_docs_pricing(route)


# Hermès兼容函数（OpenRouter API定价，需要model_metadata支持）
def _per_token_to_per_million(value: Any) -> Any:
    """将per-token价格转换为per-million（Hermès兼容）"""
    # MimirAether暂不支持OpenRouter API定价
    return value


def _pricing_entry_from_metadata(
    metadata: Dict[str, Dict[str, Any]],
    model_id: str,
    *,
    source_url: str,
    pricing_version: str,
) -> Optional[PricingEntry]:
    """从模型元数据构建定价条目（Hermès兼容，桩实现）"""
    # MimirAether暂不支持OpenRouter API定价
    return None


def _openrouter_pricing_entry(route: Any) -> Optional[PricingEntry]:
    """获取OpenRouter路由的定价条目（Hermès兼容，桩实现）"""
    # MimirAether暂不支持OpenRouter API定价
    return None


# ============================================================================
# 用量规范化
# ============================================================================

def normalize_usage(
    response_usage: Any,
    *,
    provider: Optional[str] = None,
    api_mode: Optional[str] = None,
) -> CanonicalUsage:
    """Normalize raw API response usage into canonical token buckets."""
    if not response_usage:
        return CanonicalUsage()

    provider_name = (provider or "").strip().lower()
    mode = (api_mode or "").strip().lower()

    if mode == "anthropic_messages" or provider_name == "anthropic":
        input_tokens = _to_int(_get_val(response_usage, "input_tokens", 0))
        output_tokens = _to_int(_get_val(response_usage, "output_tokens", 0))
        cache_read_tokens = _to_int(_get_val(response_usage, "cache_read_input_tokens", 0))
        cache_write_tokens = _to_int(_get_val(response_usage, "cache_creation_input_tokens", 0))
    elif mode == "openai" or mode == "":
        prompt_total = _to_int(_get_val(response_usage, "prompt_tokens", 0))
        output_tokens = _to_int(_get_val(response_usage, "completion_tokens", 0))
        details = _get_val(response_usage, "prompt_tokens_details", None)
        cache_read_tokens = _to_int(_get_val(details, "cached_tokens", 0) if details else 0)
        cache_write_tokens = _to_int(_get_val(details, "cache_write_tokens", 0) if details else 0)
        input_tokens = max(0, prompt_total - cache_read_tokens - cache_write_tokens)
    else:
        input_tokens = _to_int(_get_val(response_usage, "input_tokens", 0))
        output_tokens = _to_int(_get_val(response_usage, "output_tokens", 0))
        cache_read_tokens = _to_int(_get_val(response_usage, "cache_read_tokens", 0))
        cache_write_tokens = _to_int(_get_val(response_usage, "cache_write_tokens", 0))

    reasoning_tokens = 0
    output_details = _get_val(response_usage, "output_tokens_details", None)
    if output_details:
        reasoning_tokens = _to_int(_get_val(output_details, "reasoning_tokens", 0))

    return CanonicalUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        reasoning_tokens=reasoning_tokens,
    )


# ============================================================================
# 成本估算
# ============================================================================

def estimate_usage_cost(
    model_name: str,
    usage: CanonicalUsage,
    *,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> CostResult:
    route = resolve_billing_route(model_name, provider=provider, base_url=base_url)

    if route.billing_mode == "subscription_included":
        return CostResult(
            amount_usd=_ZERO,
            status="included",
            source="none",
            label="included",
            pricing_version="included-route",
        )

    entry = get_pricing_entry(model_name, provider=provider, base_url=base_url, api_key=api_key)
    if not entry:
        return CostResult(amount_usd=None, status="unknown", source="none", label="n/a")

    notes: list[str] = []
    amount = _ZERO

    if entry.input_cost_per_million is not None:
        amount += Decimal(usage.input_tokens) * entry.input_cost_per_million / _ONE_MILLION
    if entry.output_cost_per_million is not None:
        amount += Decimal(usage.output_tokens) * entry.output_cost_per_million / _ONE_MILLION
    if entry.cache_read_cost_per_million is not None:
        amount += Decimal(usage.cache_read_tokens) * entry.cache_read_cost_per_million / _ONE_MILLION
    if entry.cache_write_cost_per_million is not None:
        amount += Decimal(usage.cache_write_tokens) * entry.cache_write_cost_per_million / _ONE_MILLION
    if entry.request_cost is not None and usage.request_count:
        amount += Decimal(usage.request_count) * entry.request_cost

    status: CostStatus = "estimated"
    label = f"~${amount:.2f}"

    return CostResult(
        amount_usd=amount,
        status=status,
        source=entry.source,
        label=label,
        fetched_at=entry.fetched_at,
        pricing_version=entry.pricing_version,
        notes=tuple(notes),
    )


def has_known_pricing(
    model_name: str,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> bool:
    """Check whether we have pricing data for this model+route."""
    route = resolve_billing_route(model_name, provider=provider, base_url=base_url)
    if route.billing_mode == "subscription_included":
        return True
    entry = get_pricing_entry(model_name, provider=provider, base_url=base_url, api_key=api_key)
    return entry is not None


# ============================================================================
# 格式化工具
# ============================================================================

def format_duration_compact(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        # 动态选择小数位数
        if minutes >= 10:
            return f"{int(minutes)}m"
        elif minutes >= 1:
            return f"{minutes:.1f}m"
        else:
            return f"{minutes:.2f}m"
    hours = minutes / 60
    if hours < 24:
        remaining_min = int(minutes % 60)
        return f"{int(hours)}h {remaining_min}m" if remaining_min else f"{int(hours)}h"
    days = hours / 24
    return f"{days:.1f}d"


def format_token_count_compact(value: int) -> str:
    abs_value = abs(int(value))
    if abs_value < 1_000:
        return str(int(value))

    sign = "-" if value < 0 else ""
    units = ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K"))
    for threshold, suffix in units:
        if abs_value >= threshold:
            scaled = abs_value / threshold
            if scaled < 10:
                text = f"{scaled:.2f}"
            elif scaled < 100:
                text = f"{scaled:.1f}"
            else:
                text = f"{scaled:.0f}"
            if "." in text:
                text = text.rstrip("0").rstrip(".")
            return f"{sign}{text}{suffix}"

    return f"{value:,}"


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Usage Pricing 测试")
    print("=" * 60)

    # 测试1: CanonicalUsage
    print("\n[测试1] CanonicalUsage")
    usage = CanonicalUsage(input_tokens=1000, output_tokens=500, cache_read_tokens=200)
    assert usage.prompt_tokens == 1200
    assert usage.total_tokens == 1700
    print(f"  prompt_tokens: {usage.prompt_tokens}, total_tokens: {usage.total_tokens}")
    print("  ✅ 通过")

    # 测试2: BillingRoute
    print("\n[测试2] BillingRoute")
    route = resolve_billing_route("gpt-4o", provider="openai")
    assert route.provider == "openai"
    assert route.model == "gpt-4o"
    print(f"  provider: {route.provider}, model: {route.model}")
    print("  ✅ 通过")

    # 测试3: resolve_billing_route 模型推断
    print("\n[测试3] resolve_billing_route 模型推断")
    route = resolve_billing_route("anthropic/claude-3-5-sonnet-20241022")
    assert route.provider == "anthropic"
    assert route.model == "claude-3-5-sonnet-20241022"
    print(f"  推断: {route.provider}/{route.model}")
    print("  ✅ 通过")

    # 测试4: get_pricing_entry DeepSeek
    print("\n[测试4] get_pricing_entry DeepSeek")
    entry = get_pricing_entry("deepseek-chat", provider="deepseek")
    assert entry is not None
    assert entry.input_cost_per_million == Decimal("0.14")
    print(f"  input: ${entry.input_cost_per_million}/M, output: ${entry.output_cost_per_million}/M")
    print("  ✅ 通过")

    # 测试5: get_pricing_entry 未知模型
    print("\n[测试5] get_pricing_entry 未知模型")
    entry = get_pricing_entry("unknown-model", provider="unknown")
    assert entry is None
    print("  未知模型返回None")
    print("  ✅ 通过")

    # 测试6: normalize_usage OpenAI格式
    print("\n[测试6] normalize_usage OpenAI格式")
    raw_usage = {"prompt_tokens": 1500, "completion_tokens": 300, "prompt_tokens_details": {"cached_tokens": 200}}
    usage = normalize_usage(raw_usage, api_mode="openai")
    assert usage.input_tokens == 1300, f"Expected 1300, got {usage.input_tokens}"
    assert usage.cache_read_tokens == 200
    assert usage.output_tokens == 300
    print(f"  input: {usage.input_tokens}, cache_read: {usage.cache_read_tokens}, output: {usage.output_tokens}")
    print("  ✅ 通过")

    # 测试7: normalize_usage 空输入
    print("\n[测试7] normalize_usage 空输入")
    usage = normalize_usage(None)
    assert usage.input_tokens == 0
    assert usage.output_tokens == 0
    print("  空输入返回零用量")
    print("  ✅ 通过")

    # 测试8: estimate_usage_cost
    print("\n[测试8] estimate_usage_cost")
    usage = CanonicalUsage(input_tokens=1_000_000, output_tokens=500_000)
    result = estimate_usage_cost("deepseek-chat", usage, provider="deepseek")
    assert result.status == "estimated"
    assert result.amount_usd is not None
    # 0.14 * 1 + 0.28 * 0.5 = 0.14 + 0.14 = 0.28
    assert result.amount_usd == Decimal("0.28")
    print(f"  费用: {result.label}, 状态: {result.status}")
    print("  ✅ 通过")

    # 测试9: has_known_pricing
    print("\n[测试9] has_known_pricing")
    assert has_known_pricing("gpt-4o", provider="openai") == True
    assert has_known_pricing("unknown-model", provider="unknown") == False
    print("  gpt-4o: True, unknown: False")
    print("  ✅ 通过")

    # 测试10: format_duration_compact
    print("\n[测试10] format_duration_compact")
    assert format_duration_compact(30) == "30s"

    # 测试10: format_duration_compact
    print("\n[测试10] format_duration_compact")
    assert format_duration_compact(30) == "30s"
    assert format_duration_compact(90) == "1.5m"
    assert format_duration_compact(3600) == "1h"
    assert format_duration_compact(90000) == "1.0d"
    print("  ✅ 通过")

    # 测试11: format_token_count_compact
    print("\n[测试11] format_token_count_compact")
    assert format_token_count_compact(500) == "500"
    assert format_token_count_compact(1500) == "1.5K"
    assert format_token_count_compact(1_500_000) == "1.5M"
    print("  ✅ 通过")

    # 测试12: PricingEntry完整数据
    print("\n[测试12] PricingEntry完整数据")
    entry = get_pricing_entry("claude-opus-4-20250514", provider="anthropic")
    assert entry is not None
    assert entry.cache_read_cost_per_million == Decimal("1.50")
    assert entry.cache_write_cost_per_million == Decimal("18.75")
    print(f"  cache_read: ${entry.cache_read_cost_per_million}/M, cache_write: ${entry.cache_write_cost_per_million}/M")
    print("  ✅ 通过")

    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)
