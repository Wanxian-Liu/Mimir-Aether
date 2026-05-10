"""MimirAether native model-name normalisation — replaces hermes_cli.model_normalize.

Handles model-name translation for the providers MimirAether actually uses.
"""

from __future__ import annotations


def normalize_model_for_provider(model_input: str, target_provider: str) -> str:
    """Translate a model name into the format the target provider expects.

    Args:
        model_input: Model name (bare, vendor-prefixed, or native format).
        target_provider: Canonical provider id (e.g. ``"deepseek"``, ``"custom"``).

    Returns:
        Normalized model string for the target provider's API.
    """
    name = (model_input or "").strip()
    if not name:
        return name

    provider = (target_provider or "").strip().lower()

    # ── Strip vendor prefix if present ──
    bare = name
    if "/" in bare:
        bare = bare.split("/", 1)[-1]

    # ── DeepSeek model mapping ──
    if provider == "deepseek":
        return _normalize_deepseek(bare)

    # ── OpenRouter: needs vendor/model format ──
    if provider in ("openrouter",):
        return _prepend_vendor(name)

    # ── Custom / unknown providers: return bare name ──
    return bare


# ── Provider-specific normalizers ───────────────────────────────────────────

def _normalize_deepseek(name: str) -> str:
    """Map common model aliases to DeepSeek API model IDs."""
    mapping = {
        "deepseek-chat": "deepseek-chat",
        "deepseek-v3": "deepseek-chat",
        "deepseek-v4": "deepseek-chat",
        "deepseek-v4-pro": "deepseek-chat",
        "deepseek-reasoner": "deepseek-reasoner",
        "deepseek-r1": "deepseek-reasoner",
    }
    return mapping.get(name.lower(), name)


def _prepend_vendor(name: str) -> str:
    """Ensure model name has vendor/ prefix for aggregator providers.

    Heuristic: if already has slash, return as-is; otherwise guess vendor.
    """
    if "/" in name:
        return name
    lower = name.lower()
    if any(p in lower for p in ("deepseek",)):
        return f"deepseek/{name}"
    if any(p in lower for p in ("claude",)):
        return f"anthropic/{name}"
    if any(p in lower for p in ("gpt", "o1", "o3", "o4")):
        return f"openai/{name}"
    return f"openai/{name}"  # default fallback
