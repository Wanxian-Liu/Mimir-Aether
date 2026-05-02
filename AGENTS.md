# Notes for agents and contributors

## Progress inquiries

When the user asks for **进度 / 主线 / 完成度** (or similar):

1. **Read** **`docs/MAINLINE_STATUS.md`** first.
2. Refresh it from current repo truth (milestones, growth stages, optional `./run_ralph_tier0.sh` if relevant).
3. Set **最近更新** to today and append a one-line **更新日志** entry if anything changed.
4. Reply with a concise summary; the file is the durable snapshot the user can diff over time.

## Direction (do not drift)

Read **`docs/DEVELOPMENT_NORTH_STAR.md`** before large changes: **Parity** (Hermes-aligned behavior with evidence) and **Evolution** (measurable gain + regression). It scopes this repo vs isolated clones and links the Ralph contract, migration lossy points, and the three gates.

## Authoritative workspace

Use **`~/.openclaw/projects/MimirAether`** as the **only** git root for commits, pushes, and local verification. Other directories (e.g. backups or duplicate checkouts) are not the source of truth unless you explicitly reconcile them.

## Paths and config

Follow **`docs/path-contract.md`**: agent home vs profile roots vs `~/.openclaw/config.yaml` platform layer. Avoid ad-hoc home-dir logic in new code.

## Ralph mode (strict iteration)

When **Ralph 模式** is requested: follow **`docs/RALPH_MODE.md`** — iterate in the sandbox with **`./run_ralph_tier0.sh`**, log each round (问题 → 修复 → 验证), and require **3 consecutive** full passes with zero failures before calling the task done.

## Merge gate

Before pushing, **`./run_ralph_tier0.sh`** must pass (repository pre-push hook runs the same checks).
