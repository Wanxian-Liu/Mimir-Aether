"""
MimarAether Model Metadata

学习自Hermes model_metadata设计思路：
- 模型上下文长度查询
- Token估算
- 提供商前缀处理
- 模型探测

核心原则：
- 不复制代码，独立实现
- 保持API兼容
- 适配MimarAether框架
"""

import logging
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

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

# Ollama tag模式
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
    # Anthropic Claude
    "claude-opus-4-6": 1000000,
    "claude-sonnet-4-6": 1000000,
    "claude-opus-4.6": 1000000,
    "claude-sonnet-4.6": 1000000,
    "claude": 200000,
    # OpenAI
    "gpt-4.1": 1047576,
    "gpt-4": 128000,
    # Google
    "gemini": 1048576,
    # DeepSeek
    "deepseek": 128000,
    # Qwen
    "qwen3-coder-plus": 1000000,
    "qwen3-coder": 262144,
    "qwen": 131072,
    # MiniMax
    "minimax": 204800,
    # GLM
    "glm": 202752,
    # Kimi
    "kimi": 262144,
    # Grok
    "grok-4-1-fast": 2000000,
    "grok-4-fast": 2000000,
    "grok-4.20": 2000000,
    "grok-4": 256000,
    "grok": 131072,
    # Llama
    "llama": 131072,
    # Gemma
    "gemma": 8192,
}

# Context长度字段映射
_CONTEXT_LENGTH_KEYS = (
    "context_length", "context_window", "max_context_length",
    "max_position_embeddings", "max_model_len", "max_input_tokens",
    "max_sequence_length", "max_seq_len", "n_ctx_train", "n_ctx",
)

# 最大输出token字段
_MAX_COMPLETION_KEYS = (
    "max_completion_tokens", "max_output_tokens", "max_tokens",
)

# 本地服务器
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")
_CONTAINER_LOCAL_SUFFIXES = (
    ".docker.internal", ".containers.internal", ".lima.internal",
)

