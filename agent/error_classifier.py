"""
MimirAether Error Classifier

学习自Hermes error_classifier设计。

核心功能：
- 结构化API错误分类
- 智能故障恢复策略
- Provider-specific错误模式

错误类型 (FailoverReason):
- auth: 认证错误
- billing: 账单/配额问题
- rate_limit: 速率限制
- context_overflow: 上下文溢出
- model_not_found: 模型未找到
- timeout: 超时
- server_error: 服务器错误
- unknown: 未知错误
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# 错误类型枚举
# ============================================================================

class FailoverReason(enum.Enum):
    """API错误类型，决定恢复策略"""
    
    # 认证/授权
    auth = "auth"                          # 401/403 - 刷新或轮换凭证
    auth_permanent = "auth_permanent"      # 认证彻底失败 - 中止
    
    # 计费/配额
    billing = "billing"                    # 402或额度用尽 - 立即轮换
    rate_limit = "rate_limit"            # 429限流 - 退避后轮换
    
    # 服务器错误
    overloaded = "overloaded"             # 503/529 - 服务过载
    server_error = "server_error"        # 500/502 - 内部错误，重试
    
    # 传输层
    timeout = "timeout"                  # 连接/读取超时
    
    # 上下文/载荷
    context_overflow = "context_overflow" # 上下文过大 - 压缩不failover
    payload_too_large = "payload_too_large"  # 413 - 压缩载荷
    
    # 模型
    model_not_found = "model_not_found"   # 404或无效模型 - fallback
    
    # 请求格式
    format_error = "format_error"         # 400错误请求 - 中止或精简重试
    
    # Provider特定
    thinking_signature = "thinking_signature"  # Anthropic thinking签名无效
    long_context_tier = "long_context_tier"  # Anthropic长上下文tier门控
    
    # 未知
    unknown = "unknown"                   # 无法分类 - 退避重试


# ============================================================================
# 分类结果
# ============================================================================

@dataclass
class ClassifiedError:
    """结构化API错误分类，包含恢复建议"""
    
    reason: FailoverReason
    status_code: Optional[int] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    message: str = ""
    error_context: Dict[str, Any] = field(default_factory=dict)
    
    # 恢复动作提示
    retryable: bool = True              # 是否可重试
    should_compress: bool = False      # 是否应压缩上下文
    should_rotate_credential: bool = False  # 是否应轮换凭证
    should_fallback: bool = False      # 是否应fallback到其他provider
    
    @property
    def is_auth(self) -> bool:
        return self.reason in (FailoverReason.auth, FailoverReason.auth_permanent)


# ============================================================================
# 错误模式库
# ============================================================================

# 计费耗尽模式（不是临时限流）
_BILLING_PATTERNS = [
    "insufficient credits",
    "insufficient_quota",
    "credit balance",
    "credits have been exhausted",
    "top up your credits",
    "payment required",
    "billing hard limit",
    "exceeded your current quota",
    "account is deactivated",
    "plan does not include",
    # 中文
    "额度不足",
    "余额不足",
    "充值",
]

# 限流模式（临时，会恢复）
_RATE_LIMIT_PATTERNS = [
    "rate limit",
    "rate_limit",
    "too many requests",
    "throttled",
    "requests per minute",
    "tokens per minute",
    "try again in",
    "please retry after",
    "resource_exhausted",
    # 中文
    "请求过于频繁",
    "限流",
    "稍后重试",
]

# 需要区分的模式（可能是计费也可能是限流）
_USAGE_LIMIT_PATTERNS = [
    "usage limit",
    "quota",
    "limit exceeded",
    "key limit exceeded",
]

# 限流瞬时信号（表示是临时的，不是计费问题）
_USAGE_LIMIT_TRANSIENT_SIGNALS = [
    "try again",
    "retry",
    "resets at",
    "reset in",
    "wait",
    "periodic",
]

# 载荷过大模式
_PAYLOAD_TOO_LARGE_PATTERNS = [
    "request entity too large",
    "payload too large",
    "error code: 413",
    # 中文
    "请求体过大",
]

# 上下文溢出模式
_CONTEXT_OVERFLOW_PATTERNS = [
    "context length",
    "context size",
    "maximum context",
    "token limit",
    "too many tokens",
    "reduce the length",
    "exceeds the limit",
    "context window",
    "prompt is too long",
    "prompt exceeds max length",
    "max_tokens",
    "maximum number of tokens",
    "exceeds the max_model_len",
    "max_model_len",
    "prompt length",
    "input is too long",
    "maximum model length",
    "context length exceeded",
    "truncating input",
    # vLLM/Ollama
    "slot context",
    "n_ctx_slot",
    # 中文
    "超过最大长度",
    "上下文长度",
    "令牌数超限",
    "token超出",
]

# 模型未找到模式
_MODEL_NOT_FOUND_PATTERNS = [
    "is not a valid model",
    "invalid model",
    "model not found",
    "model_not_found",
    "does not exist",
    "no such model",
    "unknown model",
    "unsupported model",
    # 中文
    "模型不存在",
    "无效模型",
]

# 认证错误模式
_AUTH_PATTERNS = [
    "invalid api key",
    "invalid_api_key",
    "authentication",
    "unauthorized",
    "forbidden",
    "invalid token",
    "token expired",
    "token revoked",
    "access denied",
    # 中文
    "认证失败",
    "无效密钥",
    "未授权",
]

# Anthropic thinking签名错误
_THINKING_SIG_PATTERNS = ["signature", "thinking"]

# 传输错误类型
_TRANSPORT_ERROR_TYPES = frozenset({
    "ReadTimeout", "ConnectTimeout", "PoolTimeout",
    "ConnectError", "RemoteProtocolError",
    "ConnectionError", "ConnectionResetError",
    "ConnectionAbortedError", "BrokenPipeError",
    "TimeoutError", "ReadError",
    "ServerDisconnectedError",
    "APIConnectionError",
    "APITimeoutError",
})

# 服务器断开模式
_SERVER_DISCONNECT_PATTERNS = [
    "server disconnected",
    "peer closed connection",
    "connection reset by peer",
    "connection was closed",
    "network connection lost",
    "unexpected eof",
]


# ============================================================================
# 核心分类函数
# ============================================================================

def classify_api_error(
    error: Exception,
    *,
    provider: str = "",
    model: str = "",
    approx_tokens: int = 0,
    context_length: int = 200000,
    num_messages: int = 0,
) -> ClassifiedError:
    """
    将API错误分类为结构化恢复建议。
    
    优先级pipeline：
    1. Provider-specific模式（thinking签名、tier门控）
    2. HTTP状态码 + 消息精化
    3. 错误码分类
    4. 消息模式匹配
    5. 传输错误启发式
    6. 服务器断开 + 大会话 → 上下文溢出
    7. Fallback: unknown
    
    Args:
        error: API调用抛出的异常
        provider: 当前provider名称
        model: 当前模型
        approx_tokens: 当前上下文的大致token数
        context_length: 当前模型的最大上下文长度
    
    Returns:
        ClassifiedError: 包含原因和恢复动作提示
    """
    status_code = _extract_status_code(error)
    error_type = type(error).__name__
    body = _extract_error_body(error)
    error_code = _extract_error_code(body)
    
    # 构建综合错误消息字符串
    error_msg = _build_error_message(error, body)
    provider_lower = (provider or "").strip().lower()
    
    def _result(reason: FailoverReason, **overrides) -> ClassifiedError:
        defaults = {
            "reason": reason,
            "status_code": status_code,
            "provider": provider,
            "model": model,
            "message": _extract_message(error, body),
        }
        defaults.update(overrides)
        return ClassifiedError(**defaults)
    
    # 1. Provider-specific模式（最高优先级）
    
    # Anthropic thinking block签名无效 (400)
    if (
        status_code == 400
        and "signature" in error_msg
        and "thinking" in error_msg
    ):
        return _result(
            FailoverReason.thinking_signature,
            retryable=True,
            should_compress=False,
        )
    
    # Anthropic长上下文tier门控 (429 "extra usage" + "long context")
    if (
        status_code == 429
        and "extra usage" in error_msg
        and "long context" in error_msg
    ):
        return _result(
            FailoverReason.long_context_tier,
            retryable=True,
            should_compress=True,
        )
    
    # 2. HTTP状态码分类
    if status_code is not None:
        classified = _classify_by_status(
            status_code, error_msg, error_code, body,
            provider=provider_lower,
            approx_tokens=approx_tokens,
            context_length=context_length,
            num_messages=num_messages,
            result_fn=_result,
        )
        if classified is not None:
            return classified
    
    # 3. 错误码分类
    if error_code:
        classified = _classify_by_error_code(error_code, error_msg, _result)
        if classified is not None:
            return classified
    
    # 4. 消息模式分类（无状态码时）
    classified = _classify_by_message(
        error_msg, error_type,
        approx_tokens=approx_tokens,
        context_length=context_length,
        result_fn=_result,
    )
    if classified is not None:
        return classified
    
    # 5. 服务器断开 + 大会话 → 上下文溢出
    is_disconnect = any(p in error_msg for p in _SERVER_DISCONNECT_PATTERNS)
    if is_disconnect and not status_code:
        is_large = (
            approx_tokens > context_length * 0.6 
            or approx_tokens > 120000 
            or num_messages > 200
        )
        if is_large:
            return _result(
                FailoverReason.context_overflow,
                retryable=True,
                should_compress=True,
            )
        return _result(FailoverReason.timeout, retryable=True)
    
    # 6. 传输/超时启发式
    if error_type in _TRANSPORT_ERROR_TYPES or isinstance(error, (TimeoutError, ConnectionError, OSError)):
        return _result(FailoverReason.timeout, retryable=True)
    
    # 7. Fallback: unknown
    return _result(FailoverReason.unknown, retryable=True)


# ============================================================================
# 状态码分类
# ============================================================================

def _classify_by_status(
    status_code: int,
    error_msg: str,
    error_code: str,
    body: dict,
    *,
    provider: str,
    approx_tokens: int,
    context_length: int,
    num_messages: int,
    result_fn,
) -> Optional[ClassifiedError]:
    """基于HTTP状态码分类，带消息精化"""
    
    if status_code == 401:
        return result_fn(
            FailoverReason.auth,
            retryable=False,
            should_rotate_credential=True,
            should_fallback=True,
        )
    
    if status_code == 403:
        if "key limit exceeded" in error_msg or "spending limit" in error_msg:
            return result_fn(
                FailoverReason.billing,
                retryable=False,
                should_rotate_credential=True,
                should_fallback=True,
            )
        return result_fn(
            FailoverReason.auth,
            retryable=False,
            should_fallback=True,
        )
    
    if status_code == 402:
        return _classify_402(error_msg, result_fn)
    
    if status_code == 404:
        if any(p in error_msg for p in _MODEL_NOT_FOUND_PATTERNS):
            return result_fn(
                FailoverReason.model_not_found,
                retryable=False,
                should_fallback=True,
            )
        return result_fn(
            FailoverReason.model_not_found,
            retryable=False,
            should_fallback=True,
        )
    
    if status_code == 413:
        return result_fn(
            FailoverReason.payload_too_large,
            retryable=True,
            should_compress=True,
        )
    
    if status_code == 429:
        # 已在前面检查过long_context_tier
        return result_fn(
            FailoverReason.rate_limit,
            retryable=True,
            should_rotate_credential=True,
            should_fallback=True,
        )
    
    if status_code == 400:
        return _classify_400(
            error_msg, error_code, body,
            approx_tokens=approx_tokens,
            context_length=context_length,
            num_messages=num_messages,
            result_fn=result_fn,
        )
    
    if status_code in (500, 502):
        return result_fn(FailoverReason.server_error, retryable=True)
    
    if status_code in (503, 529):
        return result_fn(FailoverReason.overloaded, retryable=True)
    
    # 其他4xx - 不可重试
    if 400 <= status_code < 500:
        return result_fn(
            FailoverReason.format_error,
            retryable=False,
            should_fallback=True,
        )
    
    # 其他5xx - 可重试
    if 500 <= status_code < 600:
        return result_fn(FailoverReason.server_error, retryable=True)
    
    return None


def _classify_402(error_msg: str, result_fn) -> ClassifiedError:
    """区分402：计费耗尽 vs 临时使用限制"""
    has_usage_limit = any(p in error_msg for p in _USAGE_LIMIT_PATTERNS)
    has_transient_signal = any(p in error_msg for p in _USAGE_LIMIT_TRANSIENT_SIGNALS)
    
    if has_usage_limit and has_transient_signal:
        # 临时配额 - 当作限流处理
        return result_fn(
            FailoverReason.rate_limit,
            retryable=True,
            should_rotate_credential=True,
            should_fallback=True,
        )
    
    # 确认计费耗尽
    return result_fn(
        FailoverReason.billing,
        retryable=False,
        should_rotate_credential=True,
        should_fallback=True,
    )


def _classify_400(
    error_msg: str,
    error_code: str,
    body: dict,
    *,
    approx_tokens: int,
    context_length: int,
    num_messages: int,
    result_fn,
) -> ClassifiedError:
    """分类400错误 - 上下文溢出、格式错误或通用"""
    
    # 上下文溢出
    if any(p in error_msg for p in _CONTEXT_OVERFLOW_PATTERNS):
        return result_fn(
            FailoverReason.context_overflow,
            retryable=True,
            should_compress=True,
        )
    
    # 模型未找到（有些provider用400而不是404）
    if any(p in error_msg for p in _MODEL_NOT_FOUND_PATTERNS):
        return result_fn(
            FailoverReason.model_not_found,
            retryable=False,
            should_fallback=True,
        )
    
    # 有些provider把限流/计费错误当作400返回
    if any(p in error_msg for p in _RATE_LIMIT_PATTERNS):
        return result_fn(
            FailoverReason.rate_limit,
            retryable=True,
            should_rotate_credential=True,
            should_fallback=True,
        )
    if any(p in error_msg for p in _BILLING_PATTERNS):
        return result_fn(
            FailoverReason.billing,
            retryable=False,
            should_rotate_credential=True,
            should_fallback=True,
        )
    
    # 通用400 + 大会话 → 可能是上下文溢出
    err_body_msg = _get_body_message(body)
    is_generic = len(err_body_msg) < 30 or err_body_msg in ("error", "")
    is_large = (
        approx_tokens > context_length * 0.4 
        or approx_tokens > 80000 
        or num_messages > 80
    )
    
    if is_generic and is_large:
        return result_fn(
            FailoverReason.context_overflow,
            retryable=True,
            should_compress=True,
        )
    
    # 不可重试格式错误
    return result_fn(
        FailoverReason.format_error,
        retryable=False,
        should_fallback=True,
    )


# ============================================================================
# 错误码分类
# ============================================================================

def _classify_by_error_code(
    error_code: str,
    error_msg: str,
    result_fn,
) -> Optional[ClassifiedError]:
    """基于响应体中的结构化错误码分类"""
    code_lower = error_code.lower()
    
    if code_lower in ("resource_exhausted", "throttled", "rate_limit_exceeded"):
        return result_fn(
            FailoverReason.rate_limit,
            retryable=True,
            should_rotate_credential=True,
        )
    
    if code_lower in ("insufficient_quota", "billing_not_active", "payment_required"):
        return result_fn(
            FailoverReason.billing,
            retryable=False,
            should_rotate_credential=True,
            should_fallback=True,
        )
    
    if code_lower in ("model_not_found", "model_not_available", "invalid_model"):
        return result_fn(
            FailoverReason.model_not_found,
            retryable=False,
            should_fallback=True,
        )
    
    if code_lower in ("context_length_exceeded", "max_tokens_exceeded"):
        return result_fn(
            FailoverReason.context_overflow,
            retryable=True,
            should_compress=True,
        )
    
    return None


# ============================================================================
# 消息模式分类
# ============================================================================

def _classify_by_message(
    error_msg: str,
    error_type: str,
    *,
    approx_tokens: int,
    context_length: int,
    result_fn,
) -> Optional[ClassifiedError]:
    """当没有状态码时，基于错误消息模式分类"""
    
    # 载荷过大
    if any(p in error_msg for p in _PAYLOAD_TOO_LARGE_PATTERNS):
        return result_fn(
            FailoverReason.payload_too_large,
            retryable=True,
            should_compress=True,
        )
    
    # 使用限制需要区分
    has_usage_limit = any(p in error_msg for p in _USAGE_LIMIT_PATTERNS)
    if has_usage_limit:
        has_transient_signal = any(p in error_msg for p in _USAGE_LIMIT_TRANSIENT_SIGNALS)
        if has_transient_signal:
            return result_fn(
                FailoverReason.rate_limit,
                retryable=True,
                should_rotate_credential=True,
                should_fallback=True,
            )
        return result_fn(
            FailoverReason.billing,
            retryable=False,
            should_rotate_credential=True,
            should_fallback=True,
        )
    
    # 计费模式
    if any(p in error_msg for p in _BILLING_PATTERNS):
        return result_fn(
            FailoverReason.billing,
            retryable=False,
            should_rotate_credential=True,
            should_fallback=True,
        )
    
    # 限流模式
    if any(p in error_msg for p in _RATE_LIMIT_PATTERNS):
        return result_fn(
            FailoverReason.rate_limit,
            retryable=True,
            should_rotate_credential=True,
            should_fallback=True,
        )
    
    # 上下文溢出模式
    if any(p in error_msg for p in _CONTEXT_OVERFLOW_PATTERNS):
        return result_fn(
            FailoverReason.context_overflow,
            retryable=True,
            should_compress=True,
        )
    
    # 认证模式
    if any(p in error_msg for p in _AUTH_PATTERNS):
        return result_fn(
            FailoverReason.auth,
            retryable=False,
            should_rotate_credential=True,
            should_fallback=True,
        )
    
    # 模型未找到模式
    if any(p in error_msg for p in _MODEL_NOT_FOUND_PATTERNS):
        return result_fn(
            FailoverReason.model_not_found,
            retryable=False,
            should_fallback=True,
        )
    
    return None


# ============================================================================
# 辅助函数
# ============================================================================

def _extract_status_code(error: Exception) -> Optional[int]:
    """遍历错误及原因链找到HTTP状态码"""
    current = error
    for _ in range(5):
        code = getattr(current, "status_code", None)
        if isinstance(code, int):
            return code
        code = getattr(current, "status", None)
        if isinstance(code, int) and 100 <= code < 600:
            return code
        cause = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
        if cause is None or cause is current:
            break
        current = cause
    return None


def _extract_error_body(error: Exception) -> dict:
    """从SDK异常中提取结构化错误体"""
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        return body
    response = getattr(error, "response", None)
    if response is not None:
        try:
            json_body = response.json()
            if isinstance(json_body, dict):
                return json_body
        except Exception:
            pass
    return {}


def _extract_error_code(body: dict) -> str:
    """从响应体提取错误码字符串"""
    if not body:
        return ""
    error_obj = body.get("error", {})
    if isinstance(error_obj, dict):
        code = error_obj.get("code") or error_obj.get("type") or ""
        if isinstance(code, str) and code.strip():
            return code.strip()
    code = body.get("code") or body.get("error_code") or ""
    if isinstance(code, (str, int)):
        return str(code).strip()
    return ""


def _extract_message(error: Exception, body: dict) -> str:
    """提取信息量最大的错误消息"""
    if body:
        error_obj = body.get("error", {})
        if isinstance(error_obj, dict):
            msg = error_obj.get("message", "")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()[:500]
        msg = body.get("message", "")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()[:500]
    return str(error)[:500]


def _get_body_message(body: dict) -> str:
    """从body中提取消息内容"""
    if not body:
        return ""
    error_obj = body.get("error", {})
    if isinstance(error_obj, dict):
        msg = error_obj.get("message", "") or ""
        if msg:
            return msg.strip().lower()
    msg = body.get("message", "") or ""
    return msg.strip().lower()


def _build_error_message(error: Exception, body: dict) -> str:
    """构建用于模式匹配的综合错误消息字符串"""
    parts = [str(error).lower()]
    
    if isinstance(body, dict):
        error_obj = body.get("error", {})
        if isinstance(error_obj, dict):
            msg = error_obj.get("message", "")
            if msg and msg.lower() not in parts[0]:
                parts.append(msg.lower())
        elif not error_obj:
            msg = body.get("message", "")
            if msg:
                parts.append(msg.lower())
    
    return " ".join(parts)


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Error Classifier 测试")
    print("=" * 60)
    
    # 测试1: 401认证错误
    print("\n[测试1] 401认证错误")
    class Fake401Error(Exception):
        status_code = 401
    err = Fake401Error("Invalid API key")
    result = classify_api_error(err, provider="openai", model="gpt-4o")
    print(f"  reason: {result.reason.value}")
    print(f"  retryable: {result.retryable}")
    print(f"  should_rotate_credential: {result.should_rotate_credential}")
    assert result.reason == FailoverReason.auth
    print("  ✅ 通过")
    
    # 测试2: 429限流
    print("\n[测试2] 429限流")
    class Fake429Error(Exception):
        status_code = 429
    err = Fake429Error("Rate limit exceeded")
    result = classify_api_error(err, provider="openai", model="gpt-4o")
    print(f"  reason: {result.reason.value}")
    print(f"  retryable: {result.retryable}")
    print(f"  should_rotate_credential: {result.should_rotate_credential}")
    assert result.reason == FailoverReason.rate_limit
    print("  ✅ 通过")
    
    # 测试3: 上下文溢出
    print("\n[测试3] 上下文溢出")
    class Fake400Error(Exception):
        status_code = 400
        body = {"error": {"message": "Context length exceeded"}}
    err = Fake400Error()
    result = classify_api_error(
        err, 
        provider="anthropic", 
        model="claude-3-opus",
        approx_tokens=180000,
        context_length=200000
    )
    print(f"  reason: {result.reason.value}")
    print(f"  should_compress: {result.should_compress}")
    assert result.reason == FailoverReason.context_overflow
    print("  ✅ 通过")
    
    # 测试4: 404模型未找到
    print("\n[测试4] 404模型未找到")
    class Fake404Error(Exception):
        status_code = 404
        body = {"error": {"message": "Model not found"}}
    err = Fake404Error()
    result = classify_api_error(err, provider="openai", model="gpt-6")
    print(f"  reason: {result.reason.value}")
    print(f"  should_fallback: {result.should_fallback}")
    assert result.reason == FailoverReason.model_not_found
    print("  ✅ 通过")
    
    # 测试5: 计费错误
    print("\n[测试5] 402计费错误")
    class Fake402Error(Exception):
        status_code = 402
        body = {"error": {"message": "Insufficient credits"}}
    err = Fake402Error()
    result = classify_api_error(err, provider="openai", model="gpt-4o")
    print(f"  reason: {result.reason.value}")
    print(f"  should_rotate_credential: {result.should_rotate_credential}")
    assert result.reason == FailoverReason.billing
    print("  ✅ 通过")
    
    # 测试6: 超时
    print("\n[测试6] 超时")
    class FakeTimeoutError(TimeoutError):
        pass
    err = FakeTimeoutError("Connection timed out")
    result = classify_api_error(err)
    print(f"  reason: {result.reason.value}")
    print(f"  retryable: {result.retryable}")
    assert result.reason == FailoverReason.timeout
    print("  ✅ 通过")
    
    # 测试7: 500服务器错误
    print("\n[测试7] 500服务器错误")
    class Fake500Error(Exception):
        status_code = 500
    err = Fake500Error("Internal server error")
    result = classify_api_error(err)
    print(f"  reason: {result.reason.value}")
    print(f"  retryable: {result.retryable}")
    assert result.reason == FailoverReason.server_error
    print("  ✅ 通过")
    
    # 测试8: 上下文溢出（无状态码）
    print("\n[测试8] 上下文溢出（消息模式匹配）")
    class FakeGenericError(Exception):
        body = {}
    err = FakeGenericError("context length exceeded")
    result = classify_api_error(err, approx_tokens=150000, context_length=200000)
    print(f"  reason: {result.reason.value}")
    print(f"  should_compress: {result.should_compress}")
    assert result.reason == FailoverReason.context_overflow
    print("  ✅ 通过")
    
    # 测试9: 限流消息模式
    print("\n[测试9] 限流消息模式")
    class FakeRateLimitError(Exception):
        body = {"error": {"message": "Too many requests, try again in 5 minutes"}}
    err = FakeRateLimitError()
    result = classify_api_error(err)
    print(f"  reason: {result.reason.value}")
    assert result.reason == FailoverReason.rate_limit
    print("  ✅ 通过")
    
    # 测试10: 认证失败消息模式
    print("\n[测试10] 认证失败消息模式")
    class FakeAuthError(Exception):
        body = {}
    err = FakeAuthError("invalid api key")
    result = classify_api_error(err)
    print(f"  reason: {result.reason.value}")
    print(f"  should_rotate_credential: {result.should_rotate_credential}")
    assert result.reason == FailoverReason.auth
    print("  ✅ 通过")
    
    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)