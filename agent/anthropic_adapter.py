"""
MimirAether Anthropic Adapter

学习自Hermes anthropic_adapter设计思路：
- Anthropic Messages API适配
- OpenAI格式与Anthropic格式转换
- 多种认证方式支持
- OAuth token管理

核心原则：
- 不复制代码，独立实现
- 保持API兼容
- 适配MimirAether框架
"""

import copy
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# ============================================================================
# 常量
# ============================================================================

# Thinking预算映射
THINKING_BUDGET = {
    "xhigh": 32000,
    "high": 16000,
    "medium": 8000,
    "low": 4000,
}

# 自适应思考级别映射
ADAPTIVE_EFFORT_MAP = {
    "xhigh": "max",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "minimal": "low",
}

# Anthropic模型最大输出token限制
_ANTHROPIC_OUTPUT_LIMITS = {
    # Claude 4.6
    "claude-opus-4-6": 128000,
    "claude-sonnet-4-6": 64000,
    # Claude 4.5
    "claude-opus-4-5": 64000,
    "claude-sonnet-4-5": 64000,
    "claude-haiku-4-5": 64000,
    # Claude 4
    "claude-opus-4": 32000,
    "claude-sonnet-4": 64000,
    # Claude 3.7
    "claude-3-7-sonnet": 128000,
    # Claude 3.5
    "claude-3-5-sonnet": 8192,
    "claude-3-5-haiku": 8192,
    # Claude 3
    "claude-3-opus": 4096,
    "claude-3-sonnet": 4096,
    "claude-3-haiku": 4096,
    # 第三方
    "minimax": 131072,
}

# 默认输出限制
_ANTHROPIC_DEFAULT_OUTPUT_LIMIT = 128000

# Beta headers
_COMMON_BETAS = [
    "interleaved-thinking-2025-05-14",
    "fine-grained-tool-streaming-2025-05-14",
]
_TOOL_STREAMING_BETA = "fine-grained-tool-streaming-2025-05-14"
_FAST_MODE_BETA = "fast-mode-2026-02-01"
_OAUTH_ONLY_BETAS = [
    "claude-code-20250219",
    "oauth-2025-04-20",
]

# Claude Code身份
_CLAUDE_CODE_SYSTEM_PREFIX = "You are Claude Code, Anthropic's official CLI for Claude."
_MCP_TOOL_PREFIX = "mcp_"

# OAuth配置
_OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
_OAUTH_TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"
_OAUTH_REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"
_OAUTH_SCOPES = "org:create_api_key user:profile user:inference"
_CLAUDE_CODE_VERSION_FALLBACK = "2.1.74"
_claude_code_version_cache = None

# ============================================================================
# 版本检测
# ============================================================================

def _detect_claude_code_version() -> str:
    """检测Claude Code版本"""
    import subprocess

    for cmd in ("claude", "claude-code"):
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip().split()[0]
                if version and version[0].isdigit():
                    return version
        except Exception:
            pass
    return _CLAUDE_CODE_VERSION_FALLBACK


def _get_claude_code_version() -> str:
    """懒加载Claude Code版本"""
    global _claude_code_version_cache
    if _claude_code_version_cache is None:
        _claude_code_version_cache = _detect_claude_code_version()
    return _claude_code_version_cache


# ============================================================================
# Token检测
# ============================================================================

def is_oauth_token(key: str) -> bool:
    """
    检测是否为Anthropic OAuth/setup token
    
    - sk-ant-api* → 普通API key，False
    - sk-ant-oat* → setup token，True
    - eyJ* → JWT，True
    """
    if not key:
        return False
    if key.startswith("sk-ant-api"):
        return False
    if key.startswith("sk-ant-"):
        return True
    if key.startswith("eyJ"):
        return True
    return False


def normalize_base_url(base_url) -> str:
    """标准化base URL为字符串"""
    if not base_url:
        return ""
    return str(base_url).strip()