# URL到Provider映射
_URL_TO_PROVIDER = {
    "api.openai.com": "openai",
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


# ============================================================================
# Provider前缀处理
# ============================================================================

def strip_provider_prefix(model: str) -> str:
    """
    分离Provider前缀
    
    "anthropic/claude-opus-4.6" → "claude-opus-4.6"
    "local:my-model" → "my-model"
    "qwen3.5:27b" → "qwen3.5:27b" (保留Ollama tag)
    "deepseek/deepseek-chat" → "deepseek-chat"
    """
    # 处理 "/" 分隔符
    if "/" in model and not model.startswith("http"):
        parts = model.split("/")
        if len(parts) == 2:
            prefix, suffix = parts
            prefix_lower = prefix.strip().lower()
            if prefix_lower in _PROVIDER_PREFIXES:
                return suffix.strip()
    
    # 处理 ":" 分隔符
    if ":" in model and not model.startswith("http"):
        prefix, suffix = model.split(":", 1)
        prefix_lower = prefix.strip().lower()
        
        if prefix_lower in _PROVIDER_PREFIXES:
            # 保留Ollama tag格式
            if _OLLAMA_TAG_PATTERN.match(suffix.strip()):
                return model
            return suffix
    
    return model


def infer_provider_from_url(base_url: str) -> Optional[str]:
    """从base URL推断provider"""
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        return None
    
    parsed = urlparse(normalized if "://" in normalized else f"https://{normalized}")
    host = parsed.netloc.lower() or parsed.path.lower()
    
    for url_part, provider in _URL_TO_PROVIDER.items():
        if url_part in host:
            return provider
    
    return None


def is_local_endpoint(base_url: str) -> bool:
    """检查是否为本地端点"""
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        return False
    
    url = normalized if "://" in normalized else f"http://{normalized}"
    
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        
        if host in _LOCAL_HOSTS:
            return True
        
        # Docker/Podman/Lima DNS
        if any(host.endswith(suffix) for suffix in _CONTAINER_LOCAL_SUFFIXES):
            return True
        
        # RFC-1918私有IP检测
        import ipaddress
        try:
            addr = ipaddress.ip_address(host)
            return addr.is_private or addr.is_loopback or addr.is_link_local
        except ValueError:
            pass
        
        # 私有IP模式匹配
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
    
    except Exception:
        pass
    
    return False


# ============================================================================
# Token估算
# ============================================================================

def estimate_tokens(text: str) -> int:
    """
    估算文本token数
    
    简化版：中文按字符估算，英文按单词估算
    """
    if not text:
        return 0
    
    # 中文字符
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    
    # 英文单词
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    
    # 其他字符
    other_chars = len(text) - chinese_chars - sum(len(w) for w in re.findall(r'[a-zA-Z]+', text))
    
    # 估算：中文≈2 token/字符，英文≈1.3 token/词，其他≈1 token/4字符
    estimate = chinese_chars * 2 + english_words * 1.3 + other_chars // 4
    
    return max(1, int(estimate))


def estimate_messages_tokens(messages: list) -> int:
    """估算消息列表的总token数"""
    total = 0
    for msg in messages:
        # Role开销
        total += 4
        # Content
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    total += estimate_tokens(item.get("text", ""))
                else:
                    total += estimate_tokens(str(item))
        # Tool calls
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            for tc in tool_calls:
                if isinstance(tc, dict):
                    args = tc.get("function", {}).get("arguments", "")
                    total += estimate_tokens(str(args))
    # Assistant消息额外开销
    total += 3
    return total


# ============================================================================
# 模型上下文长度
# ============================================================================

def get_model_context_length(
    model: str,
    base_url: str = "",
    api_key: str = "",
    config_context_length: int = None,
    provider: str = "",
) -> int:
    """
    获取模型上下文长度
    
    优先级：
    1. 显式配置（用户指定，最优先）
    2. 缓存（之前探测的结果）
    3. 本地服务器查询
    4. 远程API查询
    5. 默认表查找
    6. 默认兜底值
    """
    # 0. 显式配置
    if config_context_length and config_context_length > 0:
        return config_context_length
    
    # 分离前缀
    bare_model = strip_provider_prefix(model)
    
    # 1. 尝试从缓存获取
    if base_url:
        cached = get_cached_context_length(bare_model, base_url)
        if cached:
            return cached
    
    # 2. 本地服务器
    if is_local_endpoint(base_url):
        local_ctx = query_local_context_length(bare_model, base_url)
        if local_ctx:
            save_context_length(bare_model, base_url, local_ctx)
            return local_ctx
    
    # 3. 远程API查询
    if api_key:
        remote_ctx = query_remote_context_length(bare_model, base_url, api_key)
        if remote_ctx:
            save_context_length(bare_model, base_url, remote_ctx)
            return remote_ctx
    
    # 4. 默认表查找
    ctx = lookup_default_context_length(bare_model)
    if ctx:
        return ctx
    
    # 5. 兜底值
    return DEFAULT_FALLBACK_CONTEXT


def lookup_default_context_length(model: str) -> Optional[int]:
    """从默认表查找上下文长度"""
    model_lower = model.lower()
    
    # 精确匹配
    for key, length in DEFAULT_CONTEXT_LENGTHS.items():
        if key.lower() == model_lower:
            return length
    
    # 前缀匹配（从长到短排序）
    sorted_keys = sorted(DEFAULT_CONTEXT_LENGTHS.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key.lower() in model_lower:
            return DEFAULT_CONTEXT_LENGTHS[key]
    
    return None


def query_local_context_length(model: str, base_url: str) -> Optional[int]:
    """查询本地服务器的上下文长度"""
    import httpx
    
    bare_model = strip_provider_prefix(model)
    server_url = base_url.rstrip("/")
    if server_url.endswith("/v1"):
        server_url = server_url[:-3]
    
    server_type = detect_local_server_type(base_url)
    
    try:
        with httpx.Client(timeout=3.0) as client:
            # Ollama
            if server_type == "ollama":
                resp = client.post(f"{server_url}/api/show", json={"name": bare_model})
                if resp.status_code == 200:
                    data = resp.json()
                    # 优先使用Modelfile中的num_ctx
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
                    # 回退到GGUF元数据
                    model_info = data.get("model_info", {})
                    for key, value in model_info.items():
                        if "context_length" in key and isinstance(value, (int, float)):
                            return int(value)
            
            # LM Studio
            if server_type == "lm-studio":
                resp = client.get(f"{server_url}/api/v1/models")
                if resp.status_code == 200:
                    data = resp.json()
                    for m in data.get("models", []):
                        if _model_matches(m.get("key", ""), bare_model) or _model_matches(m.get("id", ""), bare_model):
                            for inst in m.get("loaded_instances", []):
                                cfg = inst.get("config", {})
                                ctx = cfg.get("context_length")
                                if ctx:
                                    return int(ctx)
                            ctx = m.get("max_context_length") or m.get("context_length")
                            if ctx:
                                return int(ctx)
    
    except Exception as e:
        logger.debug(f"Local context query failed: {e}")
    
    return None


def detect_local_server_type(base_url: str) -> Optional[str]:
    """检测本地服务器类型"""
    import httpx
    
    normalized = (base_url or "").strip().rstrip("/")
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
                    data = r.json()
                    if "models" in data:
                        return "ollama"
            except Exception:
                pass
            
            # llama.cpp
            try:
                r = client.get(f"{server_url}/v1/props")
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


def query_remote_context_length(model: str, base_url: str, api_key: str) -> Optional[int]:
    """查询远程API的上下文长度"""
    import requests
    
    normalized = (base_url or "").strip().rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]
    
    # Anthropic特殊处理
    if "api.anthropic.com" in normalized:
        return _query_anthropic_context_length(model, normalized, api_key)
    
    # OpenAI兼容端点
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        url = f"{normalized}/v1/models/{model}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for key in _CONTEXT_LENGTH_KEYS:
                if key in data:
                    val = data[key]
                    if isinstance(val, int) and val > 0:
                        return val
            # 尝试从嵌套结构获取
            if "max_model_len" in data:
                return int(data["max_model_len"])
    except Exception:
        pass
    
    return None


def _query_anthropic_context_length(model: str, base_url: str, api_key: str) -> Optional[int]:
    """查询Anthropic API的上下文长度"""
    try:
        url = f"{base_url}/v1/models?limit=1000"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for m in data.get("data", []):
                if m.get("id") == model:
                    ctx = m.get("max_input_tokens")
                    if isinstance(ctx, int) and ctx > 0:
                        return ctx
    except Exception:
        pass
    return None


def _model_matches(candidate_id: str, lookup_model: str) -> bool:
    """检查模型ID是否匹配"""
    if candidate_id == lookup_model:
        return True
    if "/" in candidate_id and candidate_id.rsplit("/", 1)[1] == lookup_model:
        return True
    return False


# ============================================================================
# 缓存管理
# ============================================================================

_context_cache: Dict[str, int] = {}


def get_cached_context_length(model: str, base_url: str) -> Optional[int]:
    """获取缓存的上下文长度"""
    key = f"{model}@{base_url}"
    return _context_cache.get(key)


def save_context_length(model: str, base_url: str, length: int) -> None:
    """保存上下文长度到缓存"""
    key = f"{model}@{base_url}"
    _context_cache[key] = length
    logger.info(f"Cached context length: {model}@{base_url} = {length}")


# ============================================================================
# 错误解析
# ============================================================================

def parse_context_limit_from_error(error_msg: str) -> Optional[int]:
    """从错误消息中提取上下文限制"""
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
    """从错误消息中提取可用输出token数"""
    error_lower = error_msg.lower()
    
    if "max_tokens" not in error_lower:
        return None
    if "available_tokens" not in error_lower and "available tokens" not in error_lower:
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


# ============================================================================
# 便捷函数
# ============================================================================

def get_next_probe_tier(current_length: int) -> Optional[int]:
    """获取下一个探测层级"""
    for tier in CONTEXT_PROBE_TIERS:
        if tier < current_length:
            return tier
    return None


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    print("=" * 60)
    print("MimarAether Model Metadata 测试")
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
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)