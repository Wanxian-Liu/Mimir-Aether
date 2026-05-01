# Notes for agents and contributors

## Authoritative workspace

Use **`~/.openclaw/projects/MimirAether`** as the **only** git root for commits, pushes, and local verification. Other directories (e.g. backups or duplicate checkouts) are not the source of truth unless you explicitly reconcile them.

## Paths and config

Follow **`docs/path-contract.md`**: agent home vs profile roots vs `~/.openclaw/config.yaml` platform layer. Avoid ad-hoc home-dir logic in new code.

## Merge gate

Before pushing, **`./run_ralph_tier0.sh`** must pass (repository pre-push hook runs the same checks).
