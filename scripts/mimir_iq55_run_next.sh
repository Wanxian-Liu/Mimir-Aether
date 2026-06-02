#!/usr/bin/env bash
# Print the first executable IQ55 grain from MIMIR_TASK_QUEUE.md §14.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUEUE="$ROOT/docs/MIMIR_TASK_QUEUE.md"
PLAN="$ROOT/docs/MIMIR_IQ55_EXECUTION_WORKFLOW.md"
ROADMAP="$ROOT/docs/MIMIR_IQ55_ROADMAP.md"

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
    /^## 14\./ { in14=1; next }
    in14 && /^## [0-9]+\./ && !/^## 14\./ { exit }
    in14 && /^\| \*\*IQ55-/ && /\| \[ \] \|/ {
      line = $0
      if (line ~ /BLOCK/) next
      if (line ~ /IQ55-OPS-0[234]/) next
      gsub(/\*\*/,"",$2)
      print $2
      exit
    }
  ' "$QUEUE"
)"

if [[ -z "${next:-}" ]]; then
  echo "NEXT_TASK=NONE (§14 all [x], BLOCK, or only IQ55-OPS rows left)"
  echo "OPS_PLAN=$ROOT/docs/phase0/mw-prod-env-all.md"
  exit 0
fi

echo "NEXT_TASK=$next"
echo "WORKFLOW=$PLAN"
echo "ROADMAP=$ROADMAP"
echo "QUEUE=$QUEUE §14"

if [[ $dry -eq 1 ]]; then
  awk -v id="$next" '
    $0 ~ ("\\*\\*" id) || $0 ~ ("### " id) { show=1 }
    show && /^### IQ55-/ && $0 !~ id { exit }
    show && /^## 波次/ && $0 !~ id && show>1 { exit }
    show { print }
  ' "$ROADMAP" 2>/dev/null | head -40 || true
fi
