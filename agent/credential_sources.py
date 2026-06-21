"""
Unified removal contract for every credential source MimirAether reads from.

MimirAether seeds its credential pool from two places:

    env:<VAR>    — os.environ (OPENAI_API_KEY, ANTHROPIC_API_KEY)
    config:<key> — custom_providers config (e.g. DeepSeek)

Each source has its own reader inside ``credential_pool._seed_*`` methods.
What we unify here is **removal** — making ``auth remove <provider> <N>``
actually stay gone.

Inspired by Hermes ``credential_sources.py`` but stripped to only
the sources MimirAether actually uses.  Adding a new credential source:

    1. wire up a reader branch in ``_seed_*`` (existing pattern)
    2. gate that reader behind ``is_suppressed``
    3. register a ``RemovalStep`` here

No more per-source if/elif chains.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class RemovalResult:
    """Outcome of removing a credential source.

    Attributes:
        cleaned: Short descriptions of external state that was mutated.
            Printed as plain lines to the user.
        hints: Diagnostic lines the user may need to see (shell-exported
            env vars, external files deliberately left intact, etc.).
        suppress: Whether to mark the source as suppressed so future
            ``load_pool`` calls skip it.  Default True.
    """

    cleaned: List[str] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)
    suppress: bool = True


@dataclass
class RemovalStep:
    """How to remove one specific credential source cleanly.

    Attributes:
        provider: Provider pool key (``"openai"``, ``"*"`` for any).
        source_id: Source identifier matching ``PooledCredential.source``.
            May be a literal (``"env:"``) or use ``match_fn`` for patterns.
        remove_fn: ``(provider, removed_entry) -> RemovalResult``.
        match_fn: Optional predicate that overrides literal ``source_id``
            matching.  Used for pattern sources like ``env:*``.
        description: Human-readable label for docs / tests.
    """

    provider: str
    source_id: str
    remove_fn: Callable[..., RemovalResult]
    match_fn: Optional[Callable[[str], bool]] = None
    description: str = ""

    def matches(self, provider: str, source: str) -> bool:
        if self.provider != "*" and self.provider != provider:
            return False
        if self.match_fn is not None:
            return self.match_fn(source)
        return source == self.source_id


# ---------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


_REGISTRY: List[RemovalStep] = []


def register(step: RemovalStep) -> RemovalStep:
    _REGISTRY.append(step)
    return step


def find_removal_step(provider: str, source: str) -> Optional[RemovalStep]:
    """Return the first matching RemovalStep, or None if unregistered.

    Unregistered sources fall through to the default remove path: the pool
    entry is already gone (that happens before dispatch), no external
    cleanup, no suppression.  This is correct for ``manual`` entries —
    they were only ever stored in the pool, nothing external to clean up.
    """
    for step in _REGISTRY:
        if step.matches(provider, source):
            return step
    return None


# ---------------------------------------------------------------------------
# Individual removal implementations
# ---------------------------------------------------------------------------


def _get_dotenv_path() -> Path:
    """Return path to the .env file Mimir uses."""
    # Try $MIMIR_HOME / .env first, fall back to ~/.mimiraether/.env
    mimir_home = os.getenv("MIMIR_HOME", "")
    if mimir_home:
        candidate = Path(mimir_home) / ".env"
        if candidate.exists():
            return candidate
    return Path.home() / ".mimiraether" / ".env"


def _remove_env_var_from_dotenv(env_var: str, dotenv_path: Path) -> bool:
    """Remove ``VAR=value`` lines from a .env file.  Returns True if any were removed."""
    if not dotenv_path.exists():
        return False
    try:
        lines = dotenv_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        kept = [l for l in lines if not l.strip().startswith(f"{env_var}=")]
        if len(kept) != len(lines):
            dotenv_path.write_text("".join(kept), encoding="utf-8")
            return True
    except OSError as exc:
        logger.warning("Failed to edit %s: %s", dotenv_path, exc)
    return False


def _remove_env_source(provider: str, removed) -> RemovalResult:
    """env:<VAR> — clear from .env, hint about shell if still exported."""
    result = RemovalResult()
    env_var = removed.source[len("env:"):] if removed.source.startswith("env:") else ""
    if not env_var:
        return result

    # Check environment BEFORE modifying anything
    env_in_shell = bool(os.getenv(env_var))
    dotenv_path = _get_dotenv_path()
    env_in_dotenv = _remove_env_var_from_dotenv(env_var, dotenv_path)

    if env_in_dotenv:
        result.cleaned.append(f"Cleared {env_var} from {dotenv_path.name}")

    if env_in_shell and not env_in_dotenv:
        result.hints.append(
            f"{env_var} is still set in your shell environment (not in .env). "
            f"Unset it via your shell profile / systemd / launchd plist / etc."
        )
    elif env_in_shell and env_in_dotenv:
        result.hints.append(
            f"{env_var} was cleared from .env but is still set in the current shell."
        )

    result.hints.append(
        f"Suppressed env:{env_var} — it will not be re-seeded even if re-exported."
    )
    return result


def _remove_custom_config(provider: str, removed) -> RemovalResult:
    """config:<key> — can't modify config.yaml from here; suppress only."""
    source_label = removed.source
    return RemovalResult(hints=[
        f"Suppressed {source_label} — it will not be re-seeded.",
        "Note: The underlying value in config.yaml is unchanged.  Edit it "
        "directly to remove the credential from disk.",
    ])


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
# ORDER MATTERS — ``find_removal_step`` returns the first match.  Put
# provider-specific steps before generic ``env:*``.


def _register_all_sources() -> None:
    register(RemovalStep(
        provider="*", source_id="env:",
        match_fn=lambda src: src.startswith("env:"),
        remove_fn=_remove_env_source,
        description="Any env-seeded credential (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)",
    ))
    register(RemovalStep(
        provider="*", source_id="config:",
        match_fn=lambda src: src.startswith("config:") or src == "model_config",
        remove_fn=_remove_custom_config,
        description="Custom provider config.yaml api_key field",
    ))


_register_all_sources()
