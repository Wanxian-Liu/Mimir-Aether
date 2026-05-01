# Notes for agents and contributors

## Direction (do not drift)

Read **`docs/DEVELOPMENT_NORTH_STAR.md`** before large changes: **Parity** (Hermes-aligned behavior with evidence) and **Evolution** (measurable gain + regression). It scopes this repo vs isolated clones and links the Ralph contract, migration lossy points, and the three gates.

## Authoritative workspace

Use **`~/.openclaw/projects/MimirAether`** as the **only** git root for commits, pushes, and local verification. Other directories (e.g. backups or duplicate checkouts) are not the source of truth unless you explicitly reconcile them.

## Paths and config

Follow **`docs/path-contract.md`**: agent home vs profile roots vs `~/.openclaw/config.yaml` platform layer. Avoid ad-hoc home-dir logic in new code.

## Merge gate

Before pushing, **`./run_ralph_tier0.sh`** must pass (repository pre-push hook runs the same checks).
