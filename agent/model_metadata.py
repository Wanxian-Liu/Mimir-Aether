"""
MimirAether Model Metadata

从Hermes model_metadata设计演进而来（2026-04-24）:
- 完整的OpenRouter元数据获取与缓存
- 持久化YAML缓存（跨会话）
- Nous/OpenRouter suffix matching
- 全面的pricing和max_completion_tokens提取
- 健壮的嵌套数据遍历
- 本地Ollama/LM Studio/vLLM/llama.cpp探测

核心原则：
- 不复制代码，独立实现但功能对齐
- 保持API兼容
- 适配MimirAether框架
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
import yaml

# OpenRouter URL constant
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS_URL = f"{OPENROUTER_BASE_URL}/models"

logger = logging.getLogger(__name__)

# ============================================================================
# 常量
# ============================================================================

# Provider前缀列表
_PROVIDER_PREFIXES = frozenset({
    "openrouter", "nous", "openai-codex", "copilot", "copilot-acp",
    "gemini", "zai", "kimi-coding", "kimi-coding-cn", "minimax", "minimax-cn",
    "anthropic", "deepseek", "opencode-zen", "opencode-go", "ai-gateway",
    "kilocode", "alibaba", "qwen-oauth", "xiaomi", "arcee", "custom", "local",
    "google", "google-gemini", "google-ai-studio", "glm", "z-ai", "z.ai",
    "zhipu", "github", "github-copilot", "github-models", "kimi", "moonshot",
    "moonshot-cn", "claude", "deep-seek", "opencode", "zen", "go", "vercel",
    "kilo", "dashscope", "aliyun", "qwen", "mimo", "xiaomi-mimo",
    "arcee-ai", "arceeai", "qwen-portal",
})

_OLLAMA_TAG_PATTERN = re.compile(
    r"^(\d+\.?\d*b|latest|stable|q\d|fp?\d|instruct|chat|coder|vision|text)",
    re.IGNORECASE,
)

# Context探测层级
CONTEXT_PROBE_TIERS = [128_000, 64_000, 32_000, 16_000, 8_000]
DEFAULT_FALLBACK_CONTEXT = 128_000
MINIMUM_CONTEXT_LENGTH = 64_000

# 默认上下文长度表
DEFAULT_CONTEXT_LENGTHS = {
    # Anthropic Claude 4.6 (1M context)
    "claude-opus-4-6": 1000000,
    "claude-sonnet-4-6": 1000000,
    "claude-opus-4.6": 1000000,
    "claude-sonnet-4.6": 1000000,
    "claude": 200000,
    # OpenAI — GPT-5 family
    "gpt-5.4-nano": 400000,
    "gpt-5.4-mini": 400000,
    "gpt-5.4": 1050000,
    "gpt-5.3-codex-spark": 128000,
    "gpt-5.1-chat": 128000,
    "gpt-5": 400000,
    "gpt-4.1": 1047576,
    "gpt-4": 128000,
    # Google
    "gemini": 1048576,
    "gemma-4-31b": 256000,
    "gemma-4-26b": 256000,
    "gemma-3": 131072,
    "gemma": 8192,
    # DeepSeek
    "deepseek": 128000,
    # Meta Llama
    "llama": 131072,
    # Qwen
    "qwen3-coder-plus": 1000000,
    "qwen3-coder": 262144,
    "qwen": 131072,
    # MiniMax
    "minimax": 204800,
    # GLM
    "glm": 202752,
    # xAI Grok
    "grok-code-fast": 256000,   # grok-code-fast-1
    "grok-4-1-fast": 2000000,
    "grok-2-vision": 8192,      # grok-2-vision, -1212, -latest
    "grok-4-fast": 2000000,
    "grok-4.20": 2000000,
    "grok-4": 256000,
    "grok-3": 131072,
    "grok-2": 131072,
    "grok": 131072,
    # Kimi
    "kimi": 262144,
    # Arcee
    "trinity": 262144,
    # OpenRouter specific
    "elephant": 262144,
    # HuggingFace Inference Providers
    "Qwen/Qwen3.5-397B-A17B": 131072,
    "Qwen/Qwen3.5-35B-A3B": 131072,
    "deepseek-ai/DeepSeek-V3.2": 65536,
    "moonshotai/Kimi-K2.5": 262144,
    "moonshotai/Kimi-K2-Thinking": 262144,
    "MiniMaxAI/MiniMax-M2.5": 204800,
    "XiaomiMiMo/MiMo-V2-Flash": 256000,
    "mimo-v2-pro": 1000000,
    "mimo-v2-omni": 256000,
    "mimo-v2-flash": 256000,
    "zai-org/GLM-5": 202752,
}

_CONTEXT_LENGTH_KEYS = (
    "context_length", "context_window", "max_context_length",
    "max_position_embeddings", "max_model_len", "max_input_tokens",
    "max_sequence_length", "max_seq_len", "n_ctx_train", "n_ctx",
)

_MAX_COMPLETION_KEYS = (
    "max_completion_tokens", "max_output_tokens", "max_tokens",
)

_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")
_CONTAINER_LOCAL_SUFFIXES = (
    ".docker.internal", ".containers.internal", ".lima.internal",
)

_URL_TO_PROVIDER = {
    "api.openai.com": "openai",
    "chatgpt.com": "openai",
    "api.anthropic.com": "anthropic",
    "api.z.ai": "zai",
    "api.moonshot.ai": "kimi-coding",
    "api.moonshot.cn": "kimi-coding-cn",
    "api.kimi.com": "kimi-coding",
    "api.arcee.ai": "arcee",
    "api.minimax": "minimax",
    "dashscope.aliyuncs.com": "alibaba",
    "dashscope-intl.aliyuncs.com": "alibaba",
    "portal.qwen.ai": "qwen-oauth",
    "openrouter.ai": "openrouter",
    "generativelanguage.googleapis.com": "gemini",
    "inference-api.nousresearch.com": "nous",
    "api.deepseek.com": "deepseek",
    "api.githubcopilot.com": "copilot",
    "models.github.ai": "copilot",
    "api.fireworks.ai": "fireworks",
    "opencode.ai": "opencode-go",
    "api.x.ai": "xai",
    "api.xiaomimimo.com": "xiaomi",
    "xiaomimimo.com": "xiaomi",
}

# ============================================================================
# 缓存
# ============================================================================

_model_metadata_cache: Dict[str, Dict[str, Any]] = {}
_model_metadata_cache_time: float = 0
_MODEL_CACHE_TTL = 3600
_endpoint_model_metadata_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
_endpoint_model_metadata_cache_time: Dict[str, float] = {}
_ENDPOINT_MODEL_CACHE_TTL = 300

# ============================================================================
# 工具函数
# ============================================================================

def _normalize_base_url(base_url: str) -> str:
    return (base_url or "").strip().rstrip("/")

def _is_openrouter_base_url(base_url: str) -> bool:
    return "openrouter.ai" in _normalize_base_url(base_url).lower()

def _is_custom_endpoint(base_url: str) -> bool:
    normalized = _normalize_base_url(base_url)
    return bool(normalized) and not _is_openrouter_base_url(normalized)

def _is_known_provider_base_url(base_url: str) -> bool:
    return infer_provider_from_url(base_url) is not None

def _iter_nested_dicts(value: Any):
    """Yield all dicts nested inside *value*, including *value* itself."""
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_nested_dicts(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_nested_dicts(item)

def _coerce_reasonable_int(value: Any, minimum: int = 1024, maximum: int = 10_000_000) -> Optional[int]:
    """Coerce *value* to an int within reasonable bounds, or return None."""
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, str):
            value = value.strip().replace(",", "")
        result = int(value)
    except (TypeError, ValueError):
        return None
    if minimum <= result <= maximum:
        return result
    return None

def _extract_first_int(payload: Dict[str, Any], keys: tuple[str, ...]) -> Optional[int]:
    """Extract first integer found in *payload* for any of *keys* (nested search)."""
    keyset = {key.lower() for key in keys}
    for mapping in _iter_nested_dicts(payload):
        for key, value in mapping.items():
            if str(key).lower() not in keyset:
                continue
            coerced = _coerce_reasonable_int(value)
            if coerced is not None:
                return coerced
    return None

def _extract_context_length(payload: Dict[str, Any]) -> Optional[int]:
    return _extract_first_int(payload, _CONTEXT_LENGTH_KEYS)

def _extract_max_completion_tokens(payload: Dict[str, Any]) -> Optional[int]:
    return _extract_first_int(payload, _MAX_COMPLETION_KEYS)

def _extract_pricing(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract pricing info from model payload, handling various alias formats."""
    alias_map = {
        "prompt": ("prompt", "input", "input_cost_per_token", "prompt_token_cost"),
        "completion": ("completion", "output", "output_cost_per_token", "completion_token_cost"),
        "request": ("request", "request_cost"),
        "cache_read": ("cache_read", "cached_prompt", "input_cache_read", "cache_read_cost_per_token"),
        "cache_write": ("cache_write", "cache_creation", "input_cache_write", "cache_write_cost_per_token"),
    }
    for mapping in _iter_nested_dicts(payload):
        normalized = {str(key).lower(): value for key, value in mapping.items()}
        if not any(any(alias in normalized for alias in aliases) for aliases in alias_map.values()):
            continue
        pricing: Dict[str, Any] = {}
        for target, aliases in alias_map.items():
            for alias in aliases:
                if alias in normalized and normalized[alias] not in (None, ""):
                    pricing[target] = normalized[alias]
                    break
        if pricing:
            return pricing
    return {}