def is_third_party_endpoint(base_url: Optional[str]) -> bool:
    """检测是否为第三方Anthropic兼容端点"""
    normalized = normalize_base_url(base_url).rstrip("/").lower()
    if not normalized:
        return False
    if "anthropic.com" in normalized:
        return False
    return True


def requires_bearer_auth(base_url: Optional[str]) -> bool:
    """检测是否需要Bearer认证（如MiniMax）"""
    normalized = normalize_base_url(base_url).rstrip("/").lower()
    if not normalized:
        return False
    return normalized.startswith((
        "https://api.minimax.io/anthropic",
        "https://api.minimaxi.com/anthropic",
    ))


def get_common_betas(base_url: Optional[str]) -> List[str]:
    """获取通用的beta headers"""
    if requires_bearer_auth(base_url):
        return [b for b in _COMMON_BETAS if b != _TOOL_STREAMING_BETA]
    return _COMMON_BETAS


# ============================================================================
# 凭证读取
# ============================================================================

def read_claude_code_credentials() -> Optional[Dict[str, Any]]:
    """读取Claude Code OAuth凭证"""
    cred_path = Path.home() / ".claude" / ".credentials.json"
    if cred_path.exists():
        try:
            data = json.loads(cred_path.read_text(encoding="utf-8"))
            oauth_data = data.get("claudeAiOauth")
            if oauth_data and isinstance(oauth_data, dict):
                access_token = oauth_data.get("accessToken", "")
                if access_token:
                    return {
                        "accessToken": access_token,
                        "refreshToken": oauth_data.get("refreshToken", ""),
                        "expiresAt": oauth_data.get("expiresAt", 0),
                        "source": "claude_code_credentials_file",
                    }
        except (json.JSONDecodeError, OSError, IOError) as e:
            logger.debug("Failed to read Claude Code credentials: %s", e)
    return None


def is_token_valid(creds: Dict[str, Any]) -> bool:
    """检查token是否有效（非过期）"""
    expires_at = creds.get("expiresAt", 0)
    if not expires_at:
        return bool(creds.get("accessToken"))
    
    now_ms = int(time.time() * 1000)
    return now_ms < (expires_at - 60_000)


def resolve_anthropic_token() -> Optional[str]:
    """
    从所有可用来源解析Anthropic token
    
    优先级：
    1. ANTHROPIC_TOKEN env
    2. CLAUDE_CODE_OAUTH_TOKEN env
    3. Claude Code凭证文件
    4. ANTHROPIC_API_KEY env
    """
    creds = read_claude_code_credentials()
    
    # 1. ANTHROPIC_TOKEN
    token = os.getenv("ANTHROPIC_TOKEN", "").strip()
    if token:
        return token
    
    # 2. CLAUDE_CODE_OAUTH_TOKEN
    cc_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if cc_token:
        return cc_token
    
    # 3. Claude Code凭证文件
    if creds and is_token_valid(creds):
        return creds["accessToken"]
    
    # 4. ANTHROPIC_API_KEY
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        return api_key
    
    return None


# ============================================================================
# 客户端构建
# ============================================================================

def build_anthropic_client(
    api_key: str,
    base_url: str = None,
):
    """构建Anthropic客户端"""
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "需要安装anthropic包: pip install 'anthropic>=0.39.0'"
        )
    
    from httpx import Timeout
    
    normalized_base_url = normalize_base_url(base_url)
    kwargs = {
        "timeout": Timeout(timeout=900.0, connect=10.0),
    }
    
    if normalized_base_url:
        kwargs["base_url"] = normalized_base_url
    
    common_betas = get_common_betas(normalized_base_url)
    
    if requires_bearer_auth(normalized_base_url):
        kwargs["auth_token"] = api_key
        if common_betas:
            kwargs["default_headers"] = {"anthropic-beta": ",".join(common_betas)}
    elif is_third_party_endpoint(base_url):
        kwargs["api_key"] = api_key
        if common_betas:
            kwargs["default_headers"] = {"anthropic-beta": ",".join(common_betas)}
    elif is_oauth_token(api_key):
        all_betas = common_betas + _OAUTH_ONLY_BETAS
        kwargs["auth_token"] = api_key
        kwargs["default_headers"] = {
            "anthropic-beta": ",".join(all_betas),
            "user-agent": f"claude-cli/{_get_claude_code_version()} (external, cli)",
            "x-app": "cli",
        }
    else:
        kwargs["api_key"] = api_key
        if common_betas:
            kwargs["default_headers"] = {"anthropic-beta": ",".join(common_betas)}
    
    return anthropic.Anthropic(**kwargs)


