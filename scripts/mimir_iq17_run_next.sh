#!/usr/bin/env bash
# Print the first open IQ-17 grain from MIMIR_TASK_QUEUE.md §11.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUEUE="$ROOT/docs/MIMIR_TASK_QUEUE.md"
PLAN="$ROOT/docs/MIMIR_IQ17_EXECUTION_PLAN.md"

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
    /^## 11\. IQ/ { in11=1; next }
    in11 && /^## [0-9]+\./ && !/^## 11\./ { exit }
    in11 && /^\| \*\*IQ-/ && /\| \[ \] \|/ {
      gsub(/\*\*/,"",$2)
      print $2
      exit
    }
  ' "$QUEUE"
)"

if [[ -z "${next:-}" ]]; then
  echo "NEXT_TASK=NONE (§11 all [x] or table missing)"
  exit 0
fi

echo "NEXT_TASK=$next"
echo "PLAN=$PLAN"
echo "QUEUE=$QUEUE §11"

if [[ $dry -eq 1 ]]; then
  grep -A2 "### $next " "$PLAN" 2>/dev/null | head -5 || true
fi
