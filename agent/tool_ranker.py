"""
ToolRanker — search tools and skills by query (OS-TOOL-SRCH-01).

Builds a lightweight index from registry tool schemas + skills_list metadata.
Ranks with lexical token overlap fused with ToolQualityManager signals via RRF
(same pattern as session_search OS-SCH-02; imports rank_fusion_rrf, no copy).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from tools.session_search_tool import rank_fusion_rrf


def tool_search_enabled() -> bool:
    """Default on when unset (OS-TOOL-SRCH-01)."""
    return os.environ.get("MIMIR_TOOL_SEARCH", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.I)


def _tokenize(query: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(query or "") if len(t) >= 2]


def _normalize_phrase(text: str) -> str:
    return re.sub(r"[\s\-]+", "_", (text or "").lower().strip())


def _phrase_match_boost(query: str, entry: ToolSearchEntry) -> float:
    """Boost ``read file`` → ``read_file`` style matches."""
    q = _normalize_phrase(query)
    name = _normalize_phrase(entry.name)
    if not q or not name:
        return 0.0
    if name == q:
        return 12.0
    if name.startswith(q) or q.startswith(name):
        return 6.0
    return 0.0


def _ensure_tools_discovered() -> None:
    """Populate ``tools.registry`` (import-only path skips model_tools load)."""
    try:
        from model_tools import _discover_tools

        _discover_tools()
        return
    except Exception:
        pass
    try:
        import model_tools  # noqa: F401 — module import also discovers
    except Exception:
        pass


@dataclass(frozen=True)
class ToolSearchEntry:
    entry_id: str
    kind: str  # "tool" | "skill"
    name: str
    description: str
    toolset: str = ""
    category: str = ""
    text: str = ""


def _entry_text(
    *,
    name: str,
    description: str,
    toolset: str = "",
    category: str = "",
    schema_desc: str = "",
) -> str:
    parts = [name, description, toolset, category, schema_desc]
    return " ".join(p for p in parts if p).lower()


def _iter_registry_tool_entries() -> List[ToolSearchEntry]:
    _ensure_tools_discovered()
    from tools.registry import registry

    out: List[ToolSearchEntry] = []
    for name in registry.get_all_tool_names():
        entry = registry._tools.get(name)
        if not entry:
            continue
        schema = entry.schema or {}
        fn = schema.get("function") if isinstance(schema.get("function"), dict) else schema
        if not isinstance(fn, dict):
            fn = schema
        desc = (
            entry.description
            or fn.get("description", "")
            or schema.get("description", "")
        )
        schema_desc = str(fn.get("description", "") or "")
        out.append(
            ToolSearchEntry(
                entry_id=f"tool:{name}",
                kind="tool",
                name=name,
                description=str(desc)[:500],
                toolset=entry.toolset or "",
                text=_entry_text(
                    name=name,
                    description=str(desc),
                    toolset=entry.toolset or "",
                    schema_desc=schema_desc,
                ),
            )
        )
    return out


def _iter_skill_entries() -> List[ToolSearchEntry]:
    from skills.skills_loader import skills_list

    out: List[ToolSearchEntry] = []
    for meta in skills_list():
        if not isinstance(meta, dict):
            continue
        name = str(meta.get("name") or "").strip()
        if not name:
            continue
        desc = str(meta.get("description") or "No description")
        category = str(meta.get("category") or "")
        out.append(
            ToolSearchEntry(
                entry_id=f"skill:{name}",
                kind="skill",
                name=name,
                description=desc[:500],
                category=category,
                text=_entry_text(name=name, description=desc, category=category),
            )
        )
    return out


def build_tool_search_index(
    *,
    include_skills: bool = True,
    tool_entries: Optional[Iterable[ToolSearchEntry]] = None,
    skill_entries: Optional[Iterable[ToolSearchEntry]] = None,
) -> List[ToolSearchEntry]:
    """Index registry tools and optional skills_list rows."""
    tools = list(tool_entries) if tool_entries is not None else _iter_registry_tool_entries()
    if include_skills:
        skills = (
            list(skill_entries)
            if skill_entries is not None
            else _iter_skill_entries()
        )
        return tools + skills
    return tools


def _lexical_rank_ids(query: str, entries: Sequence[ToolSearchEntry]) -> List[str]:
    tokens = _tokenize(query)
    if not tokens:
        return [e.entry_id for e in entries[:50]]
    scored: List[tuple[str, float]] = []
    for entry in entries:
        blob = entry.text or _entry_text(
            name=entry.name,
            description=entry.description,
            toolset=entry.toolset,
            category=entry.category,
        )
        score = _phrase_match_boost(query, entry)
        for tok in tokens:
            if tok in entry.name.lower():
                score += 3.0
            elif tok in blob:
                score += 1.0
        if entry.kind == "tool":
            score += 0.25
        if score > 0:
            scored.append((entry.entry_id, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [entry_id for entry_id, _ in scored]


def _quality_rank_ids(
    query: str,
    entries: Sequence[ToolSearchEntry],
) -> List[str]:
    tokens = _tokenize(query)
    tool_entries = [e for e in entries if e.kind == "tool"]
    if not tool_entries:
        return []

    scores: Dict[str, float] = {}
    try:
        from agent.tool_quality import ToolQualityManager, tool_quality_enabled

        if tool_quality_enabled():
            qm = ToolQualityManager(enable_persistence=True)
            scores = {name: score for name, score in qm.rank_tools()}
    except Exception:
        scores = {}

    def matches(entry: ToolSearchEntry) -> bool:
        if not tokens:
            return True
        blob = entry.text or entry.name.lower()
        return any(tok in blob for tok in tokens)

    matched = [e for e in tool_entries if matches(e)]
    matched.sort(
        key=lambda e: (-scores.get(e.name, 0.5), e.name),
    )
    return [e.entry_id for e in matched]


def _entries_by_id(entries: Sequence[ToolSearchEntry]) -> Dict[str, ToolSearchEntry]:
    return {e.entry_id: e for e in entries}


def search_tools(
    query: str,
    *,
    limit: int = 10,
    include_skills: bool = True,
    entries: Optional[Sequence[ToolSearchEntry]] = None,
) -> List[Dict[str, Any]]:
    """
    Rank tools/skills for a natural-language query.

    Returns dicts: kind, name, description, toolset, category, score, entry_id.
    """
    if not tool_search_enabled():
        return []

    index = list(entries) if entries is not None else build_tool_search_index(
        include_skills=include_skills
    )
    if not index:
        return []

    lexical_ids = _lexical_rank_ids(query, index)
    quality_ids = _quality_rank_ids(query, index)

    fused: List[tuple[str, float]] = []
    if lexical_ids or quality_ids:
        fused = rank_fusion_rrf(
            {"lexical": lexical_ids, "quality": quality_ids},
        )
    ranked_ids = [entry_id for entry_id, _ in fused]
    score_by_id = {entry_id: score for entry_id, score in fused}

    by_id = _entries_by_id(index)
    results: List[Dict[str, Any]] = []
    for entry_id in ranked_ids:
        entry = by_id.get(entry_id)
        if not entry:
            continue
        score = score_by_id.get(entry_id, 0.0)
        results.append(
            {
                "entry_id": entry.entry_id,
                "kind": entry.kind,
                "name": entry.name,
                "description": entry.description,
                "toolset": entry.toolset,
                "category": entry.category,
                "score": round(score, 6),
            }
        )
        if len(results) >= max(1, limit):
            break
    return results
