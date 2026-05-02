#!/usr/bin/env bash
# Append one M6 evolution row and run ./run_ralph_tier0.sh (full Gate1–3).
# Usage: ./scripts/record_m6_evolution.sh "summary line"
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SUMMARY="${1:-}"
if [[ -z "${SUMMARY}" ]]; then
  echo "usage: $0 \"one-line summary\"" >&2
  exit 2
fi

LOG_FILE="${ROOT}/docs/evolution_log.md"
UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
RUN_STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
SHORT="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
DIRTY=""
if ! git diff --quiet 2>/dev/null; then
  DIRTY="-dirty"
fi
REV="${SHORT}${DIRTY}"
RUN_ID="${RUN_STAMP}_${SHORT}${DIRTY}"

TMP_OUT="$(mktemp)"
set +e
./run_ralph_tier0.sh >"${TMP_OUT}" 2>&1
RC=$?
set -e

ROW="| ${RUN_ID} | ${UTC} | ${REV} | ./run_ralph_tier0.sh | ${RC} | ${SUMMARY} |"
printf '%s\n' "${ROW}" >>"${LOG_FILE}"

echo "Appended to ${LOG_FILE}"
echo "${ROW}"
if [[ "${RC}" -ne 0 ]]; then
  echo "--- last 40 lines of gate output ---"
  tail -n 40 "${TMP_OUT}"
fi
rm -f "${TMP_OUT}"
exit "${RC}"
