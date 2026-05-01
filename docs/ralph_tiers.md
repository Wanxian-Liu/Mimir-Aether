# Ralph tiers (MimirAether)

Single entrypoint: `./run_ralph_tier0.sh` runs Gate1–Gate3 in order.

| Gate | What it proves | Files |
|------|----------------|--------|
| **Gate1** | Syntax/import smoke for CLI, core loop, tools | `run_ralph_tier0.sh` (py_compile + import) |
| **Gate2** | Hermes-parity unit/integration harness (loops, CLI edges, tools) | `run_ralph_tier0.sh` 列表（含 `test_code_execution_tool_schema`, `test_tool_registry_api` 等） |
| **Gate3 (Tier-1)** | One full `MimirAetherAgent.run_conversation` path with **stubbed** `_call_model_with_tokens` (no network, no API keys); checkpoints isolated under pytest `tmp_path` | `agent/test_tier1_e2e_agent.py` |

## Tier-1 scope (intentionally narrow)

- **Plain reply**: user message → mocked assistant text → same string returned from `run_conversation`.
- **Tool round-trip**: first mock turn returns `tool_calls`; `_execute_tools` is stubbed; second turn returns final text.

Out of scope for Tier-1: real HTTP to providers, gateway/WebSocket, or Hermes binary parity. Extend Tier-1 with additional tests in the same file as behaviors are locked in `docs/ralph_parity_contract_v1.md`.

## Related

- Milestones & completion criteria: `docs/ralph_roadmap_milestones.md`
- Parity contract (behavior targets): `docs/ralph_parity_contract_v1.md`
- Contract → pytest mapping: `docs/ralph_parity_testmap.md`
- Tier-0 case matrix: `docs/ralph_tier0_case_matrix.md`
