# Evolution eval — weekly (IQ-EVO-37)

## Run

```bash
cd ~/src/MimirAether
MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh
```

## Outputs

| File | Meaning |
|------|---------|
| `$MIMIR_AETHER_HOME/data/evolution_eval/memory-retrieval-<UTC>.json` | This run |
| `$MIMIR_AETHER_HOME/data/evolution_eval/memory-retrieval-latest.json` | Pointer for compare |

## Week-over-week fields

Compare in JSON:

- `like_hit_rate` / `fts_hit_rate` / `semantic_hit_rate` (if present)
- `total_queries` / `passed`

**Gate:** exit **0** = pass vs baseline; **1** = regression; **2** = missing DB.

**Bridge §4:** `evolution_eval: exit 0 · latest=<path> · LIKE=x% FTS=y% semantic=z%`
