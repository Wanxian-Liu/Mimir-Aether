#!/usr/bin/env bash
# ============================================================
# mimir_health_check.sh — MimirAether 就绪探针 R1-R10
# 对标: docs/MIMIR_EV_L_INDUSTRIAL_LEARNING.md §10
# 用法: bash scripts/mimir_health_check.sh [--json] [--quick]
#   --json  机器可读 JSON 输出
#   --quick 仅 R1-R5（必须 5 条）
# ============================================================
set -uo pipefail
# 注意：不用 set -e — 健康检查应跑完全部探针，不因单条失败而退出

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0; FAIL=0; WARN=0; MANUAL=0
JSON_MODE=false; QUICK_MODE=false
RESULTS=()

# --- 参数解析 ---
for arg in "$@"; do
  case "$arg" in
    --json) JSON_MODE=true ;;
    --quick) QUICK_MODE=true ;;
  esac
done

# --- 路径解析 ---
MIMIR_HOME="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_LOG="${MIMIR_HOME}/logs/agent.log"
TRUNCATE_BASELINE=19  # 当前基线，每次重启后更新

# --- 辅助函数 ---
now() { date '+%Y-%m-%dT%H:%M:%S'; }

log_result() {
  local id="$1" status="$2" detail="$3"
  RESULTS+=("{\"id\":\"$id\",\"status\":\"$status\",\"detail\":\"$detail\"}")
  case "$status" in
    PASS) ((PASS++))
          $JSON_MODE || echo -e "  ${GREEN}[PASS]${NC} $id — $detail" ;;
    FAIL) ((FAIL++))
          $JSON_MODE || echo -e "  ${RED}[FAIL]${NC} $id — $detail" ;;
    WARN) ((WARN++))
          $JSON_MODE || echo -e "  ${YELLOW}[WARN]${NC} $id — $detail" ;;
    MANUAL) ((MANUAL++))
          $JSON_MODE || echo -e "  ${YELLOW}[MANUAL]${NC} $id — $detail" ;;
  esac
}

# --- R1: tier0 全绿 ---
check_r1() {
  local tier0_out
  if [ -f "$REPO_ROOT/run_ralph_tier0.sh" ]; then
    tier0_out=$(cd "$REPO_ROOT" && bash run_ralph_tier0.sh 2>&1) && rc=0 || rc=$?
    if [ "$rc" -eq 0 ]; then
      log_result "R1" "PASS" "tier0 exit 0"
    else
      # 提取最后几行失败信息
      local tail_info
      tail_info=$(echo "$tier0_out" | tail -5 | tr '\n' ' ')
      log_result "R1" "FAIL" "tier0 exit $rc — $tail_info"
    fi
  else
    log_result "R1" "FAIL" "run_ralph_tier0.sh not found at $REPO_ROOT"
  fi
}

# --- R2: Gateway 进程存活 ---
check_r2() {
  local procs
  procs=$(pgrep -af 'gateway/run.py' 2>/dev/null || true)
  if [ -n "$procs" ]; then
    local pid
    pid=$(echo "$procs" | head -1 | awk '{print $1}')
    log_result "R2" "PASS" "pid=$pid"
  else
    log_result "R2" "FAIL" "no gateway/run.py process found"
  fi
}

# --- R3: Health 端点 ---
check_r3() {
  local health_port="${MIMIR_PORT:-18999}"
  local health
  health=$(curl -s --max-time 5 "http://127.0.0.1:${health_port}/health" 2>/dev/null || true)
  if echo "$health" | grep -q '"status"' 2>/dev/null; then
    log_result "R3" "PASS" "$health"
  else
    log_result "R3" "FAIL" "health endpoint unreachable or no status field — got: ${health:-timeout/empty}"
  fi
}

# --- R4: TRUNCATE 基线 ---
check_r4() {
  if [ -f "$AGENT_LOG" ]; then
    local count
    count=$(grep -c 'TRUNCATE' "$AGENT_LOG" 2>/dev/null || echo 0)
    local diff=$((count - TRUNCATE_BASELINE))
    if [ "$diff" -le 5 ]; then
      log_result "R4" "PASS" "TRUNCATE=$count (baseline=$TRUNCATE_BASELINE, delta=$diff ≤5)"
    else
      log_result "R4" "FAIL" "TRUNCATE=$count (baseline=$TRUNCATE_BASELINE, delta=$diff >5)"
    fi
  else
    log_result "R4" "WARN" "agent.log not found at $AGENT_LOG — cannot check TRUNCATE"
  fi
}

# --- R5: 飞书往返（需人工） ---
check_r5() {
  log_result "R5" "MANUAL" "发飞书消息让 Mimir 用 read_file 回复，确认 30s 内工具调用成功"
}

