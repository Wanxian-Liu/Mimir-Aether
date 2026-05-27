"""Agent tool: search registered tools and skills by query (OS-TOOL-SRCH-01)."""

from __future__ import annotations

from typing import Any, Dict

from agent.tool_ranker import search_tools, tool_search_enabled
from tools.registry import registry, tool_error, tool_result

TOOL_SEARCH_SCHEMA = {
    "name": "tool_search",
    "description": (
        "Search available tools and skills by keyword or intent. "
        "Use when unsure which tool or skill fits the task — returns ranked "
        "matches from registry schemas and skills_list metadata."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language or keyword query",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default 10)",
            },
            "include_skills": {
                "type": "boolean",
                "description": "Include skills_list entries (default true)",
            },
        },
        "required": ["query"],
    },
}


def check_tool_search_requirements() -> bool:
    return tool_search_enabled()


def _tool_search_handler(args: Dict[str, Any], **kw: Any) -> str:
    if not tool_search_enabled():
        return tool_error("tool_search disabled (MIMIR_TOOL_SEARCH=0)", success=False)
    query = str(args.get("query") or "").strip()
    if not query:
        return tool_error("query is required", success=False)
    try:
        limit = int(args.get("limit", 10))
    except (TypeError, ValueError):
        return tool_error("limit must be an integer", success=False)
    include_skills = args.get("include_skills", True)
    if isinstance(include_skills, str):
        include_skills = include_skills.strip().lower() not in ("0", "false", "no")
    hits = search_tools(
        query,
        limit=max(1, min(limit, 25)),
        include_skills=bool(include_skills),
    )
    return tool_result(
        success=True,
        query=query,
        count=len(hits),
        results=hits,
    )


registry.register(
    name="tool_search",
    toolset="tool_search",
    schema=TOOL_SEARCH_SCHEMA,
    handler=lambda args, **kw: _tool_search_handler(args, **kw),
    check_fn=check_tool_search_requirements,
    emoji="🔧",
)
