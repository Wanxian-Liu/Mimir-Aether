"""Provider profiles — declarative description of LLM provider behaviours.

Hermes-aligned pattern (providers/base.py) adapted to MimirAether's architecture.
Only what's needed *today*: the OMIT_TEMPERATURE sentinel + built-in profiles
for the providers MimirAether actually uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ── Sentinel ─────────────────────────────────────────────────────────────────
OMIT_TEMPERATURE = object()


# ── ProviderProfile ──────────────────────────────────────────────────────────

@dataclass
class ProviderProfile:
    """Declarative provider descriptor — request-level quirks only."""

    name: str
    display_name: str = ""
    description: str = ""
    default_max_tokens: int | None = None
    # Temperature: None = caller's default, OMIT_TEMPERATURE = don't send
    fixed_temperature: Any = None


# ── Built-in profiles ───────────────────────────────────────────────────────

ANTHROPIC = ProviderProfile(
    name="anthropic",
    display_name="Anthropic",
    description="Claude models via Anthropic direct API",
    default_max_tokens=4096,
)

OPENAI = ProviderProfile(
    name="openai",
    display_name="OpenAI",
    description="GPT / o-series models via OpenAI API",
)

OPENROUTER = ProviderProfile(
    name="openrouter",
    display_name="OpenRouter",
    description="Multi-model router",
)

_BUILTIN: dict[str, ProviderProfile] = {
    p.name: p for p in (ANTHROPIC, OPENAI, OPENROUTER)
}

def get_profile(name: str) -> ProviderProfile | None:
    """Return a built-in profile by name."""
    return _BUILTIN.get(name)