# --- R6: Mixin import 烟测 ---
check_r6() {
  # R6 通过 tier0 Gate1 体现；这里独立 grep 补充
  local mixin_tests
  mixin_tests=$(find "$REPO_ROOT/agent" -name 'test_*_mixin_imports.py' 2>/dev/null | wc -l)
  if [ "$mixin_tests" -ge 3 ]; then
    log_result "R6" "PASS" "found $mixin_tests mixin import test files"
  else
    log_result "R6" "FAIL" "only $mixin_tests mixin test files found (expect ≥3)"
  fi
}

# --- R7: Recovery 护栏在线 ---
check_r7() {
  if [ -f "$AGENT_LOG" ]; then
    local code_errors recovered
    code_errors=$(grep -cE 'NOT recovered.*(NameError|ImportError|AttributeError|ModuleNotFoundError)' "$AGENT_LOG" 2>/dev/null || echo 0)
    recovered=$(grep -cE 'TRUNCATE.*(NameError|ImportError|AttributeError|ModuleNotFoundError)' "$AGENT_LOG" 2>/dev/null || echo 0)
    if [ "$recovered" -eq 0 ]; then
      log_result "R7" "PASS" "code_errors_in_NOT_recovered=$code_errors, code_errors_in_TRUNCATE=$recovered"
    else
      log_result "R7" "FAIL" "code_errors_in_TRUNCATE=$recovered (should be 0) — code_errors_in_NOT_recovered=$code_errors"
    fi
  else
    log_result "R7" "WARN" "agent.log missing — skip"
  fi
}

# --- R8: 跨会话上下文 ---
check_r8() {
  local persistent="$MIMIR_HOME/data/persistent.json"
  if [ -f "$persistent" ]; then
    local size
    size=$(wc -c < "$persistent" 2>/dev/null || echo 0)
    if [ "$size" -gt 100 ]; then
      log_result "R8" "PASS" "persistent.json size=$size bytes (>100)"
    else
      log_result "R8" "FAIL" "persistent.json size=$size bytes (≤100, may be truncated)"
    fi
  else
    log_result "R8" "WARN" "persistent.json not found at $persistent"
  fi
}

# --- R9: Agent 错误率 ---
check_r9() {
  if [ -f "$AGENT_LOG" ]; then
    local recent_errors
    recent_errors=$(grep -c 'Agent error' "$AGENT_LOG" 2>/dev/null || echo 0)
    # NOTE: 简化版检查总量；精确版需按时间窗口过滤
    if [ "$recent_errors" -le 30 ]; then
      log_result "R9" "PASS" "Agent error total=$recent_errors (≤30)"
    else
      log_result "R9" "WARN" "Agent error total=$recent_errors (>30, 需检查最近5分钟增量)"
    fi
  else
    log_result "R9" "WARN" "agent.log missing — skip"
  fi
}

# --- R10: DeepSeek tool call 格式 ---
check_r10() {
  if [ -f "$AGENT_LOG" ]; then
    local orphans
    orphans=$(grep -c 'tool must be a response' "$AGENT_LOG" 2>/dev/null || echo 0)
    if [ "$orphans" -eq 0 ]; then
      log_result "R10" "PASS" "orphan tool_call count=$orphans"
    else
      log_result "R10" "FAIL" "orphan tool_call count=$orphans (should be 0)"
    fi
  else
    log_result "R10" "WARN" "agent.log missing — skip"
  fi
}

# ========================
# 主流程
# ========================

if ! $JSON_MODE; then
  echo "============================================"
  echo " MimirAether Health Check — $(now)"
  echo " Repo: $REPO_ROOT | Home: $MIMIR_HOME"
  echo "============================================"
  echo ""
fi

check_r1
check_r2
check_r3
check_r4
check_r5

if ! $QUICK_MODE; then
  check_r6
  check_r7
  check_r8
  check_r9
  check_r10
fi

# --- 汇总 ---
TOTAL=$((PASS + FAIL + WARN + MANUAL))
if $JSON_MODE; then
  # JSON 输出
  joined=$(IFS=,; echo "${RESULTS[*]}")
  cat <<JSON_OUT
{
  "timestamp": "$(now)",
  "repo_root": "$REPO_ROOT",
  "mimir_home": "$MIMIR_HOME",
  "mode": "$([ "$QUICK_MODE" = true ] && echo 'quick' || echo 'full')",
  "summary": {
    "total": $TOTAL,
    "pass": $PASS,
    "fail": $FAIL,
    "warn": $WARN,
    "manual": $MANUAL,
    "ready": $([ "$FAIL" -eq 0 ] && echo 'true' || echo 'false')
  },
  "results": [$joined]
}
JSON_OUT
else
  echo ""
  echo "============================================"
  echo " Summary: $TOTAL probes — ${GREEN}$PASS PASS${NC} / ${RED}$FAIL FAIL${NC} / ${YELLOW}$WARN WARN / $MANUAL MANUAL"
  if [ "$FAIL" -eq 0 ]; then
    echo -e " Verdict: ${GREEN}READY${NC} ✅"
  else
    echo -e " Verdict: ${RED}NOT READY${NC} ❌ — $FAIL probe(s) failed"
  fi
  echo "============================================"
fi

# 退出码：FAIL>0 → 1；否则 0
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
