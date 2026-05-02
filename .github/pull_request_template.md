## Summary

<!-- What this PR changes (1–3 sentences). -->

## M6 — evolution audit (merge discipline)

Check **one** box:

- [ ] **Recorded**: This PR touches `agent/`, `gateway/`, `tools/`, or parity tests under `agent/test_*.py` (or equivalent). I ran `./scripts/record_m6_evolution.sh "…"` and it exited **0** (same gate as pre-push: full `./run_ralph_tier0.sh`).
- [ ] **N/A**: Docs-only / `skills/` copy / comments / CI yaml with no runtime behavior — no M6 row required (see `docs/M6_EVOLUTION.md` §豁免).

Rules: **`docs/M6_EVOLUTION.md`**

## Checklist

- [ ] `./run_ralph_tier0.sh` passes locally (or pre-push hook ran green).
- [ ] No secrets committed (tokens, private URLs in fixtures).
