# Evolution audit log (M6)

Append-only. Newest rows at the **bottom**. See **`docs/M6_EVOLUTION.md`** for rules and `./scripts/record_m6_evolution.sh` for automation.

| run_id | utc_timestamp | git_rev | gate_command | exit_code | summary |
|--------|---------------|---------|--------------|-----------|---------|
| bootstrap_m6_2026-05-02 | 2026-05-02T00:00:00Z | 3c7d034-dirty | ./run_ralph_tier0.sh | 0 | M6: add `M6_EVOLUTION.md`, `evolution_log.md`, `scripts/record_m6_evolution.sh`; wire AGENTS + MAINLINE; tier0 evidence captured in same session. metrics: n/a |
| 20260502T185414Z_28683d7-dirty | 2026-05-02T18:54:14Z | 28683d7-dirty | ./run_ralph_tier0.sh | 0 | M4: auxiliary HTTP error classification slice; metrics: n/a |
| 20260502T202414Z_cf046f9-dirty | 2026-05-02T20:24:14Z | cf046f9-dirty | ./run_ralph_tier0.sh | 0 | M5: LlmInvocationPort slice + docs; metrics: n/a |
