"""
MimirAether轻量级Auxiliary Client

只支持DeepSeek API调用，简化自Hermes的auxiliary_client设计。
核心功能：
- async_call_llm: 异步LLM调用
- extract_content_or_reasoning: 从响应提取内容
"""

import os
import json
import logging
import asyncio
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# 全局HTTP客户端
_http_client: Optional[object] = None


async def get_http_client():
    """获取或创建全局HTTP客户端"""
    global _http_client
    if _http_client is None:
        import aiohttp
        _http_client = aiohttp.ClientSession()
    return _http_client


async def async_call_llm(
    prompt: str,
    model: str = "deepseek-chat",
    system_prompt: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    **kwargs
) -> str:
    """
    异步调用LLM（仅支持DeepSeek）
    
    Args:
        prompt: 用户提示
        model: 模型名称
        system_prompt: 系统提示（可选）
        max_tokens: 最大生成token数
        temperature: 温度参数
        **kwargs: 其他参数
    
    Returns:
        模型生成的文本内容
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        # 尝试使用传入的key
        api_key = kwargs.get("api_key", "")
    
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        **kwargs
    }
    
    # 移除api_key避免传递
    payload = {k: v for k, v in payload.items() if k != "api_key"}
    
    client = await get_http_client()
    
    try:
        async with client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
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
        logger.error(f"async_call_llm failed: {e}")
        raise


def extract_content_or_reasoning(response: Dict) -> str:
    """从API响应中提取内容"""
    try:
        choices = response.get("choices", [])
        if not choices:
            return ""
        
        choice = choices[0]
        
        # 优先取reasoning_content（如果有）
        if "reasoning_content" in choice.get("message", {}):
            rc = choice["message"]["reasoning_content"]
            if rc:
                return rc
        
        # 否则取content
        content = choice.get("message", {}).get("content", "")
        return content or ""
        
    except Exception as e:
        logger.error(f"extract_content_or_reasoning failed: {e}")
        return ""


async def close_client():
    """关闭HTTP客户端"""
    global _http_client
    if _http_client:
        await _http_client.close()
        _http_client = None


# 兼容性别名（供browser_tool等使用）
def call_llm(prompt: str, model: str = "deepseek-chat", system_prompt: Optional[str] = None, **kwargs) -> str:
    """同步版本call_llm（兼容browser_tool）"""
    return asyncio.get_event_loop().run_until_complete(
        async_call_llm(prompt=prompt, model=model, system_prompt=system_prompt, **kwargs)
    )
