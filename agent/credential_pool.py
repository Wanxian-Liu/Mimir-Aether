"""
MimirAether Credential Pool

简化版凭证池管理，支持多凭证Failover。

学习自Hermes credential_pool设计思路：
- 凭证池管理
- 多策略选择
- 状态追踪（ok/exhausted）
- 租约管理

核心原则：
- 不复制Hermes特定模块依赖
- 简化实现，专注核心功能
- 支持多provider
"""

import base64
import json
import logging
import os
import random
import re
import threading
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field, fields, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# SA-03: import removal contract so remove_index cleans external state too
try:
    from .credential_sources import find_removal_step as _find_removal_step
except ImportError:
    _find_removal_step = None

# ============================================================================
# 常量
# ============================================================================

STATUS_OK = "ok"
STATUS_EXHAUSTED = "exhausted"

AUTH_TYPE_API_KEY = "api_key"
AUTH_TYPE_OAUTH = "oauth"

SOURCE_MANUAL = "manual"

# 选择策略
STRATEGY_FILL_FIRST = "fill_first"
STRATEGY_ROUND_ROBIN = "round_robin"
STRATEGY_RANDOM = "random"
STRATEGY_LEAST_USED = "least_used"

SUPPORTED_STRATEGIES = {
    STRATEGY_FILL_FIRST,
    STRATEGY_ROUND_ROBIN,
    STRATEGY_RANDOM,
    STRATEGY_LEAST_USED,
}

# 耗尽冷却时间（秒）
EXHAUSTED_TTL_429 = 3600  # 1小时
EXHAUSTED_TTL_DEFAULT = 3600  # 1小时

# 凭证文件路径（项目树下 data/credentials）
CREDENTIAL_POOL_FILE = "credential_pool.json"


def _default_credentials_dir() -> Path:
    from mimir_constants import get_mimir_data_dir

    return get_mimir_data_dir() / "credentials"

# ============================================================================
# JWT 工具函数
# ============================================================================

def _decode_jwt_claims(token: Any) -> Dict[str, Any]:
    """解码JWT Token的claims payload

    学习自Hermes auth._decode_jwt_claims:
    纯函数，返回claims字典或空字典。
    """
    if not isinstance(token, str) or token.count(".") != 2:
        return {}
    payload = token.split(".")[1]
    payload += "=" * ((4 - len(payload) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload.encode("utf-8"))
        claims = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return claims if isinstance(claims, dict) else {}


def _codex_access_token_is_expiring(access_token: str, skew_seconds: int = 120) -> bool:
    """检查Codex JWT access token是否即将过期

    学习自Hermes auth._codex_access_token_is_expiring:
    解码JWT的exp字段，在过期前skew_seconds秒视为即将过期。
    """
    claims = _decode_jwt_claims(access_token)
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        return False
    return float(exp) <= (time.time() + max(0, int(skew_seconds)))


# Codex OAuth 配置常量
CODEX_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_ACCESS_TOKEN_REFRESH_SKEW_SECONDS = 120


# ============================================================================
# Codex CLI Token I/O
# ============================================================================

def _import_codex_cli_tokens() -> Optional[Dict[str, str]]:
    """从 ~/.codex/auth.json 读取Codex CLI tokens

    学习自Hermes auth._import_codex_cli_tokens:
    - 读取Codex CLI共享的auth.json
    - 仅返回有效且未过期的tokens
    - 过期的token会被拒绝导入
    """
    codex_home = os.getenv("CODEX_HOME", "").strip()
    if not codex_home:
        codex_home = str(Path.home() / ".codex")
    auth_path = Path(codex_home).expanduser() / "auth.json"
    if not auth_path.is_file():
        return None
    try:
        payload = json.loads(auth_path.read_text())
        tokens = payload.get("tokens")
        if not isinstance(tokens, dict):
            return None
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        if not access_token or not refresh_token:
            return None
        if _codex_access_token_is_expiring(access_token, 0):
            logger.debug("Codex CLI tokens at %s are expired — skipping import.", auth_path)
            return None
        return dict(tokens)
    except Exception:
        return None


def _write_codex_cli_tokens(
    access_token: str,
    refresh_token: str,
    *,
    last_refresh: Optional[str] = None,
) -> None:
    """将刷新后的tokens写回 ~/.codex/auth.json

    学习自Hermes auth._write_codex_cli_tokens:
    OpenAI OAuth refresh tokens是单次使用的，每次刷新后都会轮换。
    如果不写回，Codex CLI下次刷新时会遇到refresh_token_reused错误。
    """
    codex_home = os.getenv("CODEX_HOME", "").strip()
    if not codex_home:
        codex_home = str(Path.home() / ".codex")
    auth_path = Path(codex_home).expanduser() / "auth.json"
    try:
        existing: Dict[str, Any] = {}
        if auth_path.is_file():
            existing = json.loads(auth_path.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            existing = {}

        tokens_dict = existing.get("tokens")
        if not isinstance(tokens_dict, dict):
            tokens_dict = {}
        tokens_dict["access_token"] = access_token
        tokens_dict["refresh_token"] = refresh_token
        existing["tokens"] = tokens_dict
        if last_refresh is not None:
            existing["last_refresh"] = last_refresh

        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        auth_path.chmod(0o600)
        # 修复（2026-08-05）：写失败升级为error级（OpenClaw发现P2——原debug级是监控盲区）
        logger.info("Refreshed Codex tokens written to %s (0o600)", auth_path)
    except (OSError, IOError) as exc:
        logger.error("Failed to write refreshed tokens to %s: %s", auth_path, exc)


# ============================================================================
# Codex OAuth 刷新 (Pure Function)
# ============================================================================

def refresh_codex_oauth_pure(
    access_token: str,
    refresh_token: str,
    *,
    timeout_seconds: float = 20.0,
) -> Dict[str, Any]:
    """刷新Codex OAuth Token（纯函数，不修改任何本地状态）

    学习自Hermes auth.refresh_codex_oauth_pure:
    - 向OpenAI OAuth token endpoint发起refresh_token grant
    - 使用urllib同步HTTP
    - 返回新token对，不写任何本地文件

    Args:
        access_token: 当前access token（仅用于调用方判断是否需刷新）
        refresh_token: OAuth refresh token
        timeout_seconds: HTTP超时

    Returns:
        Dict with access_token, refresh_token, last_refresh

    Raises:
        RuntimeError: 刷新失败
    """
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        raise RuntimeError("Codex auth is missing refresh_token. Run `codex` to re-authenticate.")

    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CODEX_OAUTH_CLIENT_ID,
    }).encode()

    req = urllib.request.Request(
        CODEX_OAUTH_TOKEN_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            response_payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read().decode())
        except Exception:
            err = {}
        if isinstance(err, dict):
            err_desc = err.get("error_description") or err.get("message") or ""
            if err_desc:
                raise RuntimeError(f"Codex token refresh failed: {err_desc}")
        raise RuntimeError(f"Codex token refresh failed with status {exc.code}.")
    except Exception as exc:
        raise RuntimeError(f"Codex token refresh request failed: {exc}")

    refreshed_access = response_payload.get("access_token")
    if not isinstance(refreshed_access, str) or not refreshed_access.strip():
        raise RuntimeError("Codex token refresh response was missing access_token.")

    updated = {
        "access_token": refreshed_access.strip(),
        "refresh_token": refresh_token.strip(),
        "last_refresh": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    next_refresh = response_payload.get("refresh_token")
    if isinstance(next_refresh, str) and next_refresh.strip():
        updated["refresh_token"] = next_refresh.strip()
    return updated

# ============================================================================
# 数据类
# ============================================================================

@dataclass
class PooledCredential:
    """池化凭证"""
    provider: str
    id: str
    label: str
    auth_type: str = AUTH_TYPE_API_KEY
    priority: int = 0
    source: str = SOURCE_MANUAL
    access_token: str = ""
    refresh_token: Optional[str] = None
    last_status: Optional[str] = STATUS_OK
    last_status_at: Optional[float] = None
    last_error_code: Optional[int] = None
    last_error_reason: Optional[str] = None
    last_error_message: Optional[str] = None
    last_error_reset_at: Optional[float] = None
    base_url: Optional[str] = None
    expires_at: Optional[str] = None
    expires_at_ms: Optional[int] = None
    request_count: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, provider: str, payload: Dict[str, Any]) -> "PooledCredential":
        """从字典创建凭证"""
        known_fields = {
            "id", "label", "auth_type", "priority", "source",
            "access_token", "refresh_token", "last_status", "last_status_at",
            "last_error_code", "last_error_reason", "last_error_message",
            "last_error_reset_at", "base_url", "expires_at", "expires_at_ms",
            "request_count",
        }
        data = {k: payload.get(k) for k in known_fields if k in payload}
        data.setdefault("id", uuid.uuid4().hex[:6])
        data.setdefault("label", payload.get("source", provider))
        data.setdefault("auth_type", AUTH_TYPE_API_KEY)
        data.setdefault("priority", 0)
        data.setdefault("source", SOURCE_MANUAL)
        data.setdefault("access_token", "")
        data.setdefault("request_count", 0)
        data["extra"] = {k: v for k, v in payload.items() if k not in known_fields and v is not None}
        return cls(provider=provider, **data)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        always_emit = {
            "last_status", "last_status_at", "last_error_code",
            "last_error_reason", "last_error_message", "last_error_reset_at",
        }
        result = {}
        for key in ("provider", "id", "label", "auth_type", "priority", "source",
                    "access_token", "refresh_token", "last_status", "last_status_at",
                    "last_error_code", "last_error_reason", "last_error_message",
                    "last_error_reset_at", "base_url", "expires_at", "expires_at_ms",
                    "request_count"):
            value = getattr(self, key, None)
            if value is not None or key in always_emit:
                result[key] = value
        if self.extra:
            result.update(self.extra)
        return result

    @property
    def runtime_api_key(self) -> str:
        """运行时API Key"""
        return str(self.access_token or "")

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at_ms is None:
            return False
        return int(time.time() * 1000) >= self.expires_at_ms

    def needs_refresh(self) -> bool:
        """检查是否需要刷新"""
        if self.auth_type != AUTH_TYPE_OAUTH:
            return False
        if not self.refresh_token:
            return False
        # 提前2分钟刷新
        if self.expires_at_ms:
            return int(time.time() * 1000) >= (self.expires_at_ms - 120_000)
        return False


