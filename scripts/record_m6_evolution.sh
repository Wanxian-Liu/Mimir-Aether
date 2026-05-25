#!/usr/bin/env bash
# Append one M6 evolution row and run ./run_ralph_tier0.sh (full Gate1–3).
# Usage: ./scripts/record_m6_evolution.sh "summary line"
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ── core: record one row into evolution_log.md ──────────────────────
record_evolution_log() {
  local summary="$1"
  local exit_code="$2"
  local log_file="${ROOT}/docs/evolution_log.md"
  local utc run_stamp short dirty rev run_id

  utc="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  run_stamp="$(date -u +"%Y%m%dT%H%M%SZ")"
  short="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
  dirty=""
  if ! git diff --quiet 2>/dev/null; then
    dirty="-dirty"
  fi
  rev="${short}${dirty}"
  run_id="${run_stamp}_${short}${dirty}"

  local row="| ${run_id} | ${utc} | ${rev} | ./run_ralph_tier0.sh | ${exit_code} | ${summary} |"
  printf '%s\n' "${row}" >>"${log_file}"
  echo "${row}"
}

# ── score: update evolution score ──────────────────────────────────
update_score() {
  local summary="$1"
  local exit_code="$2"
  # score = 100 - (exit_code * 10), floor at 0
  local score=$(( 100 - exit_code * 10 ))
  if (( score < 0 )); then score=0; fi
  echo "[score] exit_code=${exit_code} → score=${score}  (${summary})"
}

# ── main ────────────────────────────────────────────────────────────
SUMMARY="${1:-}"
if [[ -z "${SUMMARY}" ]]; then
  echo "usage: $0 \"one-line summary\"" >&2
  exit 2
fi

# IEVO-01 / D5-1: block pseudo-evolution markers before tier0
if ! python3 -c "
import sys
sys.path.insert(0, '${ROOT}')
from agent.evolution_audit import assert_evolution_summary_allowed
assert_evolution_summary_allowed(sys.argv[1])
" "${SUMMARY}"; then
  echo "record_m6_evolution: rejected summary (simulated:true forbidden — see docs/M6_EVOLUTION.md)" >&2
  exit 2
fi

TMP_OUT="$(mktemp)"
set +e
./run_ralph_tier0.sh >"${TMP_OUT}" 2>&1
RC=$?
set -e

record_evolution_log "${SUMMARY}" "${RC}"
update_score "${SUMMARY}" "${RC}"

if [[ "${RC}" -ne 0 ]]; then
  echo "--- last 40 lines of gate output ---"
  tail -n 40 "${TMP_OUT}"
fi
rm -f "${TMP_OUT}"
exit "${RC}"
