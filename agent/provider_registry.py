"""MimirAether native provider registry — replaces hermes_cli.auth.PROVIDER_REGISTRY.

Only contains providers that MimirAether actually uses.  Extensible via
the ``providers:`` dict in config.yaml (custom providers) and standard
environment variables (API-key providers).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Data model ──────────────────────────────────────────────────────────────

@dataclass
class ProviderConfig:
    """Describes a known inference provider."""

    id: str
    name: str
    auth_type: str  # "api_key" | "external_process" | "oauth_device_code"
    inference_base_url: str = ""
    portal_base_url: str = ""
    client_id: str = ""
    scope: str = ""
    api_key_env_vars: tuple[str, ...] = ()
    base_url_env_var: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


_PLACEHOLDER_SECRET_VALUES: frozenset[str] = frozenset(
    {"***", "sk-***", "sk-placeholder", "placeholder", "changeme", "none", "null", "undefined"}
)


def _has_usable_secret(value: Any, *, min_length: int = 4) -> bool:
    """Return True when the value looks like a real API key."""
    if not isinstance(value, str):
        return False
    cleaned = value.strip()
    if len(cleaned) < min_length:
        return False
    if cleaned.lower() in _PLACEHOLDER_SECRET_VALUES:
        return False
    return True


# ── Registry ────────────────────────────────────────────────────────────────

PROVIDER_REGISTRY: dict[str, ProviderConfig] = {
    "deepseek": ProviderConfig(
        id="deepseek",
        name="DeepSeek",
        auth_type="api_key",
        inference_base_url="https://api.deepseek.com/v1",
        api_key_env_vars=("DEEPSEEK_API_KEY",),
        base_url_env_var="DEEPSEEK_BASE_URL",
    ),
    # Add more providers below as needed.
    # Example:
    # "openai": ProviderConfig(
    #     id="openai",
    #     name="OpenAI",
    #     auth_type="api_key",
    #     inference_base_url="https://api.openai.com/v1",
    #     api_key_env_vars=("OPENAI_API_KEY",),
    # ),
}

# ── Credential resolution (API-key providers) ──────────────────────────────

def _resolve_api_key_provider_secret(
    provider_id: str, pconfig: ProviderConfig
) -> tuple[str, str]:
    """Resolve an API-key provider's token and return (key, source)."""
    # 1. Check environment variables (os.environ only — MimirAether doesn't use .env files)
    for env_var in pconfig.api_key_env_vars:
        val = (os.getenv(env_var, "") or "").strip()
        if _has_usable_secret(val):
            return val, env_var

    # 2. Fallback: try credential pool
    try:
        from agent.credential_pool import load_pool

        pool = load_pool(provider_id)
        if pool and pool.has_credentials():
            entry = pool.peek()
            if entry:
                key = getattr(entry, "access_token", "") or getattr(entry, "runtime_api_key", "")
                key = str(key).strip()
                if _has_usable_secret(key):
                    return key, f"credential_pool:{provider_id}"
    except Exception:
        pass

    return "", ""


def resolve_api_key_provider_credentials(provider_id: str) -> dict[str, Any]:
    """Resolve API key and base URL for an API-key provider.

    Returns dict with: provider, api_key, base_url, source.
    """
    pconfig = PROVIDER_REGISTRY.get(provider_id)
    if not pconfig or pconfig.auth_type != "api_key":
        return {}  # Not an API-key provider — caller skips

    api_key, key_source = _resolve_api_key_provider_secret(provider_id, pconfig)
    if not api_key:
        return {}  # No credentials available

    env_url = ""
    if pconfig.base_url_env_var:
        env_url = (os.getenv(pconfig.base_url_env_var, "") or "").strip()

    base_url = env_url or pconfig.inference_base_url

    return {
        "provider": provider_id,
        "api_key": api_key,
        "base_url": base_url.rstrip("/"),
        "source": key_source or "default",
    }


# ── External-process providers (stub — not currently used) ──────────────────

def resolve_external_process_provider_credentials(provider_id: str) -> dict[str, Any]:
    """Resolve runtime details for local subprocess-backed providers.

    MimirAether does not currently support external-process providers.
    Returns empty dict (caller should skip).
    """
    return {}


# ── Configuration helpers ──────────────────────────────────────────────────

def is_provider_explicitly_configured(provider_id: str) -> bool:
    """Return True only if the user has explicitly configured this provider.

    Checks config.yaml model.provider field only — MimirAether does not
    use auth.json active_provider.
    """
    normalized = (provider_id or "").strip().lower()
    if not normalized:
        return False

    # Check config.yaml model.provider
    try:
        from agent.auxiliary_client import _load_config

        cfg = _load_config()
        model_cfg = cfg.get("model")
        if isinstance(model_cfg, dict):
            cfg_provider = (model_cfg.get("provider") or "").strip().lower()
            if cfg_provider == normalized:
                return True
    except Exception:
        pass

    # Check provider-specific env vars
    pconfig = PROVIDER_REGISTRY.get(normalized)
    if pconfig:
        for env_var in pconfig.api_key_env_vars:
            if _has_usable_secret(os.getenv(env_var, "")):
                return True

    return False
