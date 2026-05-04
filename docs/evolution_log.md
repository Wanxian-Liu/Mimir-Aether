# Evolution audit log (M6)

Append-only. Newest rows at the **bottom**. See **`docs/M6_EVOLUTION.md`** for rules and `./scripts/record_m6_evolution.sh` for automation.

| run_id | utc_timestamp | git_rev | gate_command | exit_code | summary |
|--------|---------------|---------|--------------|-----------|---------|
| bootstrap_m6_2026-05-02 | 2026-05-02T00:00:00Z | 3c7d034-dirty | ./run_ralph_tier0.sh | 0 | M6: add `M6_EVOLUTION.md`, `evolution_log.md`, `scripts/record_m6_evolution.sh`; wire AGENTS + MAINLINE; tier0 evidence captured in same session. metrics: n/a |
| 20260502T185414Z_28683d7-dirty | 2026-05-02T18:54:14Z | 28683d7-dirty | ./run_ralph_tier0.sh | 0 | M4: auxiliary HTTP error classification slice; metrics: n/a |
| 20260502T202414Z_cf046f9-dirty | 2026-05-02T20:24:14Z | cf046f9-dirty | ./run_ralph_tier0.sh | 0 | M5: LlmInvocationPort slice + docs; metrics: n/a |
| 20260502T203104Z_b6a8cd0-dirty | 2026-05-02T20:31:04Z | b6a8cd0-dirty | ./run_ralph_tier0.sh | 0 | M5: delegate LLM to LlmInvocationPort (builtin + inject); metrics: n/a |
| 20260502T205255Z_c35d45f-dirty | 2026-05-02T20:52:55Z | c35d45f-dirty | ./run_ralph_tier0.sh | 0 | M5: CLI/API llm_backend injection; metrics: n/a |
| 20260504T140150Z_7fcfc2e-dirty | 2026-05-04T14:01:50Z | 7fcfc2e-dirty | ./run_ralph_tier0.sh | 0 | M6 pre-push soft reminder; M6 merge workflow doc; ToolRegistry WAL; stabilize tool registry concurrency test (barrier + yield) |
| 20260504T142617Z_94abd83-dirty | 2026-05-04T14:26:17Z | 94abd83-dirty | ./run_ralph_tier0.sh | 0 | M4 green: fixtures/m4_http + refresh script; JSON-driven classification tests; MAINLINE M4 green |