def _add_model_aliases(cache: Dict[str, Dict[str, Any]], model_id: str, entry: Dict[str, Any]) -> None:
    """Add model to cache, plus bare-name alias if slash-separated."""
    cache[model_id] = entry
    if "/" in model_id:
        bare_model = model_id.split("/", 1)[1]
        cache.setdefault(bare_model, entry)

def _model_id_matches(candidate_id: str, lookup_model: str) -> bool:
    """Check if candidate_id matches lookup_model (exact or slug form)."""
    if candidate_id == lookup_model:
        return True
    if "/" in candidate_id and candidate_id.rsplit("/", 1)[1] == lookup_model:
        return True
    return False

def _normalize_model_version(model: str) -> str:
    """Normalize version separators (dots ↔ dashes) for matching."""
    return model.replace(".", "-")

# ============================================================================
# Provider前缀处理
# ============================================================================

def _strip_provider_prefix(model: str) -> str:
    """Strip a recognised provider prefix from a model string.

    ``"local:my-model"`` → ``"my-model"``
    ``"anthropic/claude-opus-4.6"`` → ``"claude-opus-4.6"``
    ``"qwen3.5:27b"``   → ``"qwen3.5:27b"``  (unchanged — not a provider prefix)
    ``"deepseek:latest"``→ ``"deepseek:latest"``(unchanged — Ollama model:tag)
    """
    # Handle "/" separator (e.g. "anthropic/claude-opus-4.6")
    if "/" in model and not model.startswith("http"):
        prefix, suffix = model.split("/", 1)
        if prefix.lower() in _PROVIDER_PREFIXES:
            return suffix
    # Handle ":" separator (e.g. "local:model-name", "deepseek:0.5b")
    if ":" not in model:
        return model
    prefix, suffix = model.split(":", 1)
    prefix_lower = prefix.strip().lower()
    if prefix_lower in _PROVIDER_PREFIXES:
        if _OLLAMA_TAG_PATTERN.match(suffix.strip()):
            return model
        return suffix
    return model

