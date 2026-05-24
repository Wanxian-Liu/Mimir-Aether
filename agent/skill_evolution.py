"""
Skill Evolution Engine — FIX/DERIVED/CAPTURED evolution with apply-retry.

Opt-in: set env MIMIR_AUTO_ANALYSIS=1 to enable automated skill evolution.
Without it, build_confirmation_prompt/parse_confirmation are no-ops.

Learned from OpenSpace skill_engine/evolver.py:
  - LLM confirmation gate: cheap LLM call decides whether to run expensive evolution
  - Apply-retry cycle: apply → validate → retry with error feedback (up to N)
  - Evolution context: recent analyses + tool issues + metrics in prompt
  - Throttled evolution: limit concurrent evolutions

Design: Operates on MimirAether skills (<MIMIR_AETHER_HOME>/skills/).
Integrates with ToolQualityManager and ExecutionRecorder for context.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Awaitable

from .tool_quality import ToolQualityManager
from .post_analysis import EvolutionSuggestion, ExecutionAnalysis
from .skill_path_guard import resolve_skill_dir, resolve_skill_write_dir
from .evolution_rollback import (
    create_skill_dir_guarded,
    write_skill_md_guarded,
)


# ── Types ───────────────────────────────────────────────────────────────────

class EvolutionAction(str, Enum):
    FIX = "fix"           # In-place repair
    DERIVED = "derived"   # Create enhanced version (new dir)
    CAPTURED = "captured" # Create new skill from pattern


_ACTION_ALIASES = {
    "derive": "derived",
    "capture": "captured",
}


def normalize_evolution_action(action: str) -> str:
    """Map post_analysis verbs (derive/capture) to EvolutionAction values."""
    key = (action or "fix").strip().lower()
    return _ACTION_ALIASES.get(key, key)


@dataclass
class EvolutionContext:
    """All the context needed to evolve a skill."""
    action: EvolutionAction
    suggestion: EvolutionSuggestion
    skill_dir: Optional[Path] = None
    skill_content: str = ""
    recent_analyses: List[ExecutionAnalysis] = field(default_factory=list)
    tool_quality_report: Dict[str, Any] = field(default_factory=dict)
    max_retries: int = 3

    @property
    def target_name(self) -> str:
        return self.suggestion.target


@dataclass
class EvolutionResult:
    """Result of one evolution attempt."""
    success: bool
    action: EvolutionAction
    target: str
    changes_applied: int = 0
    error: str = ""
    output_dir: Optional[Path] = None
    diff: str = ""
    duration_ms: float = 0.0


# ── Apply-Retry Cycle ───────────────────────────────────────────────────────

async def apply_with_retry(
    apply_fn: Callable[[str], Any],
    initial_content: str,
    *,
    ctx: EvolutionContext,
    validate_fn: Callable[[Any], bool] = None,
    retry_prompt_fn: Callable[[str, str], Awaitable[str]] = None,
) -> Optional[Any]:
    """Apply evolution changes with retry on failure.

    Flow::
        1. Apply initial content
        2. Validate result (or check for errors)
        3. If failed and retries remain: ask LLM for fix → re-apply
        4. Return successful result or None after exhaustion

    Args:
        apply_fn: Takes content string, returns result (or raises on error)
        initial_content: The LLM-generated content to apply
        ctx: Evolution context (has max_retries)
        validate_fn: Optional result validator (return True if good)
        retry_prompt_fn: Optional async fn(error_msg, prev_content) → new content
    """
    content = initial_content
    last_error = ""

    for attempt in range(ctx.max_retries + 1):
        try:
            result = apply_fn(content)
            if result is None:
                last_error = "apply_fn returned None"
            elif hasattr(result, 'error') and result.error:
                last_error = result.error
            elif validate_fn and not validate_fn(result):
                last_error = "Validation failed"
            else:
                return result
        except Exception as e:
            last_error = str(e)

        # Don't retry on last attempt
        if attempt >= ctx.max_retries:
            break

        # Get retry content from LLM
        if retry_prompt_fn:
            content = await retry_prompt_fn(last_error, content)
        else:
            break  # No retry fn available, give up

    return None


# ── LLM Confirmation Gate ───────────────────────────────────────────────────

CONFIRMATION_PROMPT = """You are an evolution gatekeeper for MimirAether. Given an evolution suggestion, decide whether to proceed.