# ============================================================================
# 工具函数
# ============================================================================

def _exhausted_ttl(error_code: Optional[int]) -> int:
    """根据错误码返回冷却时间"""
    if error_code == 429:
        return EXHAUSTED_TTL_429
    return EXHAUSTED_TTL_DEFAULT


def _parse_timestamp(value: Any) -> Optional[float]:
    """解析时间戳（支持秒、毫秒、ISO-8601）"""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric <= 0:
            return None
        # 毫秒检测
        return numeric / 1000.0 if numeric > 1_000_000_000_000 else numeric
    if isinstance(value, str):
        try:
            numeric = float(value.strip())
            return numeric / 1000.0 if numeric > 1_000_000_000_000 else numeric
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _exhausted_until(entry: PooledCredential) -> Optional[float]:
    """获取耗尽截止时间"""
    if entry.last_status != STATUS_EXHAUSTED:
        return None
    reset_at = _parse_timestamp(getattr(entry, "last_error_reset_at", None))
    if reset_at is not None:
        return reset_at
    if entry.last_status_at:
        return entry.last_status_at + _exhausted_ttl(entry.last_error_code)
    return None


def _next_priority(entries: List[PooledCredential]) -> int:
    """生成下一个优先级"""
    return max((entry.priority for entry in entries), default=-1) + 1


# ============================================================================
# Hermès兼容常量
# ============================================================================

CUSTOM_POOL_PREFIX = "custom:"
EXHAUSTED_TTL_429_SECONDS = 3600  # 1小时
EXHAUSTED_TTL_DEFAULT_SECONDS = 3600  # 1小时


# ============================================================================
# Hermès兼容凭证工具函数
# ============================================================================

def _is_manual_source(source: str) -> bool:
    """检查source是否为manual来源（Hermès兼容）"""
    normalized = (source or "").strip().lower()
    return normalized == SOURCE_MANUAL or normalized.startswith(f"{SOURCE_MANUAL}:")


def _parse_absolute_timestamp(value: Any) -> Optional[float]:
    """解析时间戳，支持秒、毫秒、ISO-8601（Hermès兼容签名）"""
    return _parse_timestamp(value)  # 复用现有的_parse_timestamp


def _extract_retry_delay_seconds(message: str) -> Optional[float]:
    """从错误消息中提取重试延迟（Hermès兼容）"""
    if not message:
        return None
    # 尝试 quotaResetDelay:XXXms/s 格式
    import re
    delay_match = re.search(r"quotaResetDelay[:\s\"]+(\d+(?:\.\d+)?)(ms|s)", message, re.IGNORECASE)
    if delay_match:
        value = float(delay_match.group(1))
        return value / 1000.0 if delay_match.group(2).lower() == "ms" else value
    # 尝试 retry after X seconds 格式
    sec_match = re.search(r"retry\s+(?:after\s+)?(\d+(?:\.\d+)?)\s*(?:sec|secs|seconds|s\b)", message, re.IGNORECASE)
    if sec_match:
        return float(sec_match.group(1))
    return None


