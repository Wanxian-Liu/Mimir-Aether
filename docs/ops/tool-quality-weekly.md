# Tool quality — weekly one-liner (IQ-EVO-36)

From repo root:

```bash
MIMIR_AETHER_HOME=~/.mimiraether ./scripts/tool_quality_weekly.sh
```

**Bridge §4 template:**

```text
tool_quality top5: <tool1 ok%=…> … (path: $MIMIR_AETHER_HOME/data/tool_quality.db)
```

**Interpretation:** `success_rate` is lifetime ok% per tool; needs `calls >= 1` in DB. Empty DB = gateway has not persisted executions yet (documented).