Suggestion:
  Target: {target}
  Action: {action}
  Reason: {reason}
  Priority: {priority}/5
  Confidence: {confidence}

Context:
  Recent tool issues: {tool_issues}
  Tool quality summary: {quality_summary}

Respond with ONLY this JSON:
{{"proceed": true/false, "reason": "<brief reason>"}}

Rules:
- proceed=true if the fix would clearly improve reliability or efficiency
- proceed=false if: low confidence (<0.5), trivial change, or risk of regression
"""


def build_confirmation_prompt(ctx: EvolutionContext) -> str:
    """Build the LLM confirmation prompt for an evolution context."""
    s = ctx.suggestion
    tool_issues = ", ".join(
        a.tool_issues[:3] for a in ctx.recent_analyses if a.tool_issues
    ) or "none"
    quality_summary = json.dumps(
        {k: v for k, v in ctx.tool_quality_report.items() if k != "tools"},
        indent=2,
        default=str,
    )

    return CONFIRMATION_PROMPT.format(
        target=s.target,
        action=s.action,
        reason=s.reason,
        priority=s.priority,
        confidence=s.confidence,
        tool_issues=tool_issues[:500],
        quality_summary=quality_summary[:500],
    )


def parse_confirmation(response: str) -> bool:
    """Parse LLM confirmation response (expects JSON with 'proceed' field)."""
    text = response.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    # Try JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return bool(data.get("proceed", False))
    except (json.JSONDecodeError, ValueError):
        pass

    # Keyword fallback
    import re
    if re.search(r'\bproceed\b.*\btrue\b', response, re.IGNORECASE):
        return True
    if re.search(r'\byes\b', response, re.IGNORECASE):
        return True
    if re.search(r'\bno\b', response, re.IGNORECASE):
        return False
    if re.search(r'\bskip\b', response, re.IGNORECASE):
        return False

    return False  # Default: skip


# ── Evolution Pipeline ──────────────────────────────────────────────────────

class SkillEvolutionPipeline:
    """Orchestrates skill evolution from suggestions.

    Usage::

        pipeline = SkillEvolutionPipeline(quality_mgr)
        await pipeline.evolve_from_suggestions(analysis.suggestions, skills_dir)
    """

    def __init__(
        self,
        quality_mgr: Optional[ToolQualityManager] = None,
        *,
        max_concurrent: int = 2,
        require_confirmation: bool = True,
    ):
        self._quality_mgr = quality_mgr
        self._max_concurrent = max_concurrent
        self._require_confirmation = require_confirmation
        self._total_evolved: int = 0
        self._total_skipped: int = 0

    async def evolve_from_suggestions(
        self,
        suggestions: List[EvolutionSuggestion],
        skills_dir: Path,
        *,
        recent_analyses: List[ExecutionAnalysis] = None,
        confirmation_fn: Callable[[str], Awaitable[str]] = None,
    ) -> List[EvolutionResult]:
        """Process evolution suggestions.

        For each suggestion:
        1. Build EvolutionContext
        2. LLM confirmation gate (optional, skips if no)
        3. Execute evolution action
        4. Record result

        Evolutions are rate-limited (max_concurrent at a time).
        """
        results: List[EvolutionResult] = []

        # Build contexts
        contexts: List[EvolutionContext] = []
        for s in suggestions:
            skill_dir = None
            skill_content = ""
            action = EvolutionAction(normalize_evolution_action(s.action))

            # Resolve skill directory for FIX/DERIVED
            if action in (EvolutionAction.FIX, EvolutionAction.DERIVED):
                candidate = resolve_skill_dir(skills_dir, s.target)
                if candidate is not None:
                    skill_dir = candidate
                    skill_md = candidate / "SKILL.md"
                    if skill_md.exists():
                        skill_content = skill_md.read_text(encoding="utf-8")

            ctx = EvolutionContext(
                action=action,
                suggestion=s,
                skill_dir=skill_dir,
                skill_content=skill_content[:12000],
                recent_analyses=recent_analyses or [],
                tool_quality_report=self._quality_mgr.get_report() if self._quality_mgr else {},
            )
            contexts.append(ctx)

        # Throttled concurrent execution
        sem = asyncio.Semaphore(self._max_concurrent)

        async def _evolve_one(ctx: EvolutionContext) -> EvolutionResult:
            async with sem:
                return await self._evolve_single(ctx, confirmation_fn)

        # Gather all (order preserved by gather)
        tasks = [_evolve_one(ctx) for ctx in contexts]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def _evolve_single(
        self,
        ctx: EvolutionContext,
        confirmation_fn: Optional[Callable[[str], Awaitable[str]]] = None,
    ) -> EvolutionResult:
        """Execute one evolution with optional confirmation."""
        start = time.monotonic()

        # Confirmation gate
        if self._require_confirmation and confirmation_fn:
            prompt = build_confirmation_prompt(ctx)
            try:
                response = await confirmation_fn(prompt)
                if not parse_confirmation(response):
                    self._total_skipped += 1
                    return EvolutionResult(
                        success=False,
                        action=ctx.action,
                        target=ctx.suggestion.target,
                        error="Skipped by confirmation gate",
                        duration_ms=(time.monotonic() - start) * 1000,
                    )
            except Exception as e:
                self._total_skipped += 1
                return EvolutionResult(
                    success=False,
                    action=ctx.action,
                    target=ctx.suggestion.target,
                    error=f"Confirmation failed: {e}",
                    duration_ms=(time.monotonic() - start) * 1000,
                )

        # Execute based on action type
        try:
            result = await self._execute_evolution(ctx)
            self._total_evolved += 1
            return result
        except Exception as e:
            return EvolutionResult(
                success=False,
                action=ctx.action,
                target=ctx.suggestion.target,
                error=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            )

    async def _execute_evolution(self, ctx: EvolutionContext) -> EvolutionResult:
        """Dispatch to the right evolution handler."""
        start = time.monotonic()

        if ctx.action == EvolutionAction.FIX and ctx.skill_dir:
            # FIX: repair in-place — write suggested_changes as new SKILL.md content
            skill_md = ctx.skill_dir / "SKILL.md"
            try:
                old_content = skill_md.read_text(encoding="utf-8") if skill_md.exists() else ""
            except OSError:
                old_content = ctx.skill_content

            new_content = ctx.suggestion.suggested_changes or ctx.suggestion.reason
            if not new_content:
                return EvolutionResult(
                    success=False,
                    action=ctx.action,
                    target=ctx.suggestion.target,
                    error="No suggested_changes or reason to apply",
                    duration_ms=(time.monotonic() - start) * 1000,
                )

            # Generate unified diff
            import difflib
            diff_lines = list(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=str(skill_md),
                tofile=str(skill_md),
            ))
            diff_text = "".join(diff_lines) if diff_lines else "(no changes)"

            rollback_error = write_skill_md_guarded(
                ctx.skill_dir,
                skill_md,
                new_content,
                prior_content=old_content,
            )
            if rollback_error:
                return EvolutionResult(
                    success=False,
                    action=ctx.action,
                    target=ctx.suggestion.target,
                    error=rollback_error,
                    diff=diff_text,
                    duration_ms=(time.monotonic() - start) * 1000,
                )

            return EvolutionResult(
                success=True,
                action=ctx.action,
                target=ctx.suggestion.target,
                changes_applied=1,
                output_dir=ctx.skill_dir,
                diff=diff_text,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        elif ctx.action == EvolutionAction.DERIVED and ctx.skill_dir:
            # DERIVED: create enhanced version — mkdir + copy source + apply changes
            parent = ctx.skill_dir.parent
            derived_target = f"{ctx.suggestion.target}-enhanced"
            new_dir = resolve_skill_write_dir(parent, derived_target)
            if new_dir is None:
                return EvolutionResult(
                    success=False,
                    action=ctx.action,
                    target=ctx.suggestion.target,
                    error="Derived skill path blocked by whitelist",
                    duration_ms=(time.monotonic() - start) * 1000,
                )

            source_md = ctx.skill_dir / "SKILL.md"
            source_content = ""
            try:
                if source_md.exists():
                    source_content = source_md.read_text(encoding="utf-8")
            except OSError:
                pass

            new_content = ctx.suggestion.suggested_changes or ctx.suggestion.reason
            if not new_content:
                return EvolutionResult(
                    success=False,
                    action=ctx.action,
                    target=ctx.suggestion.target,
                    error="No suggested_changes or reason for derived skill",
                    duration_ms=(time.monotonic() - start) * 1000,
                )

            # Inject derived_from annotation after frontmatter or at top
            derived_tag = f"<!-- derived_from: {ctx.suggestion.target} -->\n"
            if new_content.startswith("---"):
                parts = new_content.split("---", 2)
                if len(parts) >= 3:
                    new_content = f"---{parts[1]}---\n{derived_tag}{parts[2]}"
                else:
                    new_content = derived_tag + new_content
            else:
                new_content = derived_tag + new_content

            import difflib
            diff_lines = list(difflib.unified_diff(
                source_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=str(source_md) if source_md.exists() else "/dev/null",
                tofile=str(new_dir / "SKILL.md"),
            ))
            diff_text = "".join(diff_lines) if diff_lines else "(no changes)"

            rollback_error = create_skill_dir_guarded(
                new_dir,
                new_dir / "SKILL.md",
                new_content,
            )
            if rollback_error:
                return EvolutionResult(
                    success=False,
                    action=ctx.action,
                    target=ctx.suggestion.target,
                    error=rollback_error,
                    diff=diff_text,
                    duration_ms=(time.monotonic() - start) * 1000,
                )

            # Copy auxiliary files from source skill dir
            for src_file in ctx.skill_dir.iterdir():
                if src_file.name == "SKILL.md":
                    continue
                if src_file.is_file():
                    try:
                        import shutil
                        shutil.copy2(src_file, new_dir / src_file.name)
                    except OSError:
                        pass

            return EvolutionResult(
                success=True,
                action=ctx.action,
                target=ctx.suggestion.target,
                changes_applied=1,
                output_dir=new_dir,
                diff=diff_text,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        elif ctx.action == EvolutionAction.CAPTURED:
            # CAPTURED: create new skill from pattern — generate SKILL.md + write to disk
            new_content = ctx.suggestion.suggested_changes or ctx.suggestion.reason
            if not new_content:
                return EvolutionResult(
                    success=False,
                    action=ctx.action,
                    target=ctx.suggestion.target,
                    error="No suggested_changes or reason for captured skill",
                    duration_ms=(time.monotonic() - start) * 1000,
                )

            # Determine skills base directory (whitelist: must stay under skills_dir)
            if ctx.skill_dir is not None:
                skills_base = ctx.skill_dir.parent
            else:
                import os as _os
                _home = _os.environ.get("MIMIR_AETHER_HOME",
                         _os.environ.get("HERMES_HOME",
                         str(Path.home() / ".mimiraether")))
                skills_base = Path(_home) / "skills"

            write_dir = resolve_skill_write_dir(skills_base, ctx.suggestion.target)
            if write_dir is None:
                return EvolutionResult(
                    success=False,
                    action=ctx.action,
                    target=ctx.suggestion.target,
                    error="Skill path blocked by whitelist",
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            new_dir = write_dir

            # Wrap bare content in frontmatter if needed
            if not new_content.strip().startswith("---"):
                title = ctx.suggestion.target.replace("-", " ").replace("_", " ").title()
                priority = ctx.suggestion.priority
                confidence = f"{ctx.suggestion.confidence:.0%}" if ctx.suggestion.confidence else "N/A"
                new_content = (
                    f"---\n"
                    f"name: {ctx.suggestion.target}\n"
                    f"description: Auto-captured skill: {ctx.suggestion.reason}\n"
                    f"category: captured\n"
                    f"evolve_priority: {priority}\n"
                    f"evolve_confidence: {confidence}\n"
                    f"---\n\n"
                    f"{new_content}\n"
                )

            import difflib
            diff_lines = list(difflib.unified_diff(
                [],
                new_content.splitlines(keepends=True),
                fromfile="/dev/null",
                tofile=str(new_dir / "SKILL.md"),
            ))
            diff_text = "".join(diff_lines) if diff_lines else "(no changes)"

            rollback_error = create_skill_dir_guarded(
                new_dir,
                new_dir / "SKILL.md",
                new_content,
            )
            if rollback_error:
                return EvolutionResult(
                    success=False,
                    action=ctx.action,
                    target=ctx.suggestion.target,
                    error=rollback_error,
                    diff=diff_text,
                    duration_ms=(time.monotonic() - start) * 1000,
                )

            return EvolutionResult(
                success=True,
                action=ctx.action,
                target=ctx.suggestion.target,
                changes_applied=1,
                output_dir=new_dir,
                diff=diff_text,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        else:
            return EvolutionResult(
                success=False,
                action=ctx.action,
                target=ctx.suggestion.target,
                error=f"Unsupported action for target state",
                duration_ms=(time.monotonic() - start) * 1000,
            )

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "total_evolved": self._total_evolved,
            "total_skipped": self._total_skipped,
        }