# ============================================================================
# 模型名称标准化
# ============================================================================

def normalize_model_name(model: str, preserve_dots: bool = False) -> str:
    """
    标准化模型名称
    
    - 剥离anthropic/前缀
    - 点号转横线（claude-opus-4.6 → claude-opus-4-6）
    - preserve_dots=True时保留点号（如qwen3.5-plus）
    - 处理provider/model格式
    """
    lower = model.lower()
    
    # 剥离provider前缀（如anthropic/, deepseek/）
    if lower.startswith("anthropic/"):
        model = model[len("anthropic/"):]
    elif "/" in model and not preserve_dots:
        # 处理其他provider前缀（如deepseek/deepseek-chat）
        parts = model.split("/", 1)
        if parts[0].lower() in ("openrouter", "nous", "deepseek", "openai", "google",
                                "anthropic", "minimax", "kimi", "qwen", "claude", "gemini"):
            model = parts[1]
    
    if not preserve_dots:
        model = model.replace(".", "-")
    return model


def get_anthropic_max_output(model: str) -> int:
    """
    获取Anthropic模型的最大输出token
    
    使用最长前缀匹配，支持日期后缀和变体
    """
    m = model.lower().replace(".", "-")
    best_key = ""
    best_val = _ANTHROPIC_DEFAULT_OUTPUT_LIMIT
    for key, val in _ANTHROPIC_OUTPUT_LIMITS.items():
        if key in m and len(key) > len(best_key):
            best_key = key
            best_val = val
    return best_val


def supports_adaptive_thinking(model: str) -> bool:
    """检测是否支持自适应思考（Claude 4.6）"""
    return any(v in model for v in ("4-6", "4.6"))


# ============================================================================
# 工具转换
# ============================================================================

def sanitize_tool_id(tool_id: str) -> str:
    """清理tool ID为Anthropic兼容格式"""
    if not tool_id:
        return "tool_0"
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", tool_id)
    return sanitized or "tool_0"


