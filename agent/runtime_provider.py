"""MimirAether native runtime provider — replaces hermes_cli.runtime_provider.

Handles resolution of custom runtime providers from config.yaml and
credential pool fallback for API-key providers.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_named_custom_provider(requested_provider: str) -> dict[str, Any] | None:
    """Look up a named custom provider in config.yaml ``providers:`` dict.

    Args:
        requested_provider: Canonical provider id (e.g. ``"custom:my-ep"``).

    Returns:
        Dict with keys ``name``, ``base_url``, ``api_key`` or None.
    """
    requested_norm = (requested_provider or "").strip()
    if not requested_norm or requested_norm == "custom":
        return None

    # Parse "custom:name" syntax
    if requested_norm.startswith("custom:"):
        lookup_name = requested_norm[len("custom:"):]
    else:
        lookup_name = requested_norm

    if not lookup_name or lookup_name.lower() == "auto":
        return None

    try:
        from agent.auxiliary_client import _load_config

        config = _load_config()
    except Exception:
        return None

    # Check providers: dict (config.yaml providers: section)
    providers = config.get("providers")
    if isinstance(providers, dict):
        for ep_name, entry in providers.items():
            if not isinstance(entry, dict):
                continue
            if requested_norm not in (ep_name, f"custom:{ep_name}"):
                continue

            # Resolve API key from env var or inline
            key_env = str(entry.get("key_env", "") or "").strip()
            resolved_key = os.getenv(key_env, "").strip() if key_env else ""
            if not resolved_key:
                resolved_key = str(entry.get("api_key", "") or "").strip()

            base_url = entry.get("api") or entry.get("url") or entry.get("base_url") or ""
            if base_url:
                return {
                    "name": str(entry.get("name", ep_name)),
                    "base_url": str(base_url).strip(),
                    "api_key": resolved_key,
                    "source": "config",
                }
    return None


def resolve_runtime_provider(
    *,
    requested: str | None = None,
    explicit_api_key: str | None = None,
    explicit_base_url: str | None = None,
) -> dict[str, Any]:
    """Resolve runtime provider credentials.

    Simplified for MimirAether: handles "custom" provider via config.yaml
    and API-key providers via the provider registry / credential pool.

    Args:
        requested: Provider id, e.g. ``"custom"`` or ``"deepseek"``.
        explicit_api_key: Override API key.
        explicit_base_url: Override base URL.

    Returns:
        Runtime dict or empty dict on failure.
    """
    requested_provider = (requested or "").strip().lower()

    # 1. Named custom endpoint ("custom" or "custom:name")
    if requested_provider == "custom" or requested_provider.startswith("custom:"):
        custom = _get_named_custom_provider(requested_provider)
        if custom:
            if explicit_api_key:
                custom["api_key"] = explicit_api_key
            if explicit_base_url:
                custom["base_url"] = explicit_base_url
            return {
                "provider": requested_provider,
                "api_mode": "chat_completions",
                "base_url": custom["base_url"].rstrip("/"),
                "api_key": custom["api_key"],
                "source": custom.get("source", "config"),
            }
        # No custom endpoint configured
        return {}

    # 2. Explicit API-key override
    if explicit_api_key:
        from agent.provider_registry import PROVIDER_REGISTRY

        pconfig = PROVIDER_REGISTRY.get(requested_provider) if requested_provider else None
        base_url = (explicit_base_url or "").strip()
        if not base_url and pconfig:
            base_url = pconfig.inference_base_url
        if not base_url:
            return {}
        return {
            "provider": requested_provider or "custom",
            "api_mode": "chat_completions",
            "base_url": base_url.rstrip("/"),
            "api_key": explicit_api_key,
            "source": "explicit",
        }

    # 3. Known provider via registry
    if requested_provider:
        from agent.provider_registry import PROVIDER_REGISTRY, resolve_api_key_provider_credentials

        creds = resolve_api_key_provider_credentials(requested_provider)
        if creds and creds.get("api_key"):
            return {
                "provider": requested_provider,
                "api_mode": "chat_completions",
                "base_url": creds["base_url"].rstrip("/"),
                "api_key": creds["api_key"],
                "source": creds.get("source", "default"),
            }

    return {}
