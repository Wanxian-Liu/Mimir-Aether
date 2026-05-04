#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

TARGET_FILES=(
  "cli.py"
  "api_service.py"
  "agent/core_loop.py"
  "agent/turn_loop.py"
  "agent/skill_funcs.py"
  "agent/delegate_subagent.py"
  "agent/tool_registry.py"
  "agent/llm_port.py"
  "agent/tool_port.py"
  "agent/session_port.py"
  "agent/checkpoint_port.py"
  "agent/kernel_overrides.py"
  "gateway/run.py"
  "tools/code_execution_tool.py"
)

echo "=== Ralph Tier-0: Gate1 Syntax/Import ==="
python3 -m py_compile "${TARGET_FILES[@]}"
python3 - <<'PY'
import importlib
mods = [
    "cli",
    "api_service",
    "agent.core_loop",
    "agent.turn_loop",
    "agent.skill_funcs",
    "agent.delegate_subagent",
    "agent.tool_registry",
    "agent.llm_port",
    "agent.tool_port",
    "agent.session_port",
    "agent.checkpoint_port",
    "agent.kernel_overrides",
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
  agent/test_delegate_subagent_integration.py \
  agent/test_skill_funcs.py \
  agent/test_security_fencer_and_paths.py \
  agent/test_turn_loop_budget.py \
  agent/test_write_file_arg_repair.py \
  agent/test_tool_registry_api.py \
  agent/test_tool_registry_concurrency.py \
  agent/test_cli_arg_boundaries.py \
  agent/test_m3_cli_quick_task_slice.py \
  agent/test_m3_api_chat_slice.py \
  agent/test_m4_auxiliary_http_slice.py \
  agent/test_m5_kernel_replaceability_slice.py \
  agent/test_m5_entry_llm_injection_slice.py \
  agent/test_m5_tool_port_slice.py \
  agent/test_m5_entry_tool_injection_slice.py \
  agent/test_m5_session_restore_port_slice.py \
  agent/test_m5_entry_session_injection_slice.py \
  agent/test_m5_session_db_factory_slice.py \
  agent/test_m5_checkpoint_port_slice.py \
  agent/test_m5_entry_checkpoint_injection_slice.py \
  agent/test_m5_kernel_bundle_slice.py \
  agent/test_m5_gateway_session_db_slice.py

echo "=== Ralph Tier-1: Gate3 Core E2E (mocked LLM) ==="
python3 -m pytest -q agent/test_tier1_e2e_agent.py

echo "=== Ralph Tier-0/1: PASS ==="
