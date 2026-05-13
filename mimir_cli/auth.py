"""
MimirAether Auth Module - 自研实现

This module provides authentication and credential management for MimirAether.
Many functions are stubs that delegate to MimirAether's own systems.

自研状态: 部分实现核心功能，其他功能为最小化存根以保证兼容性
"""

import os
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

logger = logging.getLogger(__name__)

# ─── Exceptions ───────────────────────────────────────────────────────────────

class AuthError(Exception):
    """Raised when authentication fails."""
    pass


# ─── Constants ───────────────────────────────────────────────────────────────

DEFAULT_CODEX_BASE_URL = "https://api.openai.com/v1"
DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Provider registry
PROVIDER_REGISTRY: Dict[str, Dict[str, Any]] = {
    "deepseek": {
        "auth_type": "api_key",
        "base_url_env_var": "DEEPSEEK_API_KEY",
        "inference_base_url": "https://api.deepseek.com",
    },
}

# ─── Credential checks ────────────────────────────────────────────────────────

def _agent_key_is_usable(key: str) -> bool:
    """Check if an API key looks usable (non-empty, reasonable length)."""
    if not key or not isinstance(key, str):
        return False
    key = key.strip()
    if len(key) < 10:
        return False
    return True

def has_usable_secret(key: str) -> bool:
    """Check if a secret/key is usable."""
    return _agent_key_is_usable(key)

def format_auth_error(provider: str, message: str) -> str:
    """Format an authentication error message."""
    return f"[{provider}] Auth error: {message}"

# ─── Provider resolution ───────────────────────────────────────────────

def resolve_provider(
    provider: str,
    explicit_api_key: Optional[str] = None,
    explicit_base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve provider configuration.

    Args:
        provider: Provider name (e.g., 'deepseek', 'openrouter')
        explicit_api_key: Optional explicit API key for the provider
        explicit_base_url: Optional explicit base URL for the provider

    Returns:
        Dict with provider configuration including api_key and base_url if provided
    """
    result = PROVIDER_REGISTRY.get(provider, {}).copy()

    # If explicit credentials provided, use them
    if explicit_api_key:
        result["api_key"] = explicit_api_key
    if explicit_base_url:
        result["base_url"] = explicit_base_url

    # Auto-detect from environment for common providers
    if not result.get("api_key"):
        env_key = os.getenv(f"{provider.upper()}_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        if env_key and has_usable_secret(env_key):
            result["api_key"] = env_key

    # Set default base_url for known providers
    if not result.get("base_url"):
        if provider == "deepseek":
            result["base_url"] = "https://api.deepseek.com"

    return result

# ─── Runtime credentials (stub - delegates to env/credential pool) ────────────

def resolve_nous_runtime_credentials(min_key_ttl_seconds: int = 60) -> Optional[Dict[str, Any]]:
    """Get Nous runtime credentials, refreshing if needed."""
    # Delegate to env/credential pool
    key = os.getenv("NOUS_API_KEY") or os.getenv("API_KEY")
    if key and has_usable_secret(key):
        return {"access_token": key, "api_key": key}
    return None

def resolve_codex_runtime_credentials() -> Optional[Dict[str, Any]]:
    """Get Codex runtime credentials."""
    key = os.getenv("OPENAI_API_KEY")
    if key and has_usable_secret(key):
        return {"api_key": key, "base_url": DEFAULT_CODEX_BASE_URL}
    return None

def resolve_qwen_runtime_credentials() -> Optional[Dict[str, Any]]:
    """Get Qwen runtime credentials."""
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
    if key and has_usable_secret(key):
        return {"api_key": key, "base_url": DEFAULT_QWEN_BASE_URL}
    return None

def resolve_api_key_provider_credentials(provider: str) -> Optional[Dict[str, Any]]:
    """Get API key credentials for a custom provider."""
    key = os.getenv("CUSTOM_PROVIDER_API_KEY")
    if key and has_usable_secret(key):
        return {"api_key": key}
    return None

def resolve_external_process_provider_credentials(provider: str) -> Optional[Dict[str, Any]]:
    """Get credentials from an external process."""
    return None

# ─── Auth state ──────────────────────────────────────────────────────────────

def get_provider_auth_state(provider: str) -> Optional[Dict[str, Any]]:
    """Get the current auth state for a provider."""
    # Check environment first
    key = os.getenv(f"{provider.upper()}_API_KEY") or os.getenv("API_KEY")
    if key and has_usable_secret(key):
        return {"access_token": key, "api_key": key}
    return None

def get_auth_status(provider: str) -> Dict[str, Any]:
    """Get authentication status for a provider."""
    state = get_provider_auth_state(provider)
    return {
        "authenticated": state is not None,
        "provider": provider,
    }

# ─── Provider-specific auth ──────────────────────────────────────────────────

def get_active_provider() -> Optional[str]:
    """Get the currently active provider."""
    # Check common provider env vars
    for provider in ["openai", "anthropic", "nous", "qwen", "gemini"]:
        if os.getenv(f"{provider.upper()}_API_KEY"):
            return provider
    return os.getenv("ACTIVE_PROVIDER")

def get_nous_auth_status() -> Dict[str, Any]:
    """Get Nous authentication status."""
    key = os.getenv("NOUS_API_KEY")
    return {"authenticated": bool(key and has_usable_secret(key))}

def get_codex_auth_status() -> Dict[str, Any]:
    """Get Codex authentication status."""
    key = os.getenv("OPENAI_API_KEY")
    return {"authenticated": bool(key and has_usable_secret(key))}

def get_qwen_auth_status() -> Dict[str, Any]:
    """Get Qwen authentication status."""
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
    return {"authenticated": bool(key and has_usable_secret(key))}

def get_anthropic_key() -> Optional[str]:
    """Get Anthropic API key."""
    key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("API_KEY")
    if key and has_usable_secret(key):
        return key
    return None

def resolve_nous_access_token() -> Optional[str]:
    """Get Nous access token."""
    creds = resolve_nous_runtime_credentials()
    if creds:
        return creds.get("access_token")
    return None

# ─── Auth store (stub) ───────────────────────────────────────────────────────

def _load_auth_store() -> Dict[str, Any]:
    """Load the auth store from disk."""
    # MimirAether uses agent/credential_pool instead
    return {}

# ─── OAuth helpers (stubs) ──────────────────────────────────────────────────

def _request_device_code(provider: str) -> Dict[str, Any]:
    """Request OAuth device code."""
    raise NotImplementedError("OAuth device flow not implemented in MimirAether")

def _poll_for_token(device_code: str, provider: str) -> Dict[str, Any]:
    """Poll for OAuth token."""
    raise NotImplementedError("OAuth device flow not implemented in MimirAether")

def refresh_nous_oauth_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Refresh OAuth token from state."""
    raise NotImplementedError("OAuth not implemented in MimirAether")

# ─── Auth management ─────────────────────────────────────────────────────────

def clear_provider_auth(provider: str) -> None:
    """Clear stored auth for a provider."""
    # MimirAether credential pool handles this
    pass

def suppress_credential_source(provider: str, source: str) -> None:
    """Suppress a credential source for a provider."""
    pass

# ─── Nous models (stub) ─────────────────────────────────────────────────────

def fetch_nous_models(access_token: str, portal_url: str = "") -> list:
    """Fetch available models from Nous."""
    return []
