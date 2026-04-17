"""
MimirAether Auxiliary Client

向Hermes对齐的多Provider路由客户端。

支持Provider（按优先级）：
1. DeepSeek（已有）
2. Anthropic（新增）
3. MiniMax（新增）
4. OpenAI兼容（新增）

核心功能：
- async_call_llm: 异步LLM调用
- resolve_provider_client: Provider路由解析
- extract_content_or_reasoning: 响应提取
"""

import os
import json
import logging
import asyncio
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# 凭证池集成（学习自Hermes）
# ============================================================================

def _load_credential_pool(provider: str):
    """加载指定Provider的凭证池"""
    try:
        from agent.credential_pool import load_pool, STATUS_OK
        pool = load_pool(provider)
        if pool and pool.has_credentials():
            entry = pool.select()
            if entry:
                return entry
    except Exception as e:
        logger.debug(f"Could not load credential pool for {provider}: {e}")
    return None


def _get_credential_api_key(provider: str) -> Optional[str]:
    """从凭证池获取API Key"""
    entry = _load_credential_pool(provider)
    if entry:
        # PooledCredential.runtime_api_key 或 access_token
        return getattr(entry, 'runtime_api_key', None) or getattr(entry, 'access_token', None)
    return None


# ============================================================================
# Provider配置
# ============================================================================

PROVIDER_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "anthropic": "https://api.anthropic.com",
    "minimax": "https://api.minimax.chat",
    "openai": "https://api.openai.com",
    "moonshot": "https://api.moonshot.cn",
    "openrouter": "https://openrouter.ai/api/v1",
}

PROVIDER_MODELS = {
    "deepseek": "deepseek-chat",
    "anthropic": "claude-3-5-haiku-20241022",
    "minimax": "MiniMax-M2.7",
    "openai": "gpt-4o-mini",
    "moonshot": "moonshot-v1-8k",
}

# ============================================================================
# HTTP客户端管理
# ============================================================================

_http_client: Optional[Any] = None


async def get_http_client():
    """获取或创建全局HTTP客户端"""
    global _http_client
    if _http_client is None:
        import aiohttp
        _http_client = aiohttp.ClientSession()
    return _http_client


async def close_client():
    """关闭HTTP客户端"""
    global _http_client
    if _http_client:
        await _http_client.close()
        _http_client = None


# ============================================================================
# Provider路由（学习自Hermes）
# ============================================================================

def _normalize_provider(provider: str) -> str:
    """规范化Provider名称"""
    aliases = {
        "google": "openai",  # Gemini通过OpenAI兼容API
        "gemini": "openai",
        "claude": "anthropic",
        "kimi": "moonshot",
        "moonshot": "moonshot",
    }
    return aliases.get(provider.lower(), provider.lower())


def _resolve_provider_config(provider: str) -> Tuple[str, str, str]:
    """
    解析Provider配置（优先从凭证池获取）
    
    Returns:
        (base_url, api_key, model)
    """
    provider = _normalize_provider(provider)
    
    # 优先从凭证池获取
    api_key = _get_credential_api_key(provider)
    
    # 如果凭证池没有，从环境变量获取
    if not api_key:
        api_key_map = {
            "deepseek": "DEEPSEEK_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "minimax": "MINIMAX_API_KEY",
            "openai": "OPENAI_API_KEY",
            "moonshot": "MOONSHOT_API_KEY",
        }
        env_var = api_key_map.get(provider, "DEEPSEEK_API_KEY")
        api_key = os.environ.get(env_var, "").strip()
    
    # 如果没找到，尝试DeepSeek作为fallback
    if not api_key:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        provider = "deepseek"
    
    base_url = PROVIDER_BASE_URLS.get(provider, PROVIDER_BASE_URLS["deepseek"])
    model = PROVIDER_MODELS.get(provider, PROVIDER_MODELS["deepseek"])
    
    return base_url, api_key, model


# ============================================================================
# 核心LLM调用
# ============================================================================

