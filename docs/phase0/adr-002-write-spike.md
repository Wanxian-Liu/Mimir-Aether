# ADR-002 spike — three memory write paths (IQ-EVO-39)

> **Status:** spike only — **no code change** to write paths.  
> **ISSUES:** #3 remains `deferred`.

## Three entry points

| # | Entry | Typical target | When used |
|---|--------|----------------|-----------|
| A | HTML capsules | `$MIMIR_AETHER_HOME/memory/capsules/` | Durable user facts / preferences |
| B | `persistent.json` | `$MIMIR_AETHER_HOME/data/persistent.json` | Progress, skill curator metadata |
| C | External wiki | llm-wiki / obsidian | Human or offline; not agent default |

Legacy **mimicore/public/*.md** is read-only archive — do not treat as write target.

## Recommended order (new writes)

1. **Session-local / ephemeral** → do not write; use `session_search` + transcripts.  
2. **User-stable facts** → capsules (HTML contract).  
3. **Agent progress / skills meta** → `persistent.json` via existing curator paths only.  
4. **Wiki** → explicit human export; no automatic dual-write from gateway.

## Unification (Phase 2+)

- Depends on **ADR-001** single-writer for `persistent.json` (IND-05 done).  
- Single **MemoryFacade** should route A/B with one audit log — out of Wave 6 scope.

## References

- [ADR-002 stub](../adr/002-memory-write-paths.md)  
- [`MIMIR_HTML_MEMORY_CONTRACT.md`](../MIMIR_HTML_MEMORY_CONTRACT.md)
