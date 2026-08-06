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

# --retry=N: Ralph Wiggum Loop — retry failing gates up to N times
RETRY_COUNT=0  # default: no retry
if [[ "${1:-}" =~ ^--retry=([0-9]+)$ ]]; then
  RETRY_COUNT="${BASH_REMATCH[1]}"
  echo "=== Ralph Wiggum Loop: --retry=${RETRY_COUNT}, ${RETRY_COUNT} consecutive fail(s) to abort ==="
elif [[ "${2:-}" =~ ^--retry=([0-9]+)$ ]]; then
  RETRY_COUNT="${BASH_REMATCH[1]}"
  echo "=== Ralph Wiggum Loop: --retry=${RETRY_COUNT}, ${RETRY_COUNT} consecutive fail(s) to abort ==="
fi

# --changed-only: incremental mode (git diff HEAD → test subset)
INCREMENTAL=false
ARG_POS=1
for arg in "$@"; do
  if [[ "$arg" == "--changed-only" ]]; then
    INCREMENTAL=true
  fi
done

if [ "$INCREMENTAL" = true ]; then
  CHANGED_FILES=$(git diff HEAD --name-only 2>/dev/null || echo "")
  CHANGED_COUNT=$(echo "$CHANGED_FILES" | grep -c . 2>/dev/null || echo "0")
  echo "=== --changed-only: ${CHANGED_COUNT} file(s) changed ==="
  if [ "${CHANGED_COUNT}" -gt 15 ] 2>/dev/null; then
    echo "*** >15 files changed, falling back to full run ***"
    INCREMENTAL=false
  fi
  # Audit log with audit hash
  mkdir -p "$ROOT_DIR/logs"
  AUDIT_HASH=$(echo "$CHANGED_FILES" | sha256sum | head -c 16)
  {
    echo "[$(date -Iseconds)] incremental-run | hash=${AUDIT_HASH} | files=${CHANGED_COUNT}"
    echo "$CHANGED_FILES"
    echo "---"
  } >> "$ROOT_DIR/logs/incremental-run.log"
fi

# --fidelity-gate: Change2Task 保真度门禁 (files/hunks/lines 比率 + 阈值报警)
FIDELITY=false
for arg in "$@"; do
  if [[ "$arg" == "--fidelity-gate" ]]; then
    FIDELITY=true
  fi
done

