#!/usr/bin/env bash
set -euo pipefail

# If user-site .pth hooks hang startup (e.g. coverage auto-start under COVERAGE_*),
# run: MIMIR_TIER0_PYTHONNOUSERSITE=1 ./run_ralph_tier0.sh
# (skips ~/.local/.../site-packages; use a venv with deps if imports then fail.)
if [[ "${MIMIR_TIER0_PYTHONNOUSERSITE:-}" == "1" ]]; then
  export PYTHONNOUSERSITE=1
fi

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
  "gateway/session.py"
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
    "agent.config_mixin",
    "agent.callers_mixin",
    "agent.exec_mixin",
    "agent.recovery_mixin",
    "gateway._shared",
    "gateway.run",
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
  agent/test_hermes_tool_name_align.py \
  agent/test_tool_registry_concurrency.py \
  agent/test_cli_arg_boundaries.py \
  agent/test_m3_cli_quick_task_slice.py \
  agent/test_m3_api_chat_slice.py \
  agent/test_e006_health_endpoint.py \
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
  agent/test_m5_gateway_session_db_slice.py \
  agent/test_mimir_paths_resolution.py \
  agent/test_recovery_mixin_code_errors.py \
  agent/test_gateway_mixin_import_smoke.py \
  agent/test_exec_mixin_imports.py \
  tests/agent/test_agent_loop_integration.py \
  tests/agent/test_agent_loop_edge.py \
  agent/test_skill_evolution.py \
  agent/test_self_evolution_jepa.py \
  tests/agent/test_skill_evolution_smoke.py \
  tests/agent/test_self_evolution_smoke.py \
  tests/agent/test_e007_evolution_security.py \
  tests/test_mimir_cli_smoke.py \
  tests/test_e008_task_runner_compat.py \
  tests/test_mimir_cli_chat_decouple.py \
  tests/agent/test_skill_evolution_e009.py \
  tests/agent/test_evolution_loop_integration.py \
  tests/agent/test_e012_jepa_session_hook.py \
  tests/agent/test_intent_action_guard.py \
  tests/agent/test_rate_limit_tracker_lock.py \
  tests/agent/test_e006_tool_call_sql.py \
  tests/agent/test_e006_monitor.py \
  tests/agent/test_e011_monitor_duration.py \
  tests/gateway/test_e010_shared_symbol_bindings.py \
  tests/gateway/test_e011_session_hygiene_bindings.py \
  tests/agent/test_e011_agent_import_bindings.py \
  tests/agent/test_async_bridge_stab02.py \
  tests/test_feishu_ws_dispatch.py \
  tests/test_run_agent_activity.py \
  tests/agent/test_tool_guard_paths.py \
  tests/agent/test_evolution_rollback_stab05.py \
  tests/contract/test_runtime_path_independence_ind02.py \
  tests/contract/test_mimir_session_db_ind03.py \
  tests/contract/test_mimicore_openclaw_boundary_ind04.py \
  tests/contract/test_no_simulated_evolution_ievo01.py \
  tests/contract/test_evolution_tier0_manifest_ievo02.py \
  tests/contract/test_observability_sot_ievo03.py \
  tests/contract/test_evolution_eval_ievo04.py \
  tests/agent/test_ievo05_monitor_insights_regression.py \
  tests/contract/test_monitor_insights_ievo05.py \
  tests/contract/test_ievo06_wave_e_closeout.py \
  tests/contract/test_clearance_done.py \
  tests/contract/test_horizon_sem_sem01.py \
  tests/contract/test_horizon_sem_sem02.py \
  tests/contract/test_horizon_sem_sem03.py \
  tests/tools/test_chroma_session_indexer.py \
  tests/tools/test_session_search_semantic.py \
  tests/tools/test_memory_retrieval_benchmark_semantic.py \
  tests/contract/test_horizon_sem_sem04.py \
  tests/contract/test_horizon_sem_sem05.py \
  tests/contract/test_horizon_sem_sem06.py \
  tests/tools/test_sem05_smoke.py \
  tests/contract/test_iqevo06_closeout.py \
  tests/contract/test_horizon_iqevo_wave2.py \
  tests/contract/test_horizon_iqevo_wave3.py \
  tests/contract/test_horizon_obs_b1_01.py \
  tests/contract/test_horizon_obs_b1_02.py \
  tests/contract/test_horizon_obs_b1_03.py \
  tests/tools/test_chroma_incremental.py \
  tests/agent/test_post_close_analysis.py \
  tests/agent/test_conversation_nudges.py \
  tests/agent/test_persistent_single_writer_ind05.py

echo "=== Ralph Tier-1: Gate3 Core E2E (mocked LLM) ==="
python3 -m pytest -q agent/test_tier1_e2e_agent.py

echo "=== Advisory: .openclaw literals (non-blocking) ==="
python3 scripts/warn_openclaw_literals.py || true

echo "=== Ralph Tier-0/1: PASS ==="