def _normalize_error_context(error_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """标准化错误上下文（Hermès兼容）"""
    if not isinstance(error_context, dict):
        return {}
    normalized: Dict[str, Any] = {}
    reason = error_context.get("reason")
    if isinstance(reason, str) and reason.strip():
        normalized["reason"] = reason.strip()
    message = error_context.get("message")
    if isinstance(message, str) and message.strip():
        normalized["message"] = message.strip()
    reset_at = (
        error_context.get("reset_at")
        or error_context.get("resets_at")
        or error_context.get("retry_until")
    )
    parsed_reset_at = _parse_absolute_timestamp(reset_at)
    if parsed_reset_at is None and isinstance(message, str):
        retry_delay_seconds = _extract_retry_delay_seconds(message)
        if retry_delay_seconds is not None:
            parsed_reset_at = time.time() + retry_delay_seconds
    if parsed_reset_at is not None:
        normalized["reset_at"] = parsed_reset_at
    return normalized


def _normalize_custom_pool_name(name: str) -> str:
    """标准化自定义provider名称作为pool key后缀（Hermès兼容）"""
    return name.strip().lower().replace(" ", "-")


def _iter_custom_providers(config: Optional[dict] = None) -> Any:
    """遍历custom_providers配置（Hermès兼容）"""
    # MimirAether版本：简化实现
    if config is None:
        config = {}
    custom_providers = config.get("custom_providers", [])
    if not isinstance(custom_providers, list):
        return
    for entry in custom_providers:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        yield _normalize_custom_pool_name(name), entry


def get_custom_provider_pool_key(base_url: str) -> Optional[str]:
    """根据base_url查找对应的custom:* pool key（Hermès兼容）"""
    if not base_url:
        return None
    normalized_url = base_url.strip().rstrip("/")
    # 简化实现：遍历配置
    try:
        config = _load_config_safe() or {}
        for norm_name, entry in _iter_custom_providers(config):
            entry_url = str(entry.get("base_url") or "").strip().rstrip("/")
            if entry_url and entry_url == normalized_url:
                return f"{CUSTOM_POOL_PREFIX}{norm_name}"
    except Exception:
        pass
    return None


def list_custom_pool_providers() -> List[str]:
    """返回所有有条目的custom:* pool keys（Hermès兼容）"""
    result = []
    try:
        cred_dir = _default_credentials_dir()
        if cred_dir.exists():
            for provider_dir in cred_dir.iterdir():
                if provider_dir.is_dir() and provider_dir.name.startswith("custom:"):
                    pool_file = provider_dir / CREDENTIAL_POOL_FILE
                    if pool_file.exists():
                        try:
                            data = json.loads(pool_file.read_text())
                            if data:
                                result.append(provider_dir.name)
                        except Exception:
                            pass
    except Exception:
        pass
    return sorted(result)


def _get_custom_provider_config(pool_key: str) -> Optional[Dict[str, Any]]:
    """返回匹配pool key的custom_providers配置条目（Hermès兼容）"""
    if not pool_key.startswith(CUSTOM_POOL_PREFIX):
        return None
    suffix = pool_key[len(CUSTOM_POOL_PREFIX):]
    try:
        config = _load_config_safe() or {}
        for norm_name, entry in _iter_custom_providers(config):
            if norm_name == suffix:
                return entry
    except Exception:
        pass
    return None


def get_pool_strategy(provider: str) -> str:
    """返回provider配置的选择策略（Hermès兼容）"""
    # MimirAether简化版本：只支持fill_first
    return STRATEGY_FILL_FIRST


def label_from_token(token: str, fallback: str) -> str:
    """从JWT token中提取label（email/username）（Hermès兼容）"""
    try:
        import base64, json
        parts = token.split(".")
        if len(parts) >= 2:
            payload = parts[1]
            # URL-safe base64
            payload = payload.replace("-", "+").replace("_", "/")
            # 填充
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding
            decoded = base64.b64decode(payload)
            claims = json.loads(decoded)
            for key in ("email", "preferred_username", "upn"):
                value = claims.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    except Exception:
        pass
    return fallback


def _normalize_pool_priorities(provider: str, entries: List[PooledCredential]) -> bool:
    """规范化Anthropic provider的凭证优先级（Hermès兼容）"""
    if provider != "anthropic":
        return False

    source_rank = {
        "env:ANTHROPIC_TOKEN": 0,
        "env:CLAUDE_CODE_OAUTH_TOKEN": 1,
        "hermes_pkce": 2,
        "claude_code": 3,
        "env:ANTHROPIC_API_KEY": 4,
    }
    manual_entries = sorted(
        (entry for entry in entries if _is_manual_source(entry.source)),
        key=lambda entry: entry.priority,
    )
    seeded_entries = sorted(
        (entry for entry in entries if not _is_manual_source(entry.source)),
        key=lambda entry: (
            source_rank.get(entry.source, len(source_rank)),
            entry.priority,
            entry.label,
        ),
    )

    ordered = [*manual_entries, *seeded_entries]
    id_to_idx = {entry.id: idx for idx, entry in enumerate(entries)}
    changed = False
    for new_priority, entry in enumerate(ordered):
        if entry.priority != new_priority:
            entries[id_to_idx[entry.id]] = replace(entry, priority=new_priority)
            changed = True
    return changed


def _prune_stale_seeded_entries(entries: List[PooledCredential], active_sources: Set[str]) -> bool:
    """删除不再活跃的seeded条目（Hermès兼容）"""
    retained = [
        entry
        for entry in entries
        if _is_manual_source(entry.source)
        or entry.source in active_sources
        or not (
            entry.source.startswith("env:")
            or entry.source in {"claude_code", "hermes_pkce"}
        )
    ]
    if len(retained) == len(entries):
        return False
    entries[:] = retained
    return True


def _seed_from_singletons(provider: str, entries: List[PooledCredential]) -> Tuple[bool, Set[str]]:
    """从单例凭证（如环境变量）seed池（Hermès兼容，简化版）"""
    changed = False
    active_sources: Set[str] = set()

    # 简化实现：只处理环境变量
    env_mappings = {
        "openai": ("OPENAI_API_KEY", None),
        "anthropic": ("ANTHROPIC_API_KEY", None),
    }

    if provider in env_mappings:
        env_var, base_url = env_mappings[provider]
        token = os.getenv(env_var, "").strip()
        if token:
            source = f"env:{env_var}"
            active_sources.add(source)
            changed |= _upsert_entry_standalone(entries, provider, source, {
                "source": source,
                "auth_type": AUTH_TYPE_API_KEY,
                "access_token": token,
                "base_url": base_url or "",
                "label": env_var,
            })

    return changed, active_sources


def _seed_custom_pool(pool_key: str, entries: List[PooledCredential]) -> Tuple[bool, Set[str]]:
    """从custom_providers配置seed自定义endpoint池（Hermès兼容）"""
    changed = False
    active_sources: Set[str] = set()

    cp_config = _get_custom_provider_config(pool_key)
    if cp_config:
        api_key = str(cp_config.get("api_key") or "").strip()
        base_url = str(cp_config.get("base_url") or "").strip().rstrip("/")
        name = str(cp_config.get("name") or "").strip()
        if api_key:
            source = f"config:{name}"
            active_sources.add(source)
            changed |= _upsert_entry_standalone(entries, pool_key, source, {
                "source": source,
                "auth_type": AUTH_TYPE_API_KEY,
                "access_token": api_key,
                "base_url": base_url,
                "label": name or source,
            })

    return changed, active_sources


def _upsert_entry_standalone(
    entries: List[PooledCredential],
    provider: str,
    source: str,
    payload: Dict[str, Any],
) -> bool:
    """在entries列表中upsert条目（standalone版本）"""
    existing_idx = None
    for idx, entry in enumerate(entries):
        if entry.source == source:
            existing_idx = idx
            break

    if existing_idx is None:
        payload.setdefault("id", uuid.uuid4().hex[:6])
        payload.setdefault("priority", _next_priority(entries))
        payload.setdefault("label", payload.get("label") or source)
        entries.append(PooledCredential.from_dict(provider, payload))
        return True

    existing = entries[existing_idx]
    field_updates = {}
    extra_updates = {}
    field_names = {f.name for f in fields(existing) if f.name != "provider"}
    for key, value in payload.items():
        if key in {"id", "priority"} or value is None:
            continue
        if key == "label" and existing.label:
            continue
        if key in field_names:
            if getattr(existing, key) != value:
                field_updates[key] = value
        else:
            if existing.extra.get(key) != value:
                extra_updates[key] = value
    if field_updates or extra_updates:
        if extra_updates:
            field_updates["extra"] = {**existing.extra, **extra_updates}
        entries[existing_idx] = replace(existing, **field_updates)
        return True
    return False


# ============================================================================
# PooledCredential Hermès兼容方法
# ============================================================================

def _pooled_credential_post_init(self) -> None:
    """PooledCredential __post_init__（Hermès兼容）"""
    if self.extra is None:
        self.extra = {}


def _pooled_credential_getattr(self, name: str) -> Any:
    """PooledCredential __getattr__（Hermès兼容）"""
    if name == "extra":
        return getattr(self, "extra", {})
    # 检查extra字段
    try:
        extra = object.__getattribute__(self, "extra")
        if name in extra:
            return extra[name]
    except AttributeError:
        pass
    raise AttributeError(f"'{type(self).__name__}' object has no attribute {name!r}")


# 为PooledCredential添加 Hermès兼容方法


def _pooled_credential_runtime_base_url(self) -> Optional[str]:
    """PooledCredential.runtime_base_url（Hermès兼容）"""
    return getattr(self, "base_url", None)


# 添加runtime_base_url属性到PooledCredential
PooledCredential.runtime_base_url = property(_pooled_credential_runtime_base_url)

# 添加__getattr__到PooledCredential
PooledCredential.__getattr__ = _pooled_credential_getattr

# 添加__post_init__到PooledCredential（dataclass方法覆盖）
PooledCredential.__post_init__ = _pooled_credential_post_init


# ============================================================================
# 凭证池
# ============================================================================

class CredentialPool:
    """
    凭证池管理器
    
    支持：
    - 多凭证存储
    - 多种选择策略
    - 状态追踪（ok/exhausted）
    - 租约管理
    - 持久化
    """
    
    def __init__(
        self,
        provider: str,
        entries: Optional[List[PooledCredential]] = None,
        strategy: str = STRATEGY_FILL_FIRST,
        auto_seed_env: bool = True,
    ):
        self.provider = provider
        self._entries = sorted(entries or [], key=lambda e: e.priority)
        self._strategy = strategy if strategy in SUPPORTED_STRATEGIES else STRATEGY_FILL_FIRST
        self._current_id: Optional[str] = None
        self._lock = threading.Lock()
        self._active_leases: Dict[str, int] = {}
        self._max_concurrent = 1  # 默认每个凭证同时只能有一个租约
        self._round_robin_index = 0
        
        # 自动从环境变量加载凭证
        if auto_seed_env:
            self._seed_from_env()
    
    @property
    def strategy(self) -> str:
        return self._strategy
    
    @property
    def entries(self) -> List[PooledCredential]:
        return list(self._entries)
    
    def has_credentials(self) -> bool:
        """是否有凭证"""
        return bool(self._entries)
    
    def has_available(self) -> bool:
        """是否有可用凭证（不在冷却中）"""
        return bool(self._available_entries())
    
    def current(self) -> Optional[PooledCredential]:
        """获取当前选中的凭证"""
        if not self._current_id:
            return None
        return next((e for e in self._entries if e.id == self._current_id), None)
    
    def _persist(self) -> None:
        """持久化到磁盘"""
        try:
            _default_credentials_dir().mkdir(parents=True, exist_ok=True)
            # 每个provider一个子目录
            provider_dir = _default_credentials_dir() / self.provider
            provider_dir.mkdir(parents=True, exist_ok=True)
            filepath = provider_dir / CREDENTIAL_POOL_FILE
            data = [entry.to_dict() for entry in self._entries]
            filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            logger.debug(f"Credential pool persisted: {self.provider}")
        except Exception as e:
            logger.warning(f"Failed to persist credential pool: {e}")
    
    def _replace_entry(self, old: PooledCredential, new: PooledCredential) -> None:
        """替换凭证"""
        for idx, entry in enumerate(self._entries):
            if entry.id == old.id:
                self._entries[idx] = new
                return
    
    def _available_entries(self, *, clear_expired: bool = False) -> List[PooledCredential]:
        """获取可用凭证列表"""
        now = time.time()
        available = []
        cleared_any = False
        
        for entry in self._entries:
            # 检查耗尽状态
            if entry.last_status == STATUS_EXHAUSTED:
                exhausted_until = _exhausted_until(entry)
                if exhausted_until is not None and now < exhausted_until:
                    continue
                # 冷却期已过，清除耗尽状态
                if clear_expired:
                    cleared = replace(
                        entry,
                        last_status=STATUS_OK,
                        last_status_at=None,
                        last_error_code=None,
                        last_error_reason=None,
                        last_error_message=None,
                        last_error_reset_at=None,
                    )
                    self._replace_entry(entry, cleared)
                    entry = cleared
                    cleared_any = True
            available.append(entry)
        
        if cleared_any:
            self._persist()
        
        return available
    
    def _select_unlocked(self) -> Optional[PooledCredential]:
        """非线程安全的选择逻辑"""
        available = self._available_entries(clear_expired=True)
        if not available:
            self._current_id = None
            logger.info(f"Credential pool [{self.provider}]: no available entries")
            return None
        
        # 根据策略选择
        if self._strategy == STRATEGY_RANDOM:
            entry = random.choice(available)
            self._current_id = entry.id
            return entry
        
        if self._strategy == STRATEGY_LEAST_USED and len(available) > 1:
            entry = min(available, key=lambda e: e.request_count)
            self._current_id = entry.id
            return entry
        
        if self._strategy == STRATEGY_ROUND_ROBIN and len(available) > 1:
            self._round_robin_index = (self._round_robin_index + 1) % len(available)
            entry = available[self._round_robin_index]
            self._current_id = entry.id
            return entry
        
        # 默认fill_first
        entry = available[0]
        self._current_id = entry.id
        return entry
    
    def select(self) -> Optional[PooledCredential]:
        """选择凭证"""
        with self._lock:
            return self._select_unlocked()
    
    def peek(self) -> Optional[PooledCredential]:
        """查看可用凭证（不选中）"""
        with self._lock:
            current = self.current()
            if current is not None:
                return current
            available = self._available_entries()
            return available[0] if available else None
    
    def mark_exhausted(
        self,
        entry: Optional[PooledCredential] = None,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """标记凭证为耗尽状态"""
        with self._lock:
            target = entry or self.current()
            if target is None:
                return
            
            updated = replace(
                target,
                last_status=STATUS_EXHAUSTED,
                last_status_at=time.time(),
                last_error_code=status_code,
                last_error_message=error_message,
            )
            self._replace_entry(target, updated)
            self._persist()
            
            if self._current_id == target.id:
                self._current_id = None
                # 自动轮换到下一个
                self._select_unlocked()
            
            logger.info(f"Credential [{target.label}] marked exhausted: {error_message}")
    
    def try_refresh_current(self) -> Optional[PooledCredential]:
        """"尝试刷新当前凭证（Hermes 1:1学习）"""
        with self._lock:
            return self._try_refresh_current_unlocked()
    
    def _try_refresh_current_unlocked(self) -> Optional[PooledCredential]:
        """刷新当前凭证（内部版本，需要调用者持有锁）"""
        entry = self.current()
        if entry is None:
            return None
        refreshed = self._refresh_entry(entry, force=True)
        if refreshed is not None:
            self._current_id = refreshed.id
        return refreshed
    
    def _refresh_entry(self, entry: PooledCredential, *, force: bool) -> Optional[PooledCredential]:
        """刷新单个凭证

        学习自Hermes credential_pool._refresh_entry设计模式:
        - 三路径：anthropic / openai-codex / nous
        - 失败重试：同步外部文件后重试一次
        - 写回外部文件：保持CLI工具同步
        - Pure function委托：刷新逻辑委托给pure function，不在此处写HTTP逻辑
        """
        if entry.auth_type != AUTH_TYPE_OAUTH or not entry.refresh_token:
            if force:
                self._mark_exhausted(entry, None)
            return None

        try:
            if self.provider == "anthropic":
                from agent.anthropic_adapter import refresh_anthropic_oauth_pure

                refreshed = refresh_anthropic_oauth_pure(
                    entry.refresh_token,
                    use_json=entry.source.endswith("hermes_pkce"),
                )
                updated = replace(
                    entry,
                    access_token=refreshed["access_token"],
                    refresh_token=refreshed["refresh_token"],
                    expires_at_ms=refreshed["expires_at_ms"],
                )
                # 写回 ~/.claude/.credentials.json 保持Claude Code CLI同步
                if entry.source == "claude_code":
                    try:
                        from agent.anthropic_adapter import _write_claude_code_credentials
                        _write_claude_code_credentials(
                            refreshed["access_token"],
                            refreshed["refresh_token"],
                            refreshed["expires_at_ms"],
                        )
                    except Exception as wexc:
                        logger.debug("Failed to write refreshed token to credentials file: %s", wexc)

            elif self.provider == "openai-codex":
                # 先主动同步来自 ~/.codex/auth.json 的tokens
                # Codex CLI（或其他MimirAether profile）可能已消费掉我们的refresh_token
                synced = self._sync_codex_entry_from_cli(entry)
                if synced is not entry:
                    entry = synced
                refreshed = refresh_codex_oauth_pure(
                    entry.access_token,
                    entry.refresh_token,
                )
                updated = replace(
                    entry,
                    access_token=refreshed["access_token"],
                    refresh_token=refreshed["refresh_token"],
                    last_refresh=refreshed.get("last_refresh"),
                )

            elif self.provider == "nous":
                # Nous device_code刷新 — 简化实现
                # Hermes使用 auth_mod.refresh_nous_oauth_from_state() 完成刷新+key minting
                # MimirAether简化版：标记为不支持
                logger.debug("Nous token refresh not yet implemented in MimirAether")
                if force:
                    self._mark_exhausted(entry, None)
                return None

            else:
                logger.debug("Refresh not implemented for provider: %s", self.provider)
                return entry

        except Exception as exc:
            logger.debug("Credential refresh failed for %s/%s: %s", self.provider, entry.id, exc)

            # --- 失败重试逻辑：从外部文件同步后再试一次 ---

            # anthropic claude_code: 检查 ~/.claude/.credentials.json 是否有更新的token
            if self.provider == "anthropic" and entry.source == "claude_code":
                synced = self._sync_anthropic_entry_from_credentials_file(entry)
                if synced.refresh_token != entry.refresh_token:
                    logger.debug("Retrying refresh with synced token from credentials file")
                    try:
                        from agent.anthropic_adapter import refresh_anthropic_oauth_pure
                        refreshed = refresh_anthropic_oauth_pure(
                            synced.refresh_token,
                            use_json=synced.source.endswith("hermes_pkce"),
                        )
                        updated = replace(
                            synced,
                            access_token=refreshed["access_token"],
                            refresh_token=refreshed["refresh_token"],
                            expires_at_ms=refreshed["expires_at_ms"],
                            last_status=STATUS_OK,
                            last_status_at=None,
                            last_error_code=None,
                        )
                        self._replace_entry(synced, updated)
                        self._persist()
                        try:
                            from agent.anthropic_adapter import _write_claude_code_credentials
                            _write_claude_code_credentials(
                                refreshed["access_token"],
                                refreshed["refresh_token"],
                                refreshed["expires_at_ms"],
                            )
                        except Exception as wexc:
                            logger.debug("Failed to write refreshed token to credentials file (retry): %s", wexc)
                        return updated
                    except Exception as retry_exc:
                        logger.debug("Retry refresh also failed: %s", retry_exc)
                elif not self._entry_needs_refresh(synced):
                    # 凭证文件中已有有效token，直接使用
                    logger.debug("Credentials file has valid token, using without refresh")
                    return synced

            # openai-codex: 在主动同步和刷新之间Codex CLI可能已消费refresh_token
            if self.provider == "openai-codex":
                synced = self._sync_codex_entry_from_cli(entry)
                if synced.refresh_token != entry.refresh_token:
                    logger.debug("Retrying Codex refresh with synced token from ~/.codex/auth.json")
                    try:
                        refreshed = refresh_codex_oauth_pure(
                            synced.access_token,
                            synced.refresh_token,
                        )
                        updated = replace(
                            synced,
                            access_token=refreshed["access_token"],
                            refresh_token=refreshed["refresh_token"],
                            last_refresh=refreshed.get("last_refresh"),
                            last_status=STATUS_OK,
                            last_status_at=None,
                            last_error_code=None,
                        )
                        self._replace_entry(synced, updated)
                        self._persist()
                        try:
                            _write_codex_cli_tokens(
                                updated.access_token,
                                updated.refresh_token,
                                last_refresh=updated.last_refresh,
                            )
                        except Exception as wexc:
                            logger.debug("Failed to write refreshed Codex tokens to CLI file (retry): %s", wexc)
                        return updated
                    except Exception as retry_exc:
                        logger.debug("Codex retry refresh also failed: %s", retry_exc)
                elif not self._entry_needs_refresh(synced):
                    logger.debug("Codex CLI has valid token, using without refresh")
                    return synced

            # 重试都失败了，标记耗尽
            self._mark_exhausted(entry, None)
            return None

        # 刷新成功 — 清除错误状态，持久化
        updated = replace(
            updated,
            last_status=STATUS_OK,
            last_status_at=None,
            last_error_code=None,
            last_error_reason=None,
            last_error_message=None,
            last_error_reset_at=None,
        )
        self._replace_entry(entry, updated)
        self._persist()

        # 写回 auth store 防止 _seed_from_singletons 覆盖刷新后的token
        self._sync_device_code_entry_to_auth_store(updated)

        # 写回 ~/.codex/auth.json 保持Codex CLI/VS Code同步
        if self.provider == "openai-codex":
            try:
                _write_codex_cli_tokens(
                    updated.access_token,
                    updated.refresh_token,
                    last_refresh=updated.last_refresh,
                )
            except Exception as wexc:
                logger.debug("Failed to write refreshed Codex tokens to CLI file: %s", wexc)

        return updated

    def _entry_needs_refresh(self, entry: PooledCredential) -> bool:
        """检查凭证是否需要刷新

        学习自Hermes credential_pool._entry_needs_refresh:
        - anthropic: 基于expires_at_ms + 2分钟提前量
        - openai-codex: 基于JWT exp字段 + 2分钟提前量
        - nous: 刷新/铸造需要网络访问，在此不做预判
        """
        if entry.auth_type != AUTH_TYPE_OAUTH:
            return False

        if self.provider == "anthropic":
            if entry.expires_at_ms is None:
                return False
            return int(entry.expires_at_ms) <= int(time.time() * 1000) + 120_000

        if self.provider == "openai-codex":
            return _codex_access_token_is_expiring(
                entry.access_token,
                CODEX_ACCESS_TOKEN_REFRESH_SKEW_SECONDS,
            )

        if self.provider == "nous":
            # Nous刷新/铸造需要网络访问，不在池枚举时触发
            return False

        return False

    def _sync_anthropic_entry_from_credentials_file(self, entry: PooledCredential) -> PooledCredential:
        """从 ~/.claude/.credentials.json 同步 claude_code 池条目

        学习自Hermes credential_pool._sync_anthropic_entry_from_credentials_file:
        OAuth refresh token是单次使用的。当Claude Code CLI（或其他profile的池）
        刷新了token后，会将新对写入 ~/.claude/.credentials.json。池中的refresh_token
        变成过期状态。此方法检测差异并同步。

        仅在 provider=anthropic 且 source=claude_code 时生效。
        """
        if self.provider != "anthropic" or entry.source != "claude_code":
            return entry
        try:
            from agent.anthropic_adapter import read_claude_code_credentials
            creds = read_claude_code_credentials()
            if not creds:
                return entry
            file_refresh = creds.get("refreshToken", "")
            file_access = creds.get("accessToken", "")
            file_expires = creds.get("expiresAt", 0)
            if file_refresh and file_refresh != entry.refresh_token:
                logger.debug("Pool entry %s: syncing tokens from credentials file (refresh token changed)", entry.id)
                updated = replace(
                    entry,
                    access_token=file_access,
                    refresh_token=file_refresh,
                    expires_at_ms=file_expires,
                    last_status=None,
                    last_status_at=None,
                    last_error_code=None,
                )
                self._replace_entry(entry, updated)
                self._persist()
                return updated
        except Exception as exc:
            logger.debug("Failed to sync from credentials file: %s", exc)
        return entry

    def _sync_codex_entry_from_cli(self, entry: PooledCredential) -> PooledCredential:
        """从 ~/.codex/auth.json 同步 openai-codex 池条目

        学习自Hermes credential_pool._sync_codex_entry_from_cli:
        OpenAI OAuth refresh token是单次使用且每次刷新都会轮换。
        当Codex CLI（或其他profile）刷新token后，池中的refresh_token变成过期状态。
        此方法通过比对 ~/.codex/auth.json 检测并同步新token对。
        """
        if self.provider != "openai-codex":
            return entry
        try:
            cli_tokens = _import_codex_cli_tokens()
            if not cli_tokens:
                return entry
            cli_refresh = cli_tokens.get("refresh_token", "")
            cli_access = cli_tokens.get("access_token", "")
            if cli_refresh and cli_refresh != entry.refresh_token:
                logger.debug("Pool entry %s: syncing tokens from ~/.codex/auth.json (refresh token changed)", entry.id)
                updated = replace(
                    entry,
                    access_token=cli_access,
                    refresh_token=cli_refresh,
                    last_status=None,
                    last_status_at=None,
                    last_error_code=None,
                )
                self._replace_entry(entry, updated)
                self._persist()
                return updated
        except Exception as exc:
            logger.debug("Failed to sync from ~/.codex/auth.json: %s", exc)
        return entry

    def _load_config_safe(self) -> Optional[dict]:
        """安全加载配置文件（Hermes 1:1学习）"""
        try:
            # 尝试加载项目根 legacy JSON 配置（若存在）
            from mimir_constants import get_mimir_home

            config_path = get_mimir_home() / "config.json"
            if config_path.exists():
                import json
                with open(config_path) as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _seed_from_env(self) -> None:
        """从环境变量加载凭证（Hermes 1:1学习）"""
        # 支持的环境变量
        env_keys = [
            "DEEPSEEK_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "MOONSHOT_API_KEY",
        ]
        for key in env_keys:
            value = os.environ.get(key)
            if value:
                provider = key.replace("_API_KEY", "").lower()
                entry = PooledCredential(
                    provider=provider,
                    id=f"env_{key.lower()}",
                    label=f"{provider} from env",
                    auth_type="api_key",
                    priority=50,
                    source="env",
                    access_token=value,
                )
                self._entries.append(entry)
                logger.info(f"Loaded {provider} credential from environment")
    
    def mark_exhausted_and_rotate(self, status_code: int = None, error_context: dict = None) -> Optional[PooledCredential]:
        """标记当前凭证耗尽并轮换到下一个（Hermes 1:1学习）"""
        with self._lock:
            entry = self.current()
            if entry:
                self._mark_exhausted(entry, status_code, error_context)
            # 选择下一个可用凭证
            return self._select_unlocked()
    
    def _mark_exhausted(self, entry: PooledCredential, status_code: int = None, error_context: dict = None) -> None:
        """内部方法：标记凭证为耗尽（Hermes 1:1学习）"""
        from dataclasses import replace
        updated = replace(
            entry,
            last_status=STATUS_EXHAUSTED,
            last_status_at=time.time(),
            last_error_code=status_code,
            last_error_message=error_context.get("message") if error_context else None,
        )
        # 替换entries中的凭证
        for i, e in enumerate(self._entries):
            if e.id == entry.id:
                self._entries[i] = updated
                break
        if self._current_id == entry.id:
            self._current_id = None
    
    def _upsert_entry(self, source: str, payload: dict) -> bool:
        """插入或更新凭证（Hermes 1:1学习）"""
        # 查找是否存在
        for i, entry in enumerate(self._entries):
            if entry.source == source:
                # 更新
                from dataclasses import replace
                self._entries[i] = replace(self._entries[i], **payload)
                return True
        # 插入新凭证
        entry = PooledCredential(
            provider=self.provider,
            id=payload.get("id", uuid.uuid4().hex[:6]),
            label=payload.get("label", source),
            auth_type=payload.get("auth_type", "api_key"),
            priority=payload.get("priority", 50),
            source=source,
            access_token=payload.get("access_token", ""),
        )
        self._entries.append(entry)
        return True
    
    def mark_ok(self, entry: Optional[PooledCredential] = None) -> None:
        """标记凭证为正常状态"""
        with self._lock:
            target = entry or self.current()
            if target is None:
                return
            
            updated = replace(
                target,
                last_status=STATUS_OK,
                last_status_at=None,
                last_error_code=None,
                last_error_reason=None,
                last_error_message=None,
                last_error_reset_at=None,
            )
            self._replace_entry(target, updated)
            self._persist()
    
    def increment_request_count(self, entry: Optional[PooledCredential] = None) -> None:
        """增加请求计数"""
        with self._lock:
            target = entry or self.current()
            if target is None:
                return
            updated = replace(target, request_count=target.request_count + 1)
            self._replace_entry(target, updated)
            # 不立即持久化，避免频繁写入
    
    def acquire_lease(self, credential_id: Optional[str] = None) -> Optional[str]:
        """
        获取凭证租约
        
        Args:
            credential_id: 指定凭证ID，或None自动选择
            
        Returns:
            租约ID或None
        """
        with self._lock:
            if credential_id:
                # 指定的凭证
                for entry in self._entries:
                    if entry.id == credential_id:
                        self._active_leases[credential_id] = self._active_leases.get(credential_id, 0) + 1
                        self._current_id = credential_id
                        return credential_id
                return None
            
            # 自动选择最少使用的
            available = self._available_entries(clear_expired=True)
            if not available:
                return None
            
            # 找未达上限的
            below_cap = [
                e for e in available
                if self._active_leases.get(e.id, 0) < self._max_concurrent
            ]
            candidates = below_cap if below_cap else available
            
            # 选择请求数最少的
            chosen = min(candidates, key=lambda e: (self._active_leases.get(e.id, 0), e.priority))
            self._active_leases[chosen.id] = self._active_leases.get(chosen.id, 0) + 1
            self._current_id = chosen.id
            return chosen.id
    
    def release_lease(self, credential_id: str) -> None:
        """释放租约"""
        with self._lock:
            count = self._active_leases.get(credential_id, 0)
            if count <= 1:
                self._active_leases.pop(credential_id, None)
            else:
                self._active_leases[credential_id] = count - 1
    
    def add_entry(self, entry: PooledCredential) -> PooledCredential:
        """添加凭证到池"""
        with self._lock:
            # 生成新优先级
            new_priority = _next_priority(self._entries)
            new_entry = replace(entry, priority=new_priority)
            self._entries.append(new_entry)
            self._entries.sort(key=lambda e: e.priority)
            self._persist()
            return new_entry
    
    def remove_entry(self, entry_id: str) -> bool:
        """从池中移除凭证"""
        with self._lock:
            for idx, entry in enumerate(self._entries):
                if entry.id == entry_id:
                    self._entries.pop(idx)
                    if self._current_id == entry_id:
                        self._current_id = None
                    self._persist()
                    return True
            return False
    
    def reset_all_statuses(self) -> int:
        """重置所有凭证状态"""
        with self._lock:
            count = 0
            new_entries = []
            for entry in self._entries:
                if entry.last_status or entry.last_error_code:
                    new_entries.append(replace(
                        entry,
                        last_status=STATUS_OK,
                        last_status_at=None,
                        last_error_code=None,
                        last_error_reason=None,
                        last_error_message=None,
                        last_error_reset_at=None,
                    ))
                    count += 1
                else:
                    new_entries.append(entry)
            if count:
                self._entries = new_entries
                self._persist()
            return count
    
    def set_strategy(self, strategy: str) -> bool:
        """设置选择策略"""
        if strategy not in SUPPORTED_STRATEGIES:
            return False
        with self._lock:
            self._strategy = strategy
        return True


# ============================================================================
# CredentialPool Hermès卓容方法（在类定义之后）
# ============================================================================

def _credential_pool_reset_statuses(self) -> int:
    """重置所有凭证状态为ok（Hermès卓容签名）
    """
    with self._lock:
        count = 0
        new_entries = []
        for entry in self._entries:
            if entry.last_status or entry.last_status_at or entry.last_error_code:
                new_entries.append(replace(
                    entry,
                    last_status=None,
                    last_status_at=None,
                    last_error_code=None,
                    last_error_reason=None,
                    last_error_message=None,
                    last_error_reset_at=None,
                ))
                count += 1
            else:
                new_entries.append(entry)
        if count:
            self._entries = new_entries
            self._persist()
        return count


def _credential_pool_remove_index(self, index: int) -> Optional[PooledCredential]:
    """按索引移除凭证（Hermès卓容签名，1-based索引）
    """
    with self._lock:
        if index < 1 or index > len(self._entries):
            return None
        removed = self._entries.pop(index - 1)
        self._entries = [
            replace(entry, priority=new_priority)
            for new_priority, entry in enumerate(self._entries)
        ]
        self._persist()
        if self._current_id == removed.id:
            self._current_id = None

        # SA-03: also clean up the external source (.env, config, etc.)
        if _find_removal_step:
            step = _find_removal_step(removed.provider, removed.source or "")
            if step:
                result = step.remove_fn(removed.provider, removed)
                if result.cleaned or result.hints:
                    logger.info("[SA-03] %s removal: cleaned=%s hints=%s",
                                removed.provider, result.cleaned, result.hints)

        return removed


def _credential_pool_resolve_target(self, target: Any) -> Tuple[Optional[int], Optional[PooledCredential], Optional[str]]:
    """解析凭证目标（Hermès卓容签名）
    """
    raw = str(target or "").strip()
    if not raw:
        return None, None, "No credential target provided."

    with self._lock:
        # 按ID匹配
        for idx, entry in enumerate(self._entries, start=1):
            if entry.id == raw:
                return idx, entry, None

        # 按label匹配
        label_matches = [
            (idx, entry)
            for idx, entry in enumerate(self._entries, start=1)
            if entry.label.strip().lower() == raw.lower()
        ]
        if len(label_matches) == 1:
            return label_matches[0][0], label_matches[0][1], None
        if len(label_matches) > 1:
            return None, None, f'Ambiguous credential label "{raw}". Use the numeric index or entry id instead.'

        # 按数字索引匹配
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(self._entries):
                return index, self._entries[index - 1], None
            return None, None, f"No credential #{index}."

        return None, None, f'No credential matching "{raw}".'


# 注入Hermès卓容方法到CredentialPool
CredentialPool.reset_statuses = _credential_pool_reset_statuses
CredentialPool.remove_index = _credential_pool_remove_index
CredentialPool.resolve_target = _credential_pool_resolve_target


# ============================================================================



# ============================================================================
# Auth Store 基础设施 (Hermes 1:1)
# ============================================================================

import fcntl
import stat as _stat_mod

def _mimir_auth_file() -> Path:
    from mimir_constants import get_mimir_home

    return get_mimir_home() / "auth.json"


_AUTH_LOCK_TIMEOUT = 10.0

_auth_lock_holder = threading.local()


class _AuthStoreLock:
    """跨进程文件锁，保护auth.json的读写
    Hermes design pattern: reentrant file lock with timeout.
    """
    def __init__(self, timeout_seconds: float = _AUTH_LOCK_TIMEOUT):
        self._timeout = timeout_seconds
        self._lock_path = _mimir_auth_file().with_suffix(".lock")

    def __enter__(self):
        if getattr(_auth_lock_holder, "depth", 0) > 0:
            _auth_lock_holder.depth += 1
            return self
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._lock_path.open("a+")
        deadline = time.time() + max(1.0, self._timeout)
        while True:
            try:
                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError, PermissionError):
                if time.time() >= deadline:
                    raise TimeoutError("Timed out waiting for auth store lock")
                time.sleep(0.05)
        _auth_lock_holder.depth = 1
        return self

    def __exit__(self, *args):
        _auth_lock_holder.depth = 0
        fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        self._file.close()


def _mimir_auth_store_lock():
    return _AuthStoreLock()


def _mimir_load_auth_store() -> Dict[str, Any]:
    auth_path = _mimir_auth_file()
    if not auth_path.exists():
        return {"version": 1, "providers": {}}
    try:
        data = json.loads(auth_path.read_text())
        if isinstance(data, dict):
            data.setdefault("providers", {})
            return data
    except Exception:
        pass
    return {"version": 1, "providers": {}}


def _mimir_save_auth_store(auth_store: Dict[str, Any]) -> None:
    auth_store["version"] = 1
    auth_store["updated_at"] = datetime.now().isoformat()
    payload = json.dumps(auth_store, indent=2) + "\n"
    auth_path = _mimir_auth_file()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = auth_path.with_name(f"auth.json.tmp.{uuid.uuid4().hex}")
    try:
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(str(tmp_path), str(auth_path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    try:
        auth_path.chmod(_stat_mod.S_IRUSR | _stat_mod.S_IWUSR)
    except OSError:
        pass


def _mimir_load_provider_state(provider_id: str) -> Optional[Dict[str, Any]]:
    auth_store = _mimir_load_auth_store()
    providers = auth_store.get("providers")
    if not isinstance(providers, dict):
        return None
    state = providers.get(provider_id)
    return dict(state) if isinstance(state, dict) else None


def _mimir_save_provider_state(provider_id: str, state: Dict[str, Any]) -> None:
    with _mimir_auth_store_lock():
        auth_store = _mimir_load_auth_store()
        providers = auth_store.setdefault("providers", {})
        providers[provider_id] = state
        auth_store["active_provider"] = provider_id
        _mimir_save_auth_store(auth_store)


# ============================================================================
# Codex OAuth 工具函数 (Hermes 1:1)
# ============================================================================

CODEX_OAUTH_CLIENT_ID = "openai-codex-cli"
CODEX_OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_ACCESS_TOKEN_REFRESH_SKEW_SECONDS = 120


def _import_codex_cli_tokens() -> Optional[Dict[str, str]]:
    codex_home = os.getenv("CODEX_HOME", "").strip()
    if not codex_home:
        codex_home = str(Path.home() / ".codex")
    auth_path = Path(codex_home).expanduser() / "auth.json"
    if not auth_path.is_file():
        return None
    try:
        payload = json.loads(auth_path.read_text())
        tokens = payload.get("tokens")
        if not isinstance(tokens, dict):
            return None
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        if not access_token or not refresh_token:
            return None
        if _codex_access_token_is_expiring(access_token, skew_ms=0):
            return None
        return dict(tokens)
    except Exception:
        return None


def _codex_access_token_is_expiring(access_token: str, skew_ms: int = 0) -> bool:
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return False
        payload = parts[1]
        payload = payload.replace("-", "+").replace("_", "/")
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        import base64
        claims = json.loads(base64.b64decode(payload))
        exp = claims.get("exp")
        if isinstance(exp, (int, float)):
            now_ms = int(time.time() * 1000)
            return now_ms >= (int(exp) * 1000 - skew_ms)
    except Exception:
        pass
    return False


def _decode_jwt_claims(token: str) -> Dict[str, Any]:
    import base64
    if not token:
        return {}
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    try:
        payload = parts[1]
        payload = payload.replace("-", "+").replace("_", "/")
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        return json.loads(base64.b64decode(payload))
    except Exception:
        return {}


def _write_codex_cli_tokens(
    access_token: str,
    refresh_token: str,
    *,
    last_refresh: Optional[str] = None,
) -> None:
    codex_home = os.getenv("CODEX_HOME", "").strip()
    if not codex_home:
        codex_home = str(Path.home() / ".codex")
    auth_path = Path(codex_home).expanduser() / "auth.json"
    try:
        existing: Dict[str, Any] = {}
        if auth_path.is_file():
            existing = json.loads(auth_path.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            existing = {}
        tokens_dict = existing.get("tokens")
        if not isinstance(tokens_dict, dict):
            tokens_dict = {}
        tokens_dict["access_token"] = access_token
        tokens_dict["refresh_token"] = refresh_token
        existing["tokens"] = tokens_dict
        if last_refresh is not None:
            existing["last_refresh"] = last_refresh
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        auth_path.chmod(0o600)
    except (OSError, IOError) as exc:
        logger.debug("Failed to write Codex tokens to %s: %s", auth_path, exc)


def refresh_codex_oauth_pure(
    access_token: str,
    refresh_token: str,
    *,
    timeout_seconds: float = 20.0,
) -> Dict[str, Any]:
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        raise ValueError("Codex refresh_token is required")
    try:
        import httpx
    except ImportError:
        raise ImportError("httpx required for Codex OAuth: pip install httpx")

    timeout = httpx.Timeout(max(5.0, float(timeout_seconds)))
    with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}) as client:
        response = client.post(
            CODEX_OAUTH_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": CODEX_OAUTH_CLIENT_ID,
            },
        )

    if response.status_code != 200:
        code = "codex_refresh_failed"
        message = f"Codex token refresh failed with status {response.status_code}."
        try:
            err = response.json()
            if isinstance(err, dict):
                err_code = err.get("error", "")
                if err_code:
                    code = err_code
                err_desc = err.get("error_description") or err.get("message", "")
                if err_desc:
                    message = f"Codex token refresh failed: {err_desc}"
        except Exception:
            pass
        raise RuntimeError(f"[{code}] {message}")

    try:
        refresh_payload = response.json()
    except Exception as exc:
        raise RuntimeError("Codex token refresh returned invalid JSON.") from exc

    refreshed_access = refresh_payload.get("access_token")
    if not isinstance(refreshed_access, str) or not refreshed_access.strip():
        raise RuntimeError("Codex token refresh response missing access_token.")

    updated = {
        "access_token": refreshed_access.strip(),
        "refresh_token": refresh_token.strip(),
        "last_refresh": datetime.now().isoformat().replace("+00:00", "Z"),
    }
    next_refresh = refresh_payload.get("refresh_token")
    if isinstance(next_refresh, str) and next_refresh.strip():
        updated["refresh_token"] = next_refresh.strip()
    return updated



# ============================================================================
# OAuth Token 同步方法 (Hermes 1:1)
# ============================================================================


def _sync_device_code_entry_to_auth_store(entry: PooledCredential) -> None:
    """Write refreshed pool entry tokens back to auth.json providers.

    After a pool-level refresh, auth.json's providers.<id> still holds
    pre-refresh state. On the next load_pool(), _seed_from_singletons()
    reads that stale state and can overwrite fresh pool entries -
    potentially re-seeding consumed single-use refresh tokens.
    """
    if entry.source != "device_code":
        return
    try:
        with _mimir_auth_store_lock():
            auth_store = _mimir_load_auth_store()

            if entry.provider == "nous":
                state = _mimir_load_provider_state("nous")
                if state is None:
                    return
                state["access_token"] = entry.access_token
                if entry.refresh_token:
                    state["refresh_token"] = entry.refresh_token
                if entry.expires_at:
                    state["expires_at"] = entry.expires_at
                agent_key = getattr(entry, "agent_key", None)
                if agent_key:
                    state["agent_key"] = agent_key
                agent_key_expires_at = getattr(entry, "agent_key_expires_at", None)
                if agent_key_expires_at:
                    state["agent_key_expires_at"] = agent_key_expires_at
                for extra_key in ("obtained_at", "expires_in", "agent_key_id",
                                  "agent_key_expires_in", "agent_key_reused",
                                  "agent_key_obtained_at"):
                    val = entry.extra.get(extra_key)
                    if val is not None:
                        state[extra_key] = val
                inf_url = getattr(entry, "inference_base_url", None)
                if inf_url:
                    state["inference_base_url"] = inf_url
                _mimir_save_provider_state("nous", state)

            elif entry.provider == "openai-codex":
                state = _mimir_load_provider_state("openai-codex")
                if not isinstance(state, dict):
                    return
                tokens = state.get("tokens")
                if not isinstance(tokens, dict):
                    return
                tokens["access_token"] = entry.access_token
                if entry.refresh_token:
                    tokens["refresh_token"] = entry.refresh_token
                if hasattr(entry, "last_refresh") and entry.last_refresh:
                    state["last_refresh"] = entry.last_refresh
                _mimir_save_provider_state("openai-codex", state)
            else:
                return

            _mimir_save_auth_store(auth_store)
    except Exception as exc:
        logger.debug("Failed to sync %s pool entry to auth store: %s", entry.provider, exc)


# ============================================================================
# Nous OAuth 刷新 (Hermes 1:1)
# ============================================================================

DEFAULT_NOUS_PORTAL_URL = "https://portal.nousresearch.com"
DEFAULT_NOUS_INFERENCE_URL = "https://api.nousresearch.com/v1"
DEFAULT_NOUS_SCOPE = "openid profile inference"


def refresh_nous_oauth_from_state(
    state: Dict[str, Any],
    *,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Refresh Nous OAuth from state dict - simplified MimirAether version.

    Design pattern learned from Hermes:
    1. Use refresh_token to get new access_token
    2. If agent_key is missing/expired, mint a new one
    3. Return updated state dict with all fields

    Returns:
        Dict with refreshed fields (access_token, refresh_token, agent_key, etc.)
    """
    try:
        import httpx
    except ImportError:
        raise ImportError("httpx required for Nous OAuth: pip install httpx")

    portal_base_url = str(state.get("portal_base_url") or DEFAULT_NOUS_PORTAL_URL).rstrip("/")
    client_id = str(state.get("client_id") or "mimir-aether")
    access_token = state.get("access_token", "")
    refresh_token = state.get("refresh_token", "")

    if not access_token or not refresh_token:
        raise ValueError("Nous OAuth state missing access_token or refresh_token")

    timeout = httpx.Timeout(15.0)

    with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}) as client:
        # Step 1: refresh access token
        now = datetime.now()
        response = client.post(
            f"{portal_base_url}/api/auth/token",
            json={
                "client_id": client_id,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Nous token refresh failed ({response.status_code}): "
                f"{response.text[:200]}"
            )

        payload = response.json()
        state["access_token"] = payload["access_token"]
        if "refresh_token" in payload:
            state["refresh_token"] = payload["refresh_token"]
        state["token_type"] = payload.get("token_type", state.get("token_type", "Bearer"))
        state["scope"] = payload.get("scope", state.get("scope"))
        access_ttl = int(payload.get("expires_in", 3600))
        state["expires_in"] = access_ttl
        state["expires_at"] = (now.replace(tzinfo=None).timestamp() + access_ttl)
        state["expires_at_iso"] = datetime.fromtimestamp(
            now.timestamp() + access_ttl
        ).isoformat()
        state["obtained_at"] = now.isoformat()

        # Step 2: mint agent key if needed
        agent_key = state.get("agent_key")
        agent_key_expires_at = state.get("agent_key_expires_at")

        needs_mint = force_refresh
        if agent_key and agent_key_expires_at:
            try:
                if isinstance(agent_key_expires_at, str):
                    exp_dt = datetime.fromisoformat(
                        agent_key_expires_at.replace("Z", "+00:00")
                    )
                    if datetime.now() >= exp_dt:
                        needs_mint = True
                elif isinstance(agent_key_expires_at, (int, float)):
                    if time.time() >= float(agent_key_expires_at) - 60:
                        needs_mint = True
            except Exception:
                needs_mint = True
        else:
            needs_mint = True

        if needs_mint:
            mint_resp = client.post(
                f"{portal_base_url}/api/auth/key",
                headers={"Authorization": f"Bearer {state['access_token']}"},
                json={"ttl": 300},
            )
            if mint_resp.status_code == 200:
                mint_payload = mint_resp.json()
                now_ts = now.timestamp()
                state["agent_key"] = mint_payload["key"]
                state["agent_key_expires_at"] = (
                    now_ts + int(mint_payload.get("expires_in", 300))
                )
                state["agent_key_id"] = mint_payload.get("key_id", "")
                state["agent_key_expires_in"] = mint_payload.get("expires_in")
                state["agent_key_obtained_at"] = now.isoformat()
                minted_url = mint_payload.get("inference_base_url", "").rstrip("/")
                if minted_url:
                    state["inference_base_url"] = minted_url
            else:
                logger.debug(
                    "Nous agent key mint failed (%s), reusing cached key",
                    mint_resp.status_code,
                )

    return state


# 池注册表
# ============================================================================

class CredentialPoolRegistry:
    """
    凭证池注册表
    
    管理所有provider的凭证池
    """
    
    _instance: Optional["CredentialPoolRegistry"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._pools: Dict[str, CredentialPool] = {}
                    cls._instance._pools_lock = threading.Lock()
        return cls._instance
    
    def get_pool(self, provider: str) -> Optional[CredentialPool]:
        """获取provider的凭证池"""
        with self._pools_lock:
            return self._pools.get(provider)
    
    def create_pool(
        self,
        provider: str,
        entries: Optional[List[PooledCredential]] = None,
        strategy: str = STRATEGY_FILL_FIRST,
    ) -> CredentialPool:
        """创建或获取凭证池"""
        with self._pools_lock:
            if provider in self._pools:
                return self._pools[provider]
            pool = CredentialPool(provider, entries, strategy)
            self._pools[provider] = pool
            return pool
    
    def remove_pool(self, provider: str) -> bool:
        """移除凭证池"""
        with self._pools_lock:
            if provider in self._pools:
                del self._pools[provider]
                return True
            return False
    
    def list_providers(self) -> List[str]:
        """列出所有provider"""
        with self._pools_lock:
            return list(self._pools.keys())


# ============================================================================
# 便捷函数
# ============================================================================

def get_default_registry() -> CredentialPoolRegistry:
    """获取默认注册表实例"""
    return CredentialPoolRegistry()


def create_credential(
    provider: str,
    api_key: str,
    label: Optional[str] = None,
    base_url: Optional[str] = None,
) -> PooledCredential:
    """创建新凭证"""
    return PooledCredential(
        provider=provider,
        id=uuid.uuid4().hex[:6],
        label=label or f"{provider} credential",
        auth_type=AUTH_TYPE_API_KEY,
        source=SOURCE_MANUAL,
        access_token=api_key,
        base_url=base_url,
    )


def load_pool_from_config(provider: str) -> Optional[CredentialPool]:
    """从环境变量加载凭证池"""
    api_key = os.environ.get(f"{provider.upper()}_API_KEY", "").strip()
    if not api_key:
        # 尝试通用key
        api_key = os.environ.get("API_KEY", "").strip()
    if not api_key:
        return None
    
    entry = create_credential(provider, api_key)
    pool = CredentialPool(provider, [entry])
    return pool


# ============================================================================
# 便捷函数
# ============================================================================

def load_pool(provider: str) -> Optional[CredentialPool]:
    """
    加载指定provider的凭证池。
    
    简化版：直接从环境变量加载单个凭证。
    """
    return load_pool_from_config(provider)


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    print("=" * 60)
    print("MimirAether Credential Pool 测试")
    print("=" * 60)
    
    # 测试1: 创建凭证
    print("\n[测试1] 创建凭证")
    cred1 = create_credential("openai", "sk-key-1", "OpenAI Primary")
    cred2 = create_credential("openai", "sk-key-2", "OpenAI Backup")
    cred3 = create_credential("anthropic", "sk-ant-key-1", "Anthropic Primary")
    print(f"  凭证1: {cred1.id} - {cred1.label}")
    print(f"  凭证2: {cred2.id} - {cred2.label}")
    print(f"  凭证3: {cred3.id} - {cred3.label}")
    
    # 测试2: 创建池
    print("\n[测试2] 创建凭证池")
    pool = CredentialPool("openai", [cred1, cred2], strategy=STRATEGY_FILL_FIRST)
    print(f"  Provider: {pool.provider}")
    print(f"  凭证数: {len(pool.entries)}")
    print(f"  策略: {pool.strategy}")
    
    # 测试3: 选择凭证
    print("\n[测试3] 选择凭证")
    selected = pool.select()
    print(f"  选中: {selected.label if selected else 'None'}")
    
    # 测试4: 标记耗尽
    print("\n[测试4] 标记耗尽")
    pool.mark_exhausted(selected, status_code=429, error_message="Rate limited")
    print(f"  has_available: {pool.has_available()}")
    
    # 测试5: 自动轮换
    print("\n[测试5] 自动轮换")
    selected2 = pool.select()
    print(f"  新选中: {selected2.label if selected2 else 'None'}")
    
    # 测试6: 租约管理
    print("\n[测试6] 租约管理")
    lease_id = pool.acquire_lease()
    print(f"  获取租约: {lease_id}")
    pool.release_lease(lease_id)
    print(f"  释放租约: OK")
    
    # 测试7: 多种策略
    print("\n[测试7] 策略测试")
    strategies = [STRATEGY_FILL_FIRST, STRATEGY_ROUND_ROBIN, STRATEGY_LEAST_USED, STRATEGY_RANDOM]
    for strategy in strategies:
        test_pool = CredentialPool("test", [
            create_credential("test", f"key-{i}", f"Key-{i}") for i in range(3)
        ], strategy=strategy)
        selected = test_pool.select()
        print(f"  {strategy}: 选中 {selected.label if selected else 'None'}")
    
    # 测试8: 凭证池注册表
    print("\n[测试8] 凭证池注册表")
    registry = get_default_registry()
    registry.create_pool("openai", [cred1])
    registry.create_pool("anthropic", [cred3])
    providers = registry.list_providers()
    print(f"  Providers: {providers}")
    
    # 测试9: 凭证状态
    print("\n[测试9] 凭证状态管理")
    test_cred = create_credential("test", "key", "Test")
    print(f"  初始状态: {test_cred.last_status}")
    
    # 模拟请求计数
    for i in range(5):
        test_pool = CredentialPool("test", [test_cred])
        test_pool.select()
        test_pool.increment_request_count()
        test_cred = test_pool.current()
        print(f"  请求后计数: {test_cred.request_count if test_cred else 'N/A'}")
    
    # 测试10: 序列化
    print("\n[测试10] 序列化")
    cred = create_credential("test", "secret-key", "Test Cred", base_url="https://api.test.com")
    serialized = cred.to_dict()
    print(f"  Serialized keys: {list(serialized.keys())}")
    restored = PooledCredential.from_dict("test", serialized)
    print(f"  Restored: {restored.label} - {restored.runtime_api_key}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)