if [ "$FIDELITY" = true ]; then
  echo "=== --fidelity-gate: Change2Task 保真度检测 ==="
  cd "$ROOT_DIR"
  # 变更文件数 / hunks / lines 统计（git diff 默认 HEAD）
  DIFF_STAT=$(git diff HEAD --stat 2>/dev/null | tail -1 || echo "0 files changed")
  FILE_COUNT=$(echo "$DIFF_STAT" | grep -oP '^\s*\d+' || echo 0)
  FILES_CHANGED=$(git diff HEAD --name-only 2>/dev/null | grep -c . || echo 0)
  HUNK_COUNT=$(git diff HEAD 2>/dev/null | grep -c '^@@' || echo 0)
  LINE_ADD=$(git diff HEAD 2>/dev/null | grep -c '^+' || echo 0)
  LINE_DEL=$(git diff HEAD 2>/dev/null | grep -c '^-' || echo 0)
  TOTAL_LINES=$((LINE_ADD + LINE_DEL))
  echo "files=${FILES_CHANGED} | hunks=${HUNK_COUNT} | +${LINE_ADD} -${LINE_DEL}"

  # 结构漂移检测：跨文件重构/import变更 → 降级全量（OpenClaw 推论）
  STRUCTURAL=false
  if [ "${FILES_CHANGED}" -ge 3 ] 2>/dev/null; then
    IMPORT_CHANGES=$(git diff HEAD --name-only 2>/dev/null | grep -cE 'import|__init__|package|requirements|\.proto$|\.sql$' || echo 0)
    if [ "${IMPORT_CHANGES}" -gt 0 ] 2>/dev/null; then
      STRUCTURAL=true
      echo "*** 结构漂移检测：import/package/架构文件变更 → 建议全量测试 ***"
    fi
  fi

  # 保真度聚合分（Change2Task 权重：files 0.18 + hunks 0.20 + lines 0.28）
  if [ "${FILES_CHANGED}" -gt 0 ] 2>/dev/null && [ "${TOTAL_LINES}" -gt 0 ] 2>/dev/null; then
    # line/hunk 比率（Change2Task：≥0.50 且 ≤2.50）
    RATIO_LH=$(python3 -c "print(f'{(TOTAL_LINES / max(HUNK_COUNT,1)):.2f}')" 2>/dev/null || echo "0.00")
    # 简化保真度分：line覆盖率 vs file 数（>1 file = 上下文扩散）
    FIDELITY_SCORE=$(python3 -c "
fc=$FILES_CHANGED; tl=$TOTAL_LINES
# files 0.18: 1 file=1.0, 每多1文件-0.1；lines 0.28: 200±100行=1.0
f = max(0.0, 1.0 - (fc-1)*0.1)
l = min(1.0, tl/300)
score = 0.18*f + 0.28*l
print(f'{score:.2f}')
" 2>/dev/null || echo "0.00")
    echo "fidelity_score=${FIDELITY_SCORE} (基准 0.894) | line/hunk_ratio=${RATIO_LH}"

    # 阈值报警：<0.85 报警（OpenClaw 补丁：Change2Task 实测 0.894 是基线）
    if python3 -c "exit(0 if float('${FIDELITY_SCORE}') < 0.85 else 1)" 2>/dev/null; then
      echo "*** FIDELITY ALERT: score ${FIDELITY_SCORE} < 0.85 — 增量扫描可能在为测而测，考虑全量 ***"
      echo "[$(date -Iseconds)] fidelity-gate | score=${FIDELITY_SCORE} | files=${FILES_CHANGED} | hunks=${HUNK_COUNT} | lines=${TOTAL_LINES} | structural=${STRUCTURAL}" >> "$ROOT_DIR/logs/incremental-run.log"
    fi
  else
    echo "无变更或变更为空 — fidelity-gate 跳过"
  fi
fi

# --tool-quality: dump per-tool stats from tool_quality.db → JSON
TOOL_QUALITY=false
for arg in "$@"; do
  if [[ "$arg" == "--tool-quality" ]]; then
    TOOL_QUALITY=true
  fi
done

if [ "$TOOL_QUALITY" = true ]; then
  echo "=== --tool-quality: dumping tool quality stats ==="
  mkdir -p "$ROOT_DIR/docs/eval"
  cd "$ROOT_DIR"
  python3 -c '
import json, os, sys
sys.path.insert(0, ".")
from agent.tool_quality import ToolQualityManager
from datetime import datetime

qm = ToolQualityManager(enable_persistence=True)
report = qm.get_report()

report["generated"] = datetime.now().isoformat()
report["source"] = "tool_quality.db (via MIMIR_AETHER_HOME/data/)"

out_path = os.path.join(os.getcwd(), "docs", "eval", "tool-quality-20260730.json")
with open(out_path, "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
    print("Wrote {} tools / {} executions to {}".format(report["tools_tracked"], report["total_executions"], out_path))
'
  echo "=== --tool-quality: done ==="
  exit 0
fi

# --- Ralph Wiggum Loop helpers ---
ralph_retry_gate() {
  local gate_name="$1"
  local attempt=1
  local max_attempts=1
  [ "$RETRY_COUNT" -gt 0 ] && max_attempts=$((RETRY_COUNT + 1))
  local exit_code=0

  while [ "$attempt" -le "$max_attempts" ]; do
    if [ "$attempt" -gt 1 ]; then
      echo "=== Ralph Wiggum Loop: ${gate_name} attempt ${attempt}/${max_attempts} ==="
    fi
    # Run the gate body (passed as remaining args)
    shift
    set +e
    eval "$@"
    exit_code=$?
    set -e
    if [ "$exit_code" -eq 0 ]; then
      return 0
    fi
    if [ "$attempt" -lt "$max_attempts" ]; then
      echo "=== Gate ${gate_name} failed (exit ${exit_code}), saving error diff ==="
      # Save diff of failure context for debugging
      mkdir -p "$ROOT_DIR/logs"
      {
        echo "[$(date -Iseconds)] ralph-retry | gate=${gate_name} | attempt=${attempt} | exit=${exit_code}"
        echo "---"
      } >> "$ROOT_DIR/logs/ralph-wiggum.log"
      attempt=$((attempt + 1))
    else
      attempt=$((attempt + 1))
    fi
  done
  echo "*** Ralph Wiggum Loop: ${gate_name} failed after ${max_attempts} attempt(s) ***"
  return "$exit_code"
}

TARGET_FILES=(
  "cli.py"
  "api_service.py"
  "agent/core_loop.py"
  "agent/turn_loop.py"
  "agent/skill_funcs.py"
  "agent/delegate_subagent.py"
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
_GATE1_OK=false
for _attempt in $(seq 1 $((RETRY_COUNT > 0 ? RETRY_COUNT + 1 : 1))); do
  if [ "$_attempt" -gt 1 ]; then
    echo "=== Ralph Wiggum Loop: Gate1 attempt ${_attempt}/$((RETRY_COUNT + 1)) ==="
  fi
  set +e
  (
    if [ "$INCREMENTAL" = true ]; then
      CHANGED_TARGETS=()
      for f in "${TARGET_FILES[@]}"; do
        if echo "$CHANGED_FILES" | grep -qxF "$f"; then
          CHANGED_TARGETS+=("$f")
        fi
      done
      if [ ${#CHANGED_TARGETS[@]} -gt 0 ]; then
        python3 -m py_compile "${CHANGED_TARGETS[@]}"
        python3 -c "print('incremental_ok')"
      else
        echo "(incremental: no changed TARGET_FILES, skipping)"
      fi
    else
      python3 -m py_compile "${TARGET_FILES[@]}"
      python3 <<'PY'
import importlib
mods = [
    "cli",
    "api_service",
    "agent.core_loop",
    "agent.turn_loop",
    "agent.skill_funcs",
    "agent.delegate_subagent",
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
    fi
  )
  _GATE1_EXIT=$?
  set -e
  if [ "$_GATE1_EXIT" -eq 0 ]; then
    _GATE1_OK=true
    break
  fi
  if [ "$_attempt" -lt $((RETRY_COUNT > 0 ? RETRY_COUNT + 1 : 1)) ]; then
    echo "=== Gate1 failed (exit ${_GATE1_EXIT}), retry ==="
    mkdir -p "$ROOT_DIR/logs"
    echo "[$(date -Iseconds)] ralph-retry | gate=Gate1 | attempt=${_attempt} | exit=${_GATE1_EXIT}" >> "$ROOT_DIR/logs/ralph-wiggum.log"
  fi
done
if [ "$_GATE1_OK" != true ]; then
  echo "*** Ralph Wiggum Loop: Gate1 failed after $((RETRY_COUNT + 1)) attempt(s) ***"
  exit "$_GATE1_EXIT"
fi

echo "=== Ralph Tier-0: Gate2 Parity Tests ==="
_GATE2_OK=false
for _attempt in $(seq 1 $((RETRY_COUNT > 0 ? RETRY_COUNT + 1 : 1))); do
  if [ "$_attempt" -gt 1 ]; then
    echo "=== Ralph Wiggum Loop: Gate2 attempt ${_attempt}/$((RETRY_COUNT + 1)) ==="
  fi
  set +e
  (
    if [ "$INCREMENTAL" = true ]; then
      CHANGED_TEST_FILES=$(echo "$CHANGED_FILES" | grep -E '^(agent/test_|tests/).*\.py$' | tr '\n' ' ')
      if [ -n "$CHANGED_TEST_FILES" ]; then
        echo "(incremental: running ${CHANGED_COUNT} changed test file(s))"
        python3 -m pytest -q $CHANGED_TEST_FILES
      else
        echo "(incremental: no test files changed, skipping)"
      fi
    else
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
  agent/test_hermes_tool_name_align.py \
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
  tests/agent/test_conversation_nudges.py \
  tests/agent/test_wm_voe_learning.py \
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
  tests/contract/test_d5_adr_evolution_canonical.py \
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
  tests/contract/test_horizon_sem_sem07.py \
  tests/tools/test_sem05_smoke.py \
  tests/contract/test_iqevo06_closeout.py \
  tests/contract/test_horizon_iqevo_wave2.py \
  tests/contract/test_horizon_iqevo_wave3.py \
  tests/contract/test_horizon_obs_b1_01.py \
  tests/contract/test_horizon_obs_b1_02.py \
  tests/contract/test_horizon_obs_b1_03.py \
  tests/contract/test_horizon_aut_autonomy.py \
  tests/contract/test_horizon_iqevo_wave4.py \
  tests/contract/test_horizon_iqevo_wave5.py \
  tests/contract/test_horizon_iqevo_wave6.py \
  tests/contract/test_horizon_iqevo_wave7_1c.py \
  tests/contract/test_horizon_iqevo_wave7_intent.py \
  tests/agent/test_cross_session_grain_b.py \
  tests/contract/test_horizon_iqevo_wave8_grain_b.py \
  tests/agent/test_bridge_wave9.py \
  tests/contract/test_horizon_bridge_wave9.py \
  tests/tools/test_wave6_evidence.py \
  tests/tools/test_search_first_audit.py \
  tests/tools/test_session_search_usage_baseline.py \
  tests/tools/test_label_intent_offline.py \
  tests/agent/test_analysis_artifact_guidance.py \
  tests/agent/test_feedback_collector.py \
  tests/agent/test_auto_tuner_wave5.py \
  tests/tools/test_chroma_incremental.py \
  tests/agent/test_post_close_analysis.py \
  tests/agent/test_tool_outcome.py \
  tests/agent/test_skill_curator_lifecycle.py \
  tests/contract/test_horizon_herm_cur_02.py \
  tests/agent/test_tool_call_cache_metrics.py \
  tests/contract/test_horizon_herm_tgr_02.py \
  tests/agent/test_subdirectory_hints_prompt.py \
  tests/contract/test_horizon_herm_sdh_02.py \
  tests/agent/test_tool_quality_wiring.py \
  tests/contract/test_horizon_os_tqm_02.py \
  tests/tools/test_session_search_fusion_rank.py \
  tests/contract/test_horizon_os_sch_02.py \
  tests/agent/test_think_scrubber.py \
  tests/contract/test_horizon_herm_scr_01.py \
  tests/agent/test_redact_rules.py \
  tests/contract/test_horizon_herm_red_02.py \
  tests/agent/test_context_references_feishu.py \
  tests/contract/test_horizon_herm_ctx_02.py \
  tests/agent/test_skill_description_reviewer.py \
  tests/contract/test_horizon_os_rev_01.py \
  tests/agent/test_tool_ranker.py \
  tests/contract/test_horizon_os_tool_srch_01.py \
  tests/contract/test_horizon_p3_xsr_01.py \
  tests/agent/test_cross_session_retrieval_l2.py \
  tests/contract/test_horizon_p3_xsr_02.py \
  tests/agent/test_cross_session_retrieval_l3.py \
  tests/contract/test_horizon_p3_xsr_03.py \
  tests/contract/test_horizon_engine_ws_01.py \
  tests/contract/test_horizon_engine_rollback_01.py \
  tests/agent/test_cross_session_retrieval_feishu.py \
  tests/contract/test_horizon_ops_l2_feishu_01.py \
  tests/agent/test_memory_write_facade_p3w.py \
  tests/contract/test_horizon_engine_p3w_01.py \
  tests/contract/test_horizon_engine_gw_01.py \
  tests/agent/test_conversation_nudges.py \
  tests/agent/test_persistent_single_writer_ind05.py \
  tests/agent/test_world_model_spike.py \
  tests/agent/test_wm_voe_learning.py \
  tests/agent/test_wm_voe_learning_p11.py \
  tests/agent/test_search_first_guard.py \
  tests/agent/test_verify_before_report_guard.py \
  agent/test_persistent_store_akl.py
    fi
  )
  _GATE2_EXIT=$?
  set -e
  if [ "$_GATE2_EXIT" -eq 0 ]; then
    _GATE2_OK=true
    break
  fi
  if [ "$_attempt" -lt $((RETRY_COUNT > 0 ? RETRY_COUNT + 1 : 1)) ]; then
    echo "=== Gate2 failed (exit ${_GATE2_EXIT}), retry ==="
    mkdir -p "$ROOT_DIR/logs"
    echo "[$(date -Iseconds)] ralph-retry | gate=Gate2 | attempt=${_attempt} | exit=${_GATE2_EXIT}" >> "$ROOT_DIR/logs/ralph-wiggum.log"
  fi
done
if [ "$_GATE2_OK" != true ]; then
  echo "*** Ralph Wiggum Loop: Gate2 failed after $((RETRY_COUNT + 1)) attempt(s) ***"
  exit "$_GATE2_EXIT"
fi

echo "=== Ralph Tier-1: Gate3 Core E2E (mocked LLM) ==="
python3 -m pytest -q agent/test_tier1_e2e_agent.py

echo "=== Advisory: .openclaw literals (non-blocking) ==="
python3 scripts/warn_openclaw_literals.py || true

echo "=== Ralph Tier-0/1: PASS ==="
