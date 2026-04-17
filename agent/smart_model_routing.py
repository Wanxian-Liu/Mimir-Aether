"""
MimirAether Smart Model Routing

学习自Hermes smart_model_routing设计。

核心功能：
- 简单请求自动切换便宜模型
- 复杂任务保持主模型
- 成本优化

使用方式：
- 在core_loop调用模型前先经过路由决策
- 配置cheap_model为便宜模型（如gpt-4o-mini）
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

# 复杂关键词列表 - 包含这些词时保持主模型
_COMPLEX_KEYWORDS = {
    # 英文关键词
    "debug", "debugging", "implement", "implementation",
    "refactor", "patch", "traceback", "stacktrace",
    "exception", "error", "analyze", "analysis",
    "investigate", "architecture", "design", "compare",
    "benchmark", "optimize", "optimise", "review",
    "terminal", "shell", "tool", "tools", "pytest",
    "test", "tests", "plan", "planning", "delegate",
    "subagent", "cron", "docker", "kubernetes",
    # 中文关键词（无空格语言需要按字符匹配）
    "调试", "实现", "重构", "分析", "架构",
    "测试", "计划", "委托", "子代理", "优化",
    " benchmark", "optimize", "review",
}

# URL正则
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)

# 代码块正则
_CODE_BLOCK_RE = re.compile(r"```|`")


def _coerce_bool(value: Any, default: bool = False) -> bool:
    """将值转换为布尔值"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on", "enabled")
    return default


def _coerce_int(value: Any, default: int) -> int:
    """将值转换为整数"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def choose_cheap_model_route(
    user_message: str,
    routing_config: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    判断是否使用便宜模型路由
    
    返回便宜模型路由dict如果请求足够简单，否则返回None。
    
    简单请求判断条件（全部满足）：
    - 字符数 <= max_simple_chars (默认160)
    - 词数 <= max_simple_words (默认28)
    - 换行符 <= 1
    - 无代码块
    - 无URL
    - 无复杂关键词
    """
    cfg = routing_config or {}
    
    # 检查是否启用
    if not _coerce_bool(cfg.get("enabled"), False):
        return None
    
    # 获取便宜模型配置
    cheap_model = cfg.get("cheap_model") or {}
    if not isinstance(cheap_model, dict):
        return None
    
    provider = str(cheap_model.get("provider") or "").strip().lower()
    model = str(cheap_model.get("model") or "").strip()
    
    if not provider or not model:
        return None
    
    # 获取配置参数
    max_chars = _coerce_int(cfg.get("max_simple_chars"), 160)
    max_words = _coerce_int(cfg.get("max_simple_words"), 28)
    
    # 分析消息
    text = (user_message or "").strip()
    if not text:
        return None
    
    # 条件1: 字符数检查
    if len(text) > max_chars:
        return None
    
    # 条件2: 词数检查
    if len(text.split()) > max_words:
        return None
    
    # 条件3: 换行符检查
    if text.count("\n") > 1:
        return None
    
    # 条件4: 代码块检查
    if _CODE_BLOCK_RE.search(text):
        return None
    
    # 条件5: URL检查
    if _URL_RE.search(text):
        return None
    
    # 条件6: 复杂关键词检查（支持英文按空格分词 + 中文按字符匹配）
    lowered = text.lower()
    
    # 英文按空格分词
    words = {
        token.strip(".,:;!?()[]{}\"'`") 
        for token in lowered.split()
    }
    
    # 检查英文关键词匹配
    if words & _COMPLEX_KEYWORDS:
        return None
    
    # 检查中文关键词（直接匹配子串）
    chinese_keywords = [k for k in _COMPLEX_KEYWORDS if len(k) > 1 and not k.startswith(" ")]
    for keyword in chinese_keywords:
        if keyword in lowered:
            return None
    
    # 所有条件满足，使用便宜模型
    return {
        "provider": provider,
        "model": model,
        "api_key_env": cheap_model.get("api_key_env"),
        "base_url": cheap_model.get("base_url"),
        "routing_reason": "simple_turn",
    }