def convert_tools_to_anthropic(tools: List[Dict]) -> List[Dict]:
    """转换OpenAI工具定义为Anthropic格式"""
    if not tools:
        return []
    result = []
    for t in tools:
        fn = t.get("function", {})
        result.append({
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


# ============================================================================
# 消息转换
# ============================================================================

def _image_source_from_url(url: str) -> Dict[str, str]:
    """将OpenAI风格image URL转为Anthropic格式"""
    url = str(url or "").strip()
    if not url:
        return {"type": "url", "url": ""}
    
    if url.startswith("data:"):
        header, _, data = url.partition(",")
        media_type = "image/jpeg"
        if header.startswith("data:"):
            mime_part = header[len("data:"):].split(";", 1)[0].strip()
            if mime_part.startswith("image/"):
                media_type = mime_part
        return {
            "type": "base64",
            "media_type": media_type,
            "data": data,
        }
    
    return {"type": "url", "url": url}


def _convert_content_part(part: Any) -> Optional[Dict[str, Any]]:
    """转换单个content part为Anthropic格式"""
    if part is None:
        return None
    if isinstance(part, str):
        return {"type": "text", "text": part}
    if not isinstance(part, dict):
        return {"type": "text", "text": str(part)}
    
    ptype = part.get("type")
    
    if ptype == "input_text":
        block = {"type": "text", "text": part.get("text", "")}
    elif ptype in {"image_url", "input_image"}:
        image_value = part.get("image_url", {})
        url = image_value.get("url", "") if isinstance(image_value, dict) else str(image_value or "")
        block = {"type": "image", "source": _image_source_from_url(url)}
    else:
        block = dict(part)
    
    if isinstance(part.get("cache_control"), dict) and "cache_control" not in block:
        block["cache_control"] = dict(part["cache_control"])
    return block


def _to_plain_data(value: Any, *, _depth: int = 0, _path: Optional[set] = None) -> Any:
    """递归转换SDK对象为纯Python数据结构"""
    _MAX_DEPTH = 20
    if _depth > _MAX_DEPTH:
        return str(value)
    
    if _path is None:
        _path = set()
    
    obj_id = id(value)
    if obj_id in _path:
        return str(value)
    
    if hasattr(value, "model_dump"):
        _path.add(obj_id)
        result = _to_plain_data(value.model_dump(), _depth=_depth + 1, _path=_path)
        _path.discard(obj_id)
        return result
    if isinstance(value, dict):
        _path.add(obj_id)
        result = {k: _to_plain_data(v, _depth=_depth + 1, _path=_path) for k, v in value.items()}
        _path.discard(obj_id)
        return result
    if isinstance(value, (list, tuple)):
        _path.add(obj_id)
        result = [_to_plain_data(v, _depth=_depth + 1, _path=_path) for v in value]
        _path.discard(obj_id)
        return result
    if hasattr(value, "__dict__"):
        _path.add(obj_id)
        result = {
            k: _to_plain_data(v, _depth=_depth + 1, _path=_path)
            for k, v in vars(value).items()
            if not k.startswith("_")
        }
        _path.discard(obj_id)
        return result
    return value


def _extract_thinking_blocks(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    """提取保留的thinking blocks"""
    raw_details = message.get("reasoning_details")
    if not isinstance(raw_details, list):
        return []
    
    preserved = []
    for detail in raw_details:
        if not isinstance(detail, dict):
            continue
        block_type = str(detail.get("type", "") or "").strip().lower()
        if block_type not in {"thinking", "redacted_thinking"}:
            continue
        preserved.append(copy.deepcopy(detail))
    return preserved


def convert_messages_to_anthropic(
    messages: List[Dict],
    base_url: str = None,
) -> Tuple[Optional[Any], List[Dict]]:
    """
    转换OpenAI格式消息为Anthropic格式
    
    返回 (system_prompt, anthropic_messages)
    """
    system = None
    result = []
    
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        
        # System消息单独提取
        if role == "system":
            if isinstance(content, list):
                has_cache = any(p.get("cache_control") for p in content if isinstance(p, dict))
                if has_cache:
                    system = [p for p in content if isinstance(p, dict)]
                else:
                    system = "\n".join(p["text"] for p in content if p.get("type") == "text")
            else:
                system = content
            continue
        
        # Assistant消息
        if role == "assistant":
            blocks = _extract_thinking_blocks(m)
            if content:
                if isinstance(content, list):
                    for part in content:
                        block = _convert_content_part(part)
                        if block:
                            blocks.append(block)
                else:
                    blocks.append({"type": "text", "text": str(content)})
            
            # Tool calls
            for tc in m.get("tool_calls", []):
                if not tc or not isinstance(tc, dict):
                    continue
                fn = tc.get("function", {})
                args = fn.get("arguments", "{}")
                try:
                    parsed_args = json.loads(args) if isinstance(args, str) else args
                except (json.JSONDecodeError, ValueError):
                    parsed_args = {}
                blocks.append({
                    "type": "tool_use",
                    "id": sanitize_tool_id(tc.get("id", "")),
                    "name": fn.get("name", ""),
                    "input": parsed_args,
                })
            
            effective = blocks or content
            if not effective or effective == "":
                effective = [{"type": "text", "text": "(empty)"}]
            result.append({"role": "assistant", "content": effective})
            continue
        
        # Tool消息
        if role == "tool":
            result_content = content if isinstance(content, str) else json.dumps(content)
            if not result_content:
                result_content = "(no output)"
            tool_result = {
                "type": "tool_result",
                "tool_use_id": sanitize_tool_id(m.get("tool_call_id", "")),
                "content": result_content,
            }
            if isinstance(m.get("cache_control"), dict):
                tool_result["cache_control"] = dict(m["cache_control"])
            
            # 合并连续tool结果
            if (result and result[-1]["role"] == "user" and 
                isinstance(result[-1]["content"], list) and result[-1]["content"] and
                result[-1]["content"][0].get("type") == "tool_result"):
                result[-1]["content"].append(tool_result)
            else:
                result.append({"role": "user", "content": [tool_result]})
            continue
        
        # User消息
        if isinstance(content, list):
            converted = [_convert_content_part(p) for p in content]
            converted = [c for c in converted if c is not None]
            if not converted or all(c.get("text", "").strip() == "" for c in converted if c.get("type") == "text"):
                converted = [{"type": "text", "text": "(empty message)"}]
            result.append({"role": "user", "content": converted})
        else:
            if not content or (isinstance(content, str) and not content.strip()):
                content = "(empty message)"
            result.append({"role": "user", "content": content})
    
    # 清理孤立tool blocks
    tool_result_ids = set()
    for m in result:
        if m["role"] == "user" and isinstance(m["content"], list):
            for block in m["content"]:
                if block.get("type") == "tool_result":
                    tool_result_ids.add(block.get("tool_use_id"))
    
    for m in result:
        if m["role"] == "assistant" and isinstance(m["content"], list):
            m["content"] = [
                b for b in m["content"]
                if b.get("type") != "tool_use" or b.get("id") in tool_result_ids
            ]
            if not m["content"]:
                m["content"] = [{"type": "text", "text": "(tool call removed)"}]
    
    # 清理孤立的tool_result blocks
    tool_use_ids = set()
    for m in result:
        if m["role"] == "assistant" and isinstance(m["content"], list):
            for block in m["content"]:
                if block.get("type") == "tool_use":
                    tool_use_ids.add(block.get("id"))
    
    for m in result:
        if m["role"] == "user" and isinstance(m["content"], list):
            m["content"] = [
                b for b in m["content"]
                if b.get("type") != "tool_result" or b.get("tool_use_id") in tool_use_ids
            ]
            if not m["content"]:
                m["content"] = [{"type": "text", "text": "(tool result removed)"}]
    
    # 强制role交替
    fixed = []
    for m in result:
        if fixed and fixed[-1]["role"] == m["role"]:
            if m["role"] == "user":
                prev = fixed[-1]["content"]
                curr = m["content"]
                if isinstance(prev, str) and isinstance(curr, str):
                    fixed[-1]["content"] = prev + "\n" + curr
                elif isinstance(prev, list) and isinstance(curr, list):
                    fixed[-1]["content"] = prev + curr
            else:
                # 合并连续assistant，移除第二个的thinking blocks
                if isinstance(m["content"], list):
                    m["content"] = [
                        b for b in m["content"]
                        if not (isinstance(b, dict) and b.get("type") in ("thinking", "redacted_thinking"))
                    ]
                prev_blocks = fixed[-1]["content"]
                curr_blocks = m["content"]
                if isinstance(prev_blocks, list) and isinstance(curr_blocks, list):
                    fixed[-1]["content"] = prev_blocks + curr_blocks
                elif isinstance(prev_blocks, str) and isinstance(curr_blocks, str):
                    fixed[-1]["content"] = prev_blocks + "\n" + curr_blocks
        else:
            fixed.append(m)
    result = fixed
    
    # Thinking block签名管理
    _THINKING_TYPES = frozenset(("thinking", "redacted_thinking"))
    is_third_party = is_third_party_endpoint(base_url)
    
    last_assistant_idx = None
    for i in range(len(result) - 1, -1, -1):
        if result[i].get("role") == "assistant":
            last_assistant_idx = i
            break
    
    for idx, m in enumerate(result):
        if m.get("role") != "assistant" or not isinstance(m.get("content"), list):
            continue
        
        if is_third_party or idx != last_assistant_idx:
            # 第三方端点：移除所有thinking blocks
            # 直接Anthropic：只保留最后一个assistant的thinking
            m["content"] = [
                b for b in m["content"]
                if not (isinstance(b, dict) and b.get("type") in _THINKING_TYPES)
            ] or [{"type": "text", "text": "(thinking elided)"}]
        else:
            # 最新assistant：保留签名thinking，移除未签名thinking
            new_content = []
            for b in m["content"]:
                if not isinstance(b, dict) or b.get("type") not in _THINKING_TYPES:
                    new_content.append(b)
                    continue
                if b.get("type") == "redacted_thinking":
                    if b.get("data"):
                        new_content.append(b)
                elif b.get("signature"):
                    new_content.append(b)
                else:
                    thinking_text = b.get("thinking", "")
                    if thinking_text:
                        new_content.append({"type": "text", "text": thinking_text})
            m["content"] = new_content or [{"type": "text", "text": "(empty)"}]
        
        # 移除thinking blocks的cache_control
        for b in m["content"]:
            if isinstance(b, dict) and b.get("type") in _THINKING_TYPES:
                b.pop("cache_control", None)
    
    return system, result


# ============================================================================
# 请求构建
# ============================================================================

def build_anthropic_kwargs(
    model: str,
    messages: List[Dict],
    tools: Optional[List[Dict]],
    max_tokens: Optional[int],
    reasoning_config: Optional[Dict[str, Any]] = None,
    tool_choice: Optional[str] = None,
    is_oauth: bool = False,
    preserve_dots: bool = False,
    context_length: Optional[int] = None,
    base_url: str = None,
    fast_mode: bool = False,
) -> Dict[str, Any]:
    """
    构建Anthropic消息创建所需的kwargs
    
    参数：
    - max_tokens: 输出token上限（不是总上下文窗口）
    - context_length: 总上下文窗口大小
    - is_oauth: 是否使用OAuth Claude Code兼容模式
    - preserve_dots: 是否保留模型名中的点号
    - fast_mode: 是否启用快速模式（仅Opus 4.6）
    """
    system, anthropic_messages = convert_messages_to_anthropic(messages, base_url=base_url)
    anthropic_tools = convert_tools_to_anthropic(tools) if tools else []
    
    model = normalize_model_name(model, preserve_dots=preserve_dots)
    effective_max_tokens = max_tokens or get_anthropic_max_output(model)
    
    # 如果context_length小于输出上限，调整输出
    if context_length and effective_max_tokens > context_length:
        effective_max_tokens = max(context_length - 1, 1)
    
    # OAuth Claude Code兼容处理
    if is_oauth:
        cc_block = {"type": "text", "text": _CLAUDE_CODE_SYSTEM_PREFIX}
        if isinstance(system, list):
            system = [cc_block] + system
        elif isinstance(system, str) and system:
            system = [cc_block, {"type": "text", "text": system}]
        else:
            system = [cc_block]
        
        # 替换产品名称
        for block in system:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                text = text.replace("Hermes Agent", "Claude Code")
                text = text.replace("MimirAether", "Claude Code")
                text = text.replace("Nous Research", "Anthropic")
                block["text"] = text
        
        # 工具名称前缀
        if anthropic_tools:
            for tool in anthropic_tools:
                if "name" in tool:
                    tool["name"] = _MCP_TOOL_PREFIX + tool["name"]
        
        # 消息历史中的工具名称前缀
        for msg in anthropic_messages:
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_use" and "name" in block:
                            if not block["name"].startswith(_MCP_TOOL_PREFIX):
                                block["name"] = _MCP_TOOL_PREFIX + block["name"]
    
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": anthropic_messages,
        "max_tokens": effective_max_tokens,
    }
    
    if system:
        kwargs["system"] = system
    
    if anthropic_tools:
        kwargs["tools"] = anthropic_tools
        if tool_choice == "auto" or tool_choice is None:
            kwargs["tool_choice"] = {"type": "auto"}
        elif tool_choice == "required":
            kwargs["tool_choice"] = {"type": "any"}
        elif tool_choice == "none":
            kwargs.pop("tools", None)
        elif isinstance(tool_choice, str):
            kwargs["tool_choice"] = {"type": "tool", "name": tool_choice}
    
    # Thinking配置
    if reasoning_config and isinstance(reasoning_config, dict):
        if reasoning_config.get("enabled") is not False and "haiku" not in model.lower():
            effort = str(reasoning_config.get("effort", "medium")).lower()
            budget = THINKING_BUDGET.get(effort, 8000)
            if supports_adaptive_thinking(model):
                kwargs["thinking"] = {"type": "adaptive"}
                kwargs["output_config"] = {
                    "effort": ADAPTIVE_EFFORT_MAP.get(effort, "medium")
                }
            else:
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
                kwargs["temperature"] = 1
                kwargs["max_tokens"] = max(effective_max_tokens, budget + 4096)
    
    # 快速模式（仅Opus 4.6）
    if fast_mode and not is_third_party_endpoint(base_url):
        kwargs.setdefault("extra_body", {})["speed"] = "fast"
        betas = list(get_common_betas(base_url))
        if is_oauth:
            betas.extend(_OAUTH_ONLY_BETAS)
        betas.append(_FAST_MODE_BETA)
        kwargs["extra_headers"] = {"anthropic-beta": ",".join(betas)}
    
    return kwargs


# ============================================================================
# 响应标准化
# ============================================================================

def normalize_anthropic_response(
    response,
    strip_tool_prefix: bool = False,
):
    """
    标准化Anthropic响应为通用格式
    
    返回 (assistant_message, finish_reason)
    """
    from types import SimpleNamespace
    
    text_parts = []
    reasoning_parts = []
    reasoning_details = []
    tool_calls = []
    
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "thinking":
            reasoning_parts.append(block.thinking)
            block_dict = _to_plain_data(block)
            if isinstance(block_dict, dict):
                reasoning_details.append(block_dict)
        elif block.type == "tool_use":
            name = block.name
            if strip_tool_prefix and name.startswith(_MCP_TOOL_PREFIX):
                name = name[len(_MCP_TOOL_PREFIX):]
            tool_calls.append(
                SimpleNamespace(
                    id=block.id,
                    type="function",
                    function=SimpleNamespace(
                        name=name,
                        arguments=json.dumps(block.input),
                    ),
                )
            )
    
    # 映射stop_reason
    stop_reason_map = {
        "end_turn": "stop",
        "tool_use": "tool_calls",
        "max_tokens": "length",
        "stop_sequence": "stop",
    }
    finish_reason = stop_reason_map.get(response.stop_reason, "stop")
    
    return (
        SimpleNamespace(
            content="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls or None,
            reasoning="\n\n".join(reasoning_parts) if reasoning_parts else None,
            reasoning_content=None,
            reasoning_details=reasoning_details or None,
        ),
        finish_reason,
    )


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    print("=" * 60)
    print("MimirAether Anthropic Adapter 测试")
    print("=" * 60)
    
    # 测试1: Token类型检测
    print("\n[测试1] Token类型检测")
    tokens = [
        ("sk-ant-api...", False),
        ("sk-ant-oat...", True),
        ("eyJ...", True),
        ("normal_key", False),
    ]
    for token, expected in tokens:
        result = is_oauth_token(token)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{token[:15]}...' → {result} (expected: {expected})")
    
    # 测试2: 模型名称标准化
    print("\n[测试2] 模型名称标准化")
    models = [
        ("anthropic/claude-opus-4.6", "claude-opus-4-6"),
        ("claude-sonnet-4.6", "claude-sonnet-4-6"),
        ("qwen3.5-plus", "qwen3-5-plus", True),  # preserve_dots
        ("deepseek/deepseek-chat", "deepseek-chat"),
    ]
    for args in models:
        preserve = args[2] if len(args) > 2 else False
        input_model, expected = args[0], args[1]
        result = normalize_model_name(input_model, preserve_dots=preserve)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_model}' → '{result}' (expected: '{expected}')")
    
    # 测试3: 最大输出token
    print("\n[测试3] 最大输出token")
    models = [
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-opus-4-5",
        "claude-3-5-sonnet",
        "unknown-model",
    ]
    for model in models:
        output = get_anthropic_max_output(model)
        print(f"  {model}: {output:,} tokens")
    
    # 测试4: 工具转换
    print("\n[测试4] 工具转换")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"}
                    }
                }
            }
        }
    ]
    converted = convert_tools_to_anthropic(tools)
    print(f"  Input: {len(tools)} tool(s)")
    print(f"  Output: {len(converted)} tool(s)")
    if converted:
        print(f"  Name: {converted[0].get('name')}")
    
    # 测试5: 消息转换
    print("\n[测试5] 消息转换")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "What's the weather?"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_1", "function": {"name": "get_weather", "arguments": '{"city": "Beijing"}'}}
        ]},
        {"role": "tool", "tool_call_id": "call_1", "content": "Sunny, 25C"},
    ]
    system, anthropic_messages = convert_messages_to_anthropic(messages)
    print(f"  System: '{system[:30] if system else None}...'")
    print(f"  Messages: {len(anthropic_messages)}")
    for i, msg in enumerate(anthropic_messages):
        role = msg["role"]
        content_type = type(msg["content"]).__name__
        print(f"    [{i}] {role}: {content_type}")
    
    # 测试6: 请求构建
    print("\n[测试6] 请求构建")
    kwargs = build_anthropic_kwargs(
        model="claude-opus-4-6",
        messages=[{"role": "user", "content": "Hello"}],
        tools=None,
        max_tokens=1024,
        reasoning_config={"enabled": True, "effort": "medium"},
    )
    print(f"  Model: {kwargs.get('model')}")
    print(f"  Max tokens: {kwargs.get('max_tokens')}")
    print(f"  Has thinking: {'thinking' in kwargs}")
    print(f"  Has system: {'system' in kwargs}")
    
    # 测试7: 响应标准化
    print("\n[测试7] 响应标准化（模拟）")
    # 创建一个模拟响应对象
    class MockBlock:
        def __init__(self, block_type, text=None, thinking=None, name=None, block_id=None, input_data=None):
            self.type = block_type
            self.text = text
            self.thinking = thinking
            self.name = name
            self.id = block_id
            self.input = input_data
    
    class MockResponse:
        def __init__(self, content, stop_reason):
            self.content = content
            self.stop_reason = stop_reason
    
    mock_response = MockResponse(
        content=[
            MockBlock("text", text="Hello! How can I help?"),
        ],
        stop_reason="end_turn"
    )
    
    normalized, finish_reason = normalize_anthropic_response(mock_response)
    print(f"  Content: '{normalized.content}'")
    print(f"  Finish reason: {finish_reason}")
    print(f"  Tool calls: {normalized.tool_calls}")
    print(f"  Reasoning: {normalized.reasoning}")
    
    # 测试8: 端点检测
    print("\n[测试8] 端点检测")
    urls = [
        "https://api.anthropic.com",
        "https://api.anthropic.com/v1",
        "https://api.minimax.io/anthropic",
        "https://api.openai.com/v1",
        None,
    ]
    for url in urls:
        is_3rd = is_third_party_endpoint(url)
        needs_bearer = requires_bearer_auth(url)
        print(f"  {url}: third_party={is_3rd}, bearer={needs_bearer}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)