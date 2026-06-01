#!/usr/bin/env bash
# Print the first executable ENG-WF grain from MIMIR_TASK_QUEUE.md §12.
# Skips rows marked BLOCK in the task column (Mimir should not take those as NEXT).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUEUE="$ROOT/docs/MIMIR_TASK_QUEUE.md"
PLAN="$ROOT/docs/MIMIR_ENGINEERING_WORKFLOW.md"

dry=0
if [[ "${1:-}" == "--dry-run" ]] || [[ "${1:-}" == "--help" ]]; then
  dry=1
fi

if [[ ! -f "$QUEUE" ]]; then
  echo "missing $QUEUE" >&2
  exit 1
fi

next="$(
  awk '
    /^## 12\./ { in12=1; next }
    in12 && /^## [0-9]+\./ && !/^## 12\./ { exit }
    in12 && /^\| \*\*ENG-WF-/ && /\| \[ \] \|/ {
      line = $0
      if (line ~ /BLOCK/) next
      gsub(/\*\*/,"",$2)
      print $2
      exit
    }
  ' "$QUEUE"
)"

if [[ -z "${next:-}" ]]; then
  echo "NEXT_TASK=NONE (§12 all [x] or only BLOCK rows)"
  exit 0
fi

echo "NEXT_TASK=$next"
echo "PLAN=$PLAN"
echo "QUEUE=$QUEUE §12"

if [[ $dry -eq 1 ]]; then
  awk -v id="$next" '
    $0 ~ ("#### " id " ") { show=1 }
    show && /^#### ENG-WF-/ && $0 !~ id { exit }
    show { print }
  ' "$PLAN" 2>/dev/null | head -40 || true
fi
