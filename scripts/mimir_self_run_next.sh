#!/usr/bin/env bash
# Mimir: find next [ ] grain in TASK_QUEUE.md §10
# Usage: ./scripts/mimir_self_run_next.sh [--dry-run|--help]
set -euo pipefail

MIMIR_REPO_ROOT="${MIMIR_REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
QUEUE="$MIMIR_REPO_ROOT/docs/MIMIR_TASK_QUEUE.md"
CHAIN="$MIMIR_REPO_ROOT/docs/MIMIR_SELF_IMPROVEMENT_CHAIN.md"

if [[ "${1:-}" == "--help" ]]; then
  echo "Usage: $0 [--dry-run]"
  echo "  --dry-run  (default) print next task ID without executing"
  exit 0
fi

id=$(grep -E '^\| \*\*SELF-' "$QUEUE" | grep '\[ \]' | head -1 | \
  sed -n 's/.*\*\*\(SELF-[^*]*\)\*\*.*/\1/p' || true)

if [[ -z "$id" ]]; then
  echo "§10: no open [ ] (see SELF-LOOP or bridge §1)"
  exit 0
fi

echo "NEXT_TASK=$id"
echo "CHAIN=$CHAIN"
echo "Discipline: tier0 → commit → push → [x] → next grain without asking 刘哥."

# Show the task description from the chain doc (if present)
awk -v id="$id" '
  $0 ~ "\\*\\*" id "\\*\\*" {p=1; next}
  p && /^$/ {if (c++ >= 1) exit}
  p {print}
' "$CHAIN" 2>/dev/null | head -5 || true
