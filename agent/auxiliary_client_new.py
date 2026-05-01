
import json
import logging
import os
import threading
import time
import re
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
import yaml
from pathlib import Path

from mimir_constants import get_mimir_home

def __load_config():
    config_path = get_mimir_home() / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}

logger = logging.getLogger(__name__)

# ============================================================================
# Provider Aliases
# ============================================================================

_PROVIDER_ALIASES: Dict[str, str] = {
    "google": "gemini",
    "google-gemini": "gemini",
    "google-ai-studio": "gemini",
    "glm": "zai",
    "z-ai": "zai",
    "z.ai": "zai",
    "zhipu": "zai",
    "kimi": "kimi-coding",
    "moonshot": "kimi-coding",
    "kimi-cn": "kimi-coding-cn",
    "moonshot-cn": "kimi-coding-cn",
    "minimax-china": "minimax-cn",
    "minimax_cn": "minimax-cn",
    "claude": "anthropic",
    "claude-code": "anthropic",
}


def _normalize_aux_provider(provider: Optional[str]) -> str:
    """Normalize provider name through alias table."""
    normalized = (provider or "auto").strip().lower()
    if normalized.startswith("custom:"):
        suffix = normalized.split(":", 1)[1].strip()
        return suffix if suffix else "custom"
    if normalized == "codex":
        return "openai-codex"
    if normalized == "main":
        main_prov = _read_main_provider()
        if main_prov and main_prov not in ("auto", "main", ""):
            return main_prov
        return "custom"
    return _PROVIDER_ALIASES.get(normalized, normalized)


# ============================================================================
# Default auxiliary models per provider
# ============================================================================

_OPENROUTER_MODEL = "google/gemini-3-flash-preview"
_NOUS_MODEL = "google/gemini-3-flash-preview"
_NOUS_DEFAULT_BASE_URL = "https://inference-api.nousresearch.com/v1"
_ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com"
_CODEX_AUX_MODEL = "gpt-5.2-codex"
_CODEX_AUX_BASE_URL = "https://chatgpt.com/backend-api/codex"

_API_KEY_PROVIDER_AUX_MODELS: Dict[str, str] = {
    "gemini": "gemini-3-flash-preview",
    "zai": "glm-4.5-flash",
    "kimi-coding": "kimi-k2-turbo-preview",
    "kimi-coding-cn": "kimi-k2-turbo-preview",
    "minimax": "MiniMax-M2.7",
    "minimax-cn": "MiniMax-M2.7",
    "anthropic": "claude-haiku-4-5-20251001",
    "deepseek": "deepseek-chat",
    "ai-gateway": "google/gemini-3-flash",
    "opencode-zen": "gemini-3-flash",
    "opencode-go": "glm-5",
    "kilocode": "google/gemini-3-flash-preview",
}

_PROVIDER_VISION_MODELS: Dict[str, str] = {
    "xiaomi": "mimo-v2-omni",
}

# OpenRouter attribution headers
_OR_HEADERS = {
    "HTTP-Referer": "https://mimir-aether.nousresearch.com",
    "X-OpenRouter-Title": "MimirAether",
}

# Nous Portal extra_body tags
NOUS_EXTRA_BODY = {"tags": ["product=mimir-aether"]}

# Module-level state
auxiliary_is_nous: bool = False
_stale_base_url_warned: bool = False

# ============================================================================
# Credential Pool Integration
# ============================================================================

def _select_pool_entry(provider: str) -> Tuple[bool, Optional[Any]]:
    """Return (pool_exists, selected_entry) from credential pool."""
    try:
        from agent.credential_pool import load_pool
        pool = load_pool(provider)
    except Exception as exc:
        logger.debug("Auxiliary: could not load pool for %s: %s", provider, exc)
        return False, None
    if not pool or not pool.has_credentials():
        return False, None
    try:
        return True, pool.select()
    except Exception as exc:
        logger.debug("Auxiliary: could not select pool entry for %s: %s", provider, exc)
        return True, None


def _pool_runtime_api_key(entry: Any) -> str:
    """Extract API key from pool entry."""
    if entry is None:
        return ""
    key = getattr(entry, "runtime_api_key", None) or getattr(entry, "access_token", "")
    return str(key or "").strip()


def _pool_runtime_base_url(entry: Any, fallback: str = "") -> str:
    """Extract base URL from pool entry."""
    if entry is None:
        return str(fallback or "").strip().rstrip("/")
    url = (
        getattr(entry, "runtime_base_url", None)
        or getattr(entry, "inference_base_url", None)
        or getattr(entry, "base_url", None)
        or fallback
    )
    return str(url or "").strip().rstrip("/")


def _to_openai_base_url(base_url: str) -> str:
    """Normalize Anthropic-style base URL to OpenAI-compatible /v1 format."""
    url = str(base_url or "").strip().rstrip("/")
    if url.endswith("/anthropic"):
        rewritten = url[:-len("/anthropic")] + "/v1"
        logger.debug("Auxiliary: rewrote base URL %s -> %s", url, rewritten)
        return rewritten
    return url


# ============================================================================
# Config Helpers
# ============================================================================

def _read_main_model() -> str:
    """Read user's configured main model from config.yaml."""
    try:
        cfg = _load_config()
        model_cfg = cfg.get("model", {})
        if isinstance(model_cfg, str) and model_cfg.strip():
            return model_cfg.strip()
        if isinstance(model_cfg, dict):
            default = model_cfg.get("default", "")
            if isinstance(default, str) and default.strip():
                return default.strip()
    except Exception:
        pass
    return ""


def _read_main_provider() -> str:
    """Read user's configured main provider from config.yaml."""
    try:
        cfg = _load_config()
        model_cfg = cfg.get("model", {})
        if isinstance(model_cfg, dict):
            provider = model_cfg.get("provider", "")
            if isinstance(provider, str) and provider.strip():
                return provider.strip().lower()
    except Exception:
        pass
    return ""


def _current_custom_base_url() -> str:
    """Get current custom endpoint base URL."""
    custom_base, _, _ = _resolve_custom_runtime()
    return custom_base or ""