def strip_provider_prefix(model: str) -> str:
    """Public wrapper for _strip_provider_prefix."""
    return _strip_provider_prefix(model)

def infer_provider_from_url(base_url: str) -> Optional[str]:
    """Infer provider name from a base URL."""
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return None
    parsed = urlparse(normalized if "://" in normalized else f"https://{normalized}")
    host = parsed.netloc.lower() or parsed.path.lower()
    for url_part, provider in _URL_TO_PROVIDER.items():
        if url_part in host:
            return provider
    return None

def is_local_endpoint(base_url: str) -> bool:
    """Return True if base_url points to a local machine."""
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return False
    url = normalized if "://" in normalized else f"http://{normalized}"
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
    except Exception:
        return False
    if host in _LOCAL_HOSTS:
        return True
    if any(host.endswith(suffix) for suffix in _CONTAINER_LOCAL_SUFFIXES):
        return True
    import ipaddress
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        pass
    parts = host.split(".")
    if len(parts) == 4:
        try:
            first, second = int(parts[0]), int(parts[1])
            if first == 10:
                return True
            if first == 172 and 16 <= second <= 31:
                return True
            if first == 192 and second == 168:
                return True
        except ValueError:
            pass
    return False

# ============================================================================
# Token估算
# ============================================================================

def estimate_tokens(text: str) -> int:
    """估算文本token数（中英文混合优化）"""
    if not text:
        return 0
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    other_chars = len(text) - chinese_chars - sum(len(w) for w in re.findall(r'[a-zA-Z]+', text))
    estimate = chinese_chars * 2 + english_words * 1.3 + other_chars // 4
    return max(1, int(estimate))

def estimate_messages_tokens(messages: list) -> int:
    """估算消息列表的总token数"""
    total = 0
    for msg in messages:
        total += 4
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    total += estimate_tokens(item.get("text", ""))
                else:
                    total += estimate_tokens(str(item))
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            for tc in tool_calls:
                if isinstance(tc, dict):
                    args = tc.get("function", {}).get("arguments", "")
                    total += estimate_tokens(str(args))
    total += 3
    return total

# ============================================================================
# OpenRouter元数据获取
# ============================================================================

