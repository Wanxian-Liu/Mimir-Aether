#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

TARGET_FILES=(
  "cli.py"
  "agent/core_loop.py"
  "agent/turn_loop.py"
  "agent/skill_funcs.py"
  "agent/delegate_subagent.py"
  "agent/tool_registry.py"
  "tools/code_execution_tool.py"
)

echo "=== Ralph Tier-0: Gate1 Syntax/Import ==="
python3 -m py_compile "${TARGET_FILES[@]}"
python3 - <<'PY'
import importlib
mods = [
    "cli",
    "agent.core_loop",
    "agent.turn_loop",
    "agent.skill_funcs",
    "agent.delegate_subagent",
    "agent.tool_registry",
    "tools.code_execution_tool",
]
for m in mods:
    importlib.import_module(m)
print("import_ok")
PY

echo "=== Ralph Tier-0: Gate2 Parity Tests ==="
python3 -m pytest -q \
  agent/test_agent_loop.py \
  agent/test_agent_loop_edge.py \
  agent/test_code_execution_tool_env.py \
  agent/test_code_execution_remote_mock.py \
  agent/test_code_execution_tool_schema.py \
  agent/test_delegate_subagent_semantics.py \
  agent/test_skill_funcs.py \
  agent/test_security_fencer_and_paths.py \
  agent/test_turn_loop_budget.py \
  agent/test_write_file_arg_repair.py \
  agent/test_tool_registry_api.py \
  agent/test_tool_registry_concurrency.py \
  agent/test_cli_arg_boundaries.py

echo "=== Ralph Tier-1: Gate3 Core E2E (mocked LLM) ==="
python3 -m pytest -q agent/test_tier1_e2e_agent.py

echo "=== Ralph Tier-0/1: PASS ==="