async def async_call_llm(
    prompt: str,
    model: str = "deepseek-chat",
    system_prompt: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    provider: str = "auto",
    **kwargs
) -> str:
    """
    异步调用LLM（支持多Provider）
    
    Args:
        prompt: 用户提示
        model: 模型名称
        system_prompt: 系统提示（可选）
        max_tokens: 最大生成token数
        temperature: 温度参数
        provider: Provider选择（auto/deepseek/anthropic/minimax/openai/moonshot）
        **kwargs: 其他参数
    
    Returns:
        模型生成的文本内容
    """
    # 自动选择Provider
    if provider == "auto":
        provider = _detect_provider(model)
    
    base_url, api_key, effective_model = _resolve_provider_config(provider)
    
    if not api_key:
        raise ValueError(f"No API key found for provider: {provider}")
    
    # 构建消息
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    # 根据Provider选择API格式
    if provider == "anthropic":
        return await _call_anthropic(
            base_url=base_url,
            api_key=api_key,
            model=effective_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
    else:
        return await _call_openai_compatible(
            base_url=base_url,
            api_key=api_key,
            model=effective_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )


def _detect_provider(model: str) -> str:
    """根据模型名检测Provider"""
    model_lower = model.lower()
    if "claude" in model_lower or "anthropic" in model_lower:
        return "anthropic"
    if "deepseek" in model_lower:
        return "deepseek"
    if "gpt" in model_lower or "openai" in model_lower:
        return "openai"
    if "minimax" in model_lower:
        return "minimax"
    if "moonshot" in model_lower or "kimi" in model_lower:
        return "moonshot"
    return "deepseek"  # 默认


async def _call_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    messages: list,
    max_tokens: int,
    temperature: float,
    **kwargs
) -> str:
    """调用OpenAI兼容API"""
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        **kwargs
    }
    
    # 移除可能干扰的参数
    payload = {k: v for k, v in payload.items() 
                if k not in ("api_key", "provider") and v is not None}
    
    client = await get_http_client()
    
    try:
        async with client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120)
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"API error {resp.status}: {error_text}")
            
            result = await resp.json()
            return extract_content_or_reasoning(result)
            
    except Exception as e:
        logger.error(f"_call_openai_compatible failed: {e}")
        raise


async def _call_anthropic(
    base_url: str,
    api_key: str,
    model: str,
    messages: list,
    max_tokens: int,
    temperature: float,
    **kwargs
) -> str:
    """调用Anthropic API（Messages格式）"""
    # 转换消息格式
    system_content = ""
    anthropic_messages = []
    
    for msg in messages:
        if msg["role"] == "system":
            system_content = msg["content"]
        else:
            anthropic_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": anthropic_messages,
    }
    
    if system_content:
        payload["system"] = system_content
    
    if temperature != 0.7:
        payload["temperature"] = temperature
    
    client = await get_http_client()
    
    try:
        async with client.post(
            f"{base_url}/v1/messages",
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120)
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"Anthropic API error {resp.status}: {error_text}")
            
            result = await resp.json()
            # Anthropic响应格式
            content = result.get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", "")
            return ""
            
    except Exception as e:
        logger.error(f"_call_anthropic failed: {e}")
        raise


def extract_content_or_reasoning(response: Dict) -> str:
    """从API响应中提取内容"""
    try:
        # OpenAI兼容格式
        choices = response.get("choices", [])
        if choices:
            choice = choices[0]
            # reasoning_content优先
            message = choice.get("message", {})
            if "reasoning_content" in message:
                rc = message["reasoning_content"]
                if rc:
                    return rc
            content = message.get("content", "")
            if content:
                return content
        
        return ""
        
    except Exception as e:
        logger.error(f"extract_content_or_reasoning failed: {e}")
        return ""


# ============================================================================
# 同步版本（兼容browser_tool）
# ============================================================================

def call_llm(
    prompt: str, 
    model: str = "deepseek-chat", 
    system_prompt: Optional[str] = None,
    provider: str = "auto",
    **kwargs
) -> str:
    """同步版本call_llm（兼容browser_tool）"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        async_call_llm(
            prompt=prompt, 
            model=model, 
            system_prompt=system_prompt,
            provider=provider,
            **kwargs
        )
    )