def fetch_model_metadata(force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """Fetch model metadata from OpenRouter (cached for 1 hour)."""
    global _model_metadata_cache, _model_metadata_cache_time

    if not force_refresh and _model_metadata_cache and (time.time() - _model_metadata_cache_time) < _MODEL_CACHE_TTL:
        return _model_metadata_cache

    try:
        response = requests.get(OPENROUTER_MODELS_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        cache: Dict[str, Dict[str, Any]] = {}
        for model in data.get("data", []):
            model_id = model.get("id", "")
            entry = {
                "context_length": model.get("context_length", 128000),
                "max_completion_tokens": model.get("top_provider", {}).get("max_completion_tokens", 4096),
                "name": model.get("name", model_id),
                "pricing": model.get("pricing", {}),
            }
            _add_model_aliases(cache, model_id, entry)
            canonical = model.get("canonical_slug", "")
            if canonical and canonical != model_id:
                _add_model_aliases(cache, canonical, entry)

        _model_metadata_cache = cache
        _model_metadata_cache_time = time.time()
        logger.debug("Fetched metadata for %s models from OpenRouter", len(cache))
        return cache

    except Exception as e:
        logging.warning(f"Failed to fetch model metadata from OpenRouter: {e}")
        return _model_metadata_cache or {}

# ============================================================================
# Endpoint元数据获取
# ============================================================================

def fetch_endpoint_model_metadata(
    base_url: str,
    api_key: str = "",
    force_refresh: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Fetch model metadata from an OpenAI-compatible /models endpoint."""
    normalized = _normalize_base_url(base_url)
    if not normalized or _is_openrouter_base_url(normalized):
        return {}

    if not force_refresh:
        cached = _endpoint_model_metadata_cache.get(normalized)
        cached_at = _endpoint_model_metadata_cache_time.get(normalized, 0)
        if cached is not None and (time.time() - cached_at) < _ENDPOINT_MODEL_CACHE_TTL:
            return cached

    candidates = [normalized]
    if normalized.endswith("/v1"):
        alternate = normalized[:-3].rstrip("/")
    else:
        alternate = normalized + "/v1"
    if alternate and alternate not in candidates:
        candidates.append(alternate)

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    last_error: Optional[Exception] = None

    for candidate in candidates:
        url = candidate.rstrip("/") + "/models"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            payload = response.json()
            cache: Dict[str, Dict[str, Any]] = {}
            for model in payload.get("data", []):
                if not isinstance(model, dict):
                    continue
                model_id = model.get("id")
                if not model_id:
                    continue
                entry: Dict[str, Any] = {"name": model.get("name", model_id)}
                context_length = _extract_context_length(model)
                if context_length is not None:
                    entry["context_length"] = context_length
                max_completion_tokens = _extract_max_completion_tokens(model)
                if max_completion_tokens is not None:
                    entry["max_completion_tokens"] = max_completion_tokens
                pricing = _extract_pricing(model)
                if pricing:
                    entry["pricing"] = pricing
                _add_model_aliases(cache, model_id, entry)

            # llama.cpp: query /props for actual allocated context
            is_llamacpp = any(
                m.get("owned_by") == "llamacpp"
                for m in payload.get("data", []) if isinstance(m, dict)
            )
            if is_llamacpp:
                try:
                    base = candidate.rstrip("/").replace("/v1", "")
                    props_resp = requests.get(base + "/v1/props", headers=headers, timeout=5)
                    if not props_resp.ok:
                        props_resp = requests.get(base + "/props", headers=headers, timeout=5)
                    if props_resp.ok:
                        props = props_resp.json()
                        gen_settings = props.get("default_generation_settings", {})
                        n_ctx = gen_settings.get("n_ctx")
                        model_alias = props.get("model_alias", "")
                        if n_ctx and model_alias and model_alias in cache:
                            cache[model_alias]["context_length"] = n_ctx
                except Exception:
                    pass

            _endpoint_model_metadata_cache[normalized] = cache
            _endpoint_model_metadata_cache_time[normalized] = time.time()
            return cache
        except Exception as exc:
            last_error = exc

    if last_error:
        logger.debug("Failed to fetch model metadata from %s/models: %s", normalized, last_error)
    _endpoint_model_metadata_cache[normalized] = {}
    _endpoint_model_metadata_cache_time[normalized] = time.time()
    return {}

# ============================================================================
# 持久化缓存
# ============================================================================

def _get_context_cache_path() -> Path:
    """Return path to the persistent context length cache file."""
    from mimiraether_constants import get_mimiraether_home
    return get_mimiraether_home() / "context_length_cache.yaml"

def _load_context_cache() -> Dict[str, int]:
    """Load the model+provider -> context_length cache from disk."""
    path = _get_context_cache_path()
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("context_lengths", {})
    except Exception as e:
        logger.debug("Failed to load context length cache: %s", e)
        return {}

def save_context_length(model: str, base_url: str, length: int) -> None:
    """Persist a discovered context length for a model+provider combo."""
    key = f"{model}@{base_url}"
    cache = _load_context_cache()
    if cache.get(key) == length:
        return  # already stored
    cache[key] = length
    path = _get_context_cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump({"context_lengths": cache}, f, default_flow_style=False)
        logger.info("Cached context length %s -> %s tokens", key, f"{length:,}")
    except Exception as e:
        logger.debug("Failed to save context length cache: %s", e)

def get_cached_context_length(model: str, base_url: str) -> Optional[int]:
    """Look up a previously discovered context length for model+provider."""
    key = f"{model}@{base_url}"
    cache = _load_context_cache()
    return cache.get(key)

# ============================================================================
# 本地服务器探测
# ============================================================================

def detect_local_server_type(base_url: str) -> Optional[str]:
    """Detect which local server is running at base_url."""
    import httpx

    normalized = _normalize_base_url(base_url)
    server_url = normalized
    if server_url.endswith("/v1"):
        server_url = server_url[:-3]

    try:
        with httpx.Client(timeout=2.0) as client:
            # LM Studio
            try:
                r = client.get(f"{server_url}/api/v1/models")
                if r.status_code == 200:
                    return "lm-studio"
            except Exception:
                pass
            # Ollama
            try:
                r = client.get(f"{server_url}/api/tags")
                if r.status_code == 200:
                    try:
                        data = r.json()
                        if "models" in data:
                            return "ollama"
                    except Exception:
                        pass
            except Exception:
                pass
            # llama.cpp
            try:
                r = client.get(f"{server_url}/v1/props")
                if r.status_code != 200:
                    r = client.get(f"{server_url}/props")
                if r.status_code == 200 and "default_generation_settings" in r.text:
                    return "llamacpp"
            except Exception:
                pass
            # vLLM
            try:
                r = client.get(f"{server_url}/version")
                if r.status_code == 200:
                    data = r.json()
                    if "version" in data:
                        return "vllm"
            except Exception:
                pass
    except Exception:
        pass

    return None

def query_ollama_num_ctx(model: str, base_url: str) -> Optional[int]:
    """Query Ollama server for model's num_ctx from GGUF metadata via /api/show."""
    import httpx

    bare_model = _strip_provider_prefix(model)
    server_url = base_url.rstrip("/")
    if server_url.endswith("/v1"):
        server_url = server_url[:-3]

    try:
        server_type = detect_local_server_type(base_url)
    except Exception:
        return None
    if server_type != "ollama":
        return None

    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.post(f"{server_url}/api/show", json={"name": bare_model})
            if resp.status_code != 200:
                return None
            data = resp.json()

            # Prefer explicit num_ctx from Modelfile parameters
            params = data.get("parameters", "")
            if "num_ctx" in params:
                for line in params.split("\n"):
                    if "num_ctx" in line:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            try:
                                return int(parts[-1])
                            except ValueError:
                                pass

            # Fall back to GGUF model_info context_length
            model_info = data.get("model_info", {})
            for key, value in model_info.items():
                if "context_length" in key and isinstance(value, (int, float)):
                    return int(value)
    except Exception:
        pass
    return None

def _query_local_context_length(model: str, base_url: str) -> Optional[int]:
    """Query a local server for the model's context length."""
    import httpx

    model = _strip_provider_prefix(model)
    server_url = base_url.rstrip("/")
    if server_url.endswith("/v1"):
        server_url = server_url[:-3]

    try:
        server_type = detect_local_server_type(base_url)
    except Exception:
        server_type = None

    try:
        with httpx.Client(timeout=3.0) as client:
            if server_type == "ollama":
                resp = client.post(f"{server_url}/api/show", json={"name": model})
                if resp.status_code == 200:
                    data = resp.json()
                    params = data.get("parameters", "")
                    if "num_ctx" in params:
                        for line in params.split("\n"):
                            if "num_ctx" in line:
                                parts = line.strip().split()
                                if len(parts) >= 2:
                                    try:
                                        return int(parts[-1])
                                    except ValueError:
                                        pass
                    model_info = data.get("model_info", {})
                    for key, value in model_info.items():
                        if "context_length" in key and isinstance(value, (int, float)):
                            return int(value)

            if server_type == "lm-studio":
                resp = client.get(f"{server_url}/api/v1/models")
                if resp.status_code == 200:
                    data = resp.json()
                    for m in data.get("models", []):
                        if _model_id_matches(m.get("key", ""), model) or _model_id_matches(m.get("id", ""), model):
                            for inst in m.get("loaded_instances", []):
                                cfg = inst.get("config", {})
                                ctx = cfg.get("context_length")
                                if ctx and isinstance(ctx, (int, float)):
                                    return int(ctx)
                            ctx = m.get("max_context_length") or m.get("context_length")
                            if ctx and isinstance(ctx, (int, float)):
                                return int(ctx)

            # Try /v1/models/{model}
            resp = client.get(f"{server_url}/v1/models/{model}")
            if resp.status_code == 200:
                data = resp.json()
                ctx = data.get("max_model_len") or data.get("context_length") or data.get("max_tokens")
                if ctx and isinstance(ctx, (int, float)):
                    return int(ctx)

            # Try /v1/models list
            resp = client.get(f"{server_url}/v1/models")
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    if _model_id_matches(m.get("id", ""), model):
                        ctx = m.get("max_model_len") or m.get("context_length") or m.get("max_tokens")
                        if ctx and isinstance(ctx, (int, float)):
                            return int(ctx)
    except Exception:
        pass

    return None

def query_local_context_length(model: str, base_url: str) -> Optional[int]:
    """Public wrapper for _query_local_context_length."""
    return _query_local_context_length(model, base_url)

# ============================================================================
# 远程API查询
# ============================================================================

def _query_anthropic_context_length(model: str, base_url: str, api_key: str) -> Optional[int]:
    """Query Anthropic /v1/models for context length (API key only, not OAuth)."""
    if not api_key or api_key.startswith("sk-ant-oat"):
        return None
    try:
        base = base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        url = f"{base}/v1/models?limit=1000"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        for m in data.get("data", []):
            if m.get("id") == model:
                ctx = m.get("max_input_tokens")
                if isinstance(ctx, int) and ctx > 0:
                    return ctx
    except Exception as e:
        logger.debug("Anthropic /v1/models query failed: %s", e)
    return None

def _resolve_nous_context_length(model: str) -> Optional[int]:
    """Resolve Nous model context length via OpenRouter metadata with suffix matching."""
    metadata = fetch_model_metadata()
    if model in metadata:
        return metadata[model].get("context_length")

    normalized = _normalize_model_version(model).lower()

    for or_id, entry in metadata.items():
        bare = or_id.split("/", 1)[1] if "/" in or_id else or_id
        if bare.lower() == model.lower() or _normalize_model_version(bare).lower() == normalized:
            return entry.get("context_length")

    # Partial prefix match for preview models
    model_lower = model.lower()
    for or_id, entry in metadata.items():
        bare = or_id.split("/", 1)[1] if "/" in or_id else or_id
        for candidate, query in [(bare.lower(), model_lower), (_normalize_model_version(bare).lower(), normalized)]:
            if candidate.startswith(query) and (
                len(candidate) == len(query) or candidate[len(query)] in "-:."
            ):
                return entry.get("context_length")

    return None

def query_remote_context_length(model: str, base_url: str, api_key: str) -> Optional[int]:
    """Query remote API for model context length."""
    normalized = (base_url or "").strip().rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]

    if "api.anthropic.com" in normalized:
        return _query_anthropic_context_length(model, normalized, api_key)

    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        url = f"{normalized}/v1/models/{model}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            ctx = _extract_context_length(data)
            if ctx:
                return ctx
            if "max_model_len" in data:
                return int(data["max_model_len"])
    except Exception:
        pass

    return None

# ============================================================================
# 主查询函数
# ============================================================================

def get_model_context_length(
    model: str,
    base_url: str = "",
    api_key: str = "",
    config_context_length: int = None,
    provider: str = "",
) -> int:
    """Get the context length for a model.

    Resolution order:
    0. Explicit config override
    1. Persistent cache (previously discovered via probing)
    2. Active endpoint metadata (for truly custom/unknown endpoints)
    3. Local server query
    4. Anthropic /v1/models API
    5. Provider-aware via models.dev + nous suffix-match
    6. OpenRouter live API metadata (provider-unaware fallback)
    7. Hardcoded defaults (fuzzy match, longest key first)
    8. Local server as last resort
    9. Default fallback (128K)
    """
    # 0. Explicit config override
    if config_context_length is not None and isinstance(config_context_length, int) and config_context_length > 0:
        return config_context_length

    model = _strip_provider_prefix(model)

    # 1. Persistent cache
    if base_url:
        cached = get_cached_context_length(model, base_url)
        if cached is not None:
            return cached

    # 2. Active endpoint metadata for truly custom endpoints
    if _is_custom_endpoint(base_url) and not _is_known_provider_base_url(base_url):
        endpoint_metadata = fetch_endpoint_model_metadata(base_url, api_key=api_key)
        matched = endpoint_metadata.get(model)
        if not matched:
            if len(endpoint_metadata) == 1:
                matched = next(iter(endpoint_metadata.values()))
            else:
                for key, entry in endpoint_metadata.items():
                    if model in key or key in model:
                        matched = entry
                        break
        if matched:
            context_length = matched.get("context_length")
            if isinstance(context_length, int):
                return context_length
        if not _is_known_provider_base_url(base_url):
            if is_local_endpoint(base_url):
                local_ctx = _query_local_context_length(model, base_url)
                if local_ctx and local_ctx > 0:
                    save_context_length(model, base_url, local_ctx)
                    return local_ctx
            logger.info(
                "Could not detect context length for model %r at %s — "
                "defaulting to %s tokens (probe-down).",
                model, base_url, f"{DEFAULT_FALLBACK_CONTEXT:,}",
            )
            return DEFAULT_FALLBACK_CONTEXT

    # 3. Anthropic /v1/models API
    if provider == "anthropic" or (base_url and "api.anthropic.com" in base_url):
        ctx = _query_anthropic_context_length(model, base_url or "https://api.anthropic.com", api_key)
        if ctx:
            return ctx

    # 4. Provider-aware lookups before generic OR cache
    effective_provider = provider
    if not effective_provider or effective_provider in ("openrouter", "custom"):
        if base_url:
            inferred = infer_provider_from_url(base_url)
            if inferred:
                effective_provider = inferred

    if effective_provider == "nous":
        ctx = _resolve_nous_context_length(model)
        if ctx:
            return ctx
    if effective_provider:
        from agent.models_dev import lookup_models_dev_context
        ctx = lookup_models_dev_context(effective_provider, model)
        if ctx:
            return ctx

    # 6. OpenRouter live API metadata (provider-unaware fallback)
    metadata = fetch_model_metadata()
    if model in metadata:
        return metadata[model].get("context_length", 128000)

    # 7. Hardcoded defaults (longest key first for specificity)
    model_lower = model.lower()
    for default_model, length in sorted(DEFAULT_CONTEXT_LENGTHS.items(), key=lambda x: len(x[0]), reverse=True):
        if default_model in model_lower:
            return length

    # 8. Local server as last resort
    if base_url and is_local_endpoint(base_url):
        local_ctx = _query_local_context_length(model, base_url)
        if local_ctx and local_ctx > 0:
            save_context_length(model, base_url, local_ctx)
            return local_ctx

    # 9. Default fallback — 128K
    return DEFAULT_FALLBACK_CONTEXT

def lookup_default_context_length(model: str) -> Optional[int]:
    """从默认表查找上下文长度"""
    model_lower = model.lower()
    for key, length in DEFAULT_CONTEXT_LENGTHS.items():
        if key.lower() == model_lower:
            return length
    sorted_keys = sorted(DEFAULT_CONTEXT_LENGTHS.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key.lower() in model_lower:
            return DEFAULT_CONTEXT_LENGTHS[key]
    return None

# ============================================================================
# Token估算（Hermès兼容）
# ============================================================================

def estimate_tokens_rough(text: str) -> int:
    """Rough token estimate (~4 chars/token) for pre-flight checks."""
    if not text:
        return 0
    return (len(text) + 3) // 4

def estimate_messages_tokens_rough(messages: List[Dict[str, Any]]) -> int:
    """Rough token estimate for a message list (pre-flight only)."""
    total_chars = sum(len(str(msg)) for msg in messages)
    return (total_chars + 3) // 4

def estimate_request_tokens_rough(
    messages: List[Dict[str, Any]],
    *,
    system_prompt: str = "",
    tools: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """Rough token estimate for a full chat-completions request."""
    total_chars = 0
    if system_prompt:
        total_chars += len(system_prompt)
    if messages:
        total_chars += sum(len(str(msg)) for msg in messages)
    if tools:
        total_chars += len(str(tools))
    return (total_chars + 3) // 4

# ============================================================================
# 错误解析
# ============================================================================

def parse_context_limit_from_error(error_msg: str) -> Optional[int]:
    """Extract context limit from an API error message."""
    error_lower = error_msg.lower()
    patterns = [
        r'(?:max(?:imum)?|limit)\s*(?:context\s*)?(?:length|size|window)?\s*(?:is|of|:)?\s*(\d{4,})',
        r'context\s*(?:length|size|window)\s*(?:is|of|:)?\s*(\d{4,})',
        r'(\d{4,})\s*(?:token)?\s*(?:context|limit)',
        r'>\s*(\d{4,})\s*(?:max|limit|token)',
        r'(\d{4,})\s*(?:max(?:imum)?)\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, error_lower)
        if match:
            limit = int(match.group(1))
            if 1024 <= limit <= 10_000_000:
                return limit
    return None

def parse_available_output_tokens_from_error(error_msg: str) -> Optional[int]:
    """Detect an 'output cap too large' error and return available output tokens."""
    error_lower = error_msg.lower()
    is_output_cap_error = (
        "max_tokens" in error_lower
        and ("available_tokens" in error_lower or "available tokens" in error_lower)
    )
    if not is_output_cap_error:
        return None
    patterns = [
        r'available_tokens[:\s]+(\d+)',
        r'available\s+tokens[:\s]+(\d+)',
        r'=\s*(\d+)\s*$',
    ]
    for pattern in patterns:
        match = re.search(pattern, error_lower)
        if match:
            tokens = int(match.group(1))
            if tokens >= 1:
                return tokens
    return None

def get_next_probe_tier(current_length: int) -> Optional[int]:
    """Return the next lower probe tier, or None if already at minimum."""
    for tier in CONTEXT_PROBE_TIERS:
        if tier < current_length:
            return tier
    return None

# ============================================================================
# Hermès兼容别名（已在上方实现）
# ============================================================================

# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("=" * 60)
    print("MimirAether Model Metadata 测试")
    print("=" * 60)

    # 测试1: Provider前缀分离
    print("\n[测试1] Provider前缀分离")
    test_cases = [
        ("anthropic/claude-opus-4.6", "claude-opus-4.6"),
        ("local:my-model", "my-model"),
        ("qwen3.5:27b", "qwen3.5:27b"),
        ("deepseek/deepseek-chat", "deepseek-chat"),
    ]
    for input_model, expected in test_cases:
        result = strip_provider_prefix(input_model)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_model}' → '{result}' (expected: '{expected}')")

    # 测试2: Token估算
    print("\n[测试2] Token估算")
    test_texts = [
        "Hello, world!",
        "你好，世界！",
        "这是一个测试用例。" * 10,
    ]
    for text in test_texts:
        tokens = estimate_tokens(text)
        print(f"  '{text[:30]}...' → {tokens} tokens")

    # 测试3: 上下文长度查询
    print("\n[测试3] 上下文长度查询")
    models = ["claude-opus-4.6", "gpt-4", "deepseek-chat", "unknown-model"]
    for model in models:
        ctx = get_model_context_length(model)
        print(f"  {model}: {ctx:,} tokens")

    # 测试4: 本地端点检测
    print("\n[测试4] 本地端点检测")
    urls = ["http://localhost:8000", "http://127.0.0.1:11434", "https://api.openai.com"]
    for url in urls:
        is_local = is_local_endpoint(url)
        print(f"  {url}: {'local' if is_local else 'remote'}")

    # 测试5: Provider推断
    print("\n[测试5] Provider推断")
    urls = [
        "https://api.anthropic.com",
        "https://api.deepseek.com",
        "https://api.moonshot.ai",
    ]
    for url in urls:
        provider = infer_provider_from_url(url)
        print(f"  {url}: {provider}")

    # 测试6: 错误解析
    print("\n[测试6] 错误解析")
    errors = [
        "maximum context length is 32768 tokens",
        "context_length_exceeded: 131072",
        "max_tokens: 32768 > context_window: 200000 - input_tokens: 190000 = available_tokens: 10000",
    ]
    for error in errors:
        ctx = parse_context_limit_from_error(error)
        output = parse_available_output_tokens_from_error(error)
        print(f"  Error: {error[:50]}...")
        if ctx:
            print(f"    Context limit: {ctx:,}")
        if output:
            print(f"    Available output: {output:,}")

    # 测试7: OpenRouter元数据（需要网络）
    print("\n[测试7] OpenRouter元数据获取")
    metadata = fetch_model_metadata()
    print(f"  Fetched {len(metadata)} models from OpenRouter")

    # 测试8: _iter_nested_dicts
    print("\n[测试8] 嵌套字典遍历")
    nested = {"a": 1, "b": {"c": 2, "d": [3, {"e": 4}]}}
    dicts = list(_iter_nested_dicts(nested))
    print(f"  Found {len(dicts)} dicts in nested structure")

    # 测试9: _coerce_reasonable_int
    print("\n[测试9] 整数强制转换")
    test_vals = [100, "200", "1,000", None, True, 5, 20000000]
    for v in test_vals:
        result = _coerce_reasonable_int(v)
        print(f"  {repr(v)} → {result}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
