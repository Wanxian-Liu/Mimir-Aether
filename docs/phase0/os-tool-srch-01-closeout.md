# OS-TOOL-SRCH-01 closeout — ToolRanker / tool_search

**Grain:** `OS-TOOL-SRCH-01` · Wave 13 Task 10  
**Backlog:** `docs/MIMIR_EXEC_BACKLOG.md` §18.2 / §19.1  
**Base:** `3b04452`

## Problem

Agents had `skills_list` and a large registry but no **query-ranked discovery** when the right tool or skill was unclear. OS-SCH-02 established RRF fusion for session search; tool search needed the same pattern without copying OpenSpace code.

## Delivered

| Piece | Path |
|-------|------|
| **ToolRanker** | `agent/tool_ranker.py` — index from registry schemas + `skills_list`; lexical + quality RRF via `rank_fusion_rrf` |
| **Agent tool** | `tools/tool_search_tool.py` — `tool_search` registered on `tools.registry` |
| **Wiring** | `model_tools._discover_tools`, `tools/toolsets.py` (`tool_search` toolset + core list), `mimir_cli/tools_config.py` |
| **Env** | `MIMIR_TOOL_SEARCH=1` (default on); `MIMIR_TOOL_QUALITY` feeds quality ranker when on |
| **Tests** | `tests/agent/test_tool_ranker.py`, `tests/contract/test_horizon_os_tool_srch_01.py` |

## Verify

```bash
python3 -m pytest tests/agent/test_tool_ranker.py tests/contract/test_horizon_os_tool_srch_01.py -q
./run_ralph_tier0.sh
```

Manual (loads registry via `_ensure_tools_discovered`):

```bash
python3 -c "from agent.tool_ranker import search_tools; print(search_tools('read file', limit=3))"
```

Expect top hit **`read_file`** (tool). Benign `Failed to parse frontmatter` lines may appear while scanning user skills with malformed YAML.

## Gateway

**No restart required** — new tool loads on next agent process start (import `model_tools` / gateway runner recycle as usual).

## Next

- **P3-XSR-01** — cross-session retrieval proposal (Wave 14 · doc-only)