def resolve_turn_route(
    user_message: str,
    routing_config: Optional[Dict[str, Any]] = None,
    primary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    解析本轮使用的模型路由
    
    返回完整路由决策，包含：
    - model: 最终使用的模型
    - provider: provider名称
    - runtime: 运行时配置
    - label: 路由标签（用于日志）
    - is_cheap: 是否使用了便宜模型
    """
    # 默认主模型配置
    default_primary = {
        "model": os.environ.get("LLM_MODEL", "kimi-k2.5"),
        "provider": "deepseek",
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "base_url": "https://api.deepseek.com",
        "api_mode": "chat",
    }
    
    if primary:
        default_primary.update(primary)
    
    primary = default_primary
    
    # 尝试获取便宜模型路由
    cheap_route = choose_cheap_model_route(user_message, routing_config)
    
    if not cheap_route:
        # 不使用便宜模型，返回主模型
        return {
            "model": primary.get("model"),
            "provider": primary.get("provider"),
            "runtime": {
                "api_key": primary.get("api_key"),
                "base_url": primary.get("base_url"),
                "api_mode": primary.get("api_mode", "chat"),
            },
            "label": None,
            "is_cheap": False,
        }
    
    # 使用便宜模型
    # 解析api_key
    api_key = None
    api_key_env = cheap_route.get("api_key_env")
    if api_key_env:
        api_key = os.environ.get(api_key_env) or None
    
    # 解析base_url
    base_url = cheap_route.get("base_url")
    
    return {
        "model": cheap_route.get("model"),
        "provider": cheap_route.get("provider"),
        "runtime": {
            "api_key": api_key,
            "base_url": base_url,
            "api_mode": "chat",
        },
        "label": f"smart_route -> {cheap_route.get('model')} ({cheap_route.get('provider')})",
        "is_cheap": True,
        "routing_reason": cheap_route.get("routing_reason"),
    }


# =============================================================================
# 配置示例
# =============================================================================

DEFAULT_ROUTING_CONFIG = {
    "enabled": False,  # 默认关闭
    "max_simple_chars": 160,
    "max_simple_words": 28,
    "cheap_model": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
}


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Smart Model Routing 测试")
    print("=" * 60)
    
    # 测试配置
    config = {
        "enabled": True,
        "max_simple_chars": 160,
        "max_simple_words": 28,
        "cheap_model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
        },
    }
    
    primary = {
        "model": "kimi-k2.5",
        "provider": "deepseek",
        "api_key": "test-key",
        "base_url": "https://api.deepseek.com",
    }
    
    print("\n[测试1] 简单问候")
    msg1 = "你好，今天天气怎么样？"
    result1 = resolve_turn_route(msg1, config, primary)
    print(f"  消息: {msg1}")
    print(f"  结果: model={result1['model']}, is_cheap={result1['is_cheap']}, label={result1['label']}")
    
    print("\n[测试2] 调试请求")
    msg2 = "帮我debug这段代码"
    result2 = resolve_turn_route(msg2, config, primary)
    print(f"  消息: {msg2}")
    print(f"  结果: model={result2['model']}, is_cheap={result2['is_cheap']}")
    
    print("\n[测试3] 实现功能请求")
    msg3 = "帮我实现一个排序算法"
    result3 = resolve_turn_route(msg3, config, primary)
    print(f"  消息: {msg3}")
    print(f"  结果: model={result3['model']}, is_cheap={result3['is_cheap']}")
    
    print("\n[测试4] 简单确认")
    msg4 = "好的"
    result4 = resolve_turn_route(msg4, config, primary)
    print(f"  消息: {msg4}")
    print(f"  结果: model={result4['model']}, is_cheap={result4['is_cheap']}, label={result4['label']}")
    
    print("\n[测试5] 包含URL")
    msg5 = "看看这个链接 https://example.com"
    result5 = resolve_turn_route(msg5, config, primary)
    print(f"  消息: {msg5}")
    print(f"  结果: model={result5['model']}, is_cheap={result5['is_cheap']}")
    
    print("\n[测试6] 包含代码")
    msg6 = "这段代码有问题：```python print('hello') ```"
    result6 = resolve_turn_route(msg6, config, primary)
    print(f"  消息: {msg6[:30]}...")
    print(f"  结果: model={result6['model']}, is_cheap={result6['is_cheap']}")
    
    print("\n[测试7] 关闭路由")
    config_disabled = {"enabled": False}
    msg7 = "你好"
    result7 = resolve_turn_route(msg7, config_disabled, primary)
    print(f"  消息: {msg7}")
    print(f"  结果: model={result7['model']}, is_cheap={result7['is_cheap']}")
    
    print("\n[测试8] 长消息")
    msg8 = "这是一个比较长的消息，需要测试超过160个字符的情况，看看是否会被识别为复杂请求并保持主模型。这是一个比较长的消息，需要测试超过160个字符的情况。" * 2
    result8 = resolve_turn_route(msg8, config, primary)
    print(f"  消息长度: {len(msg8)} 字符")
    print(f"  结果: model={result8['model']}, is_cheap={result8['is_cheap']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)