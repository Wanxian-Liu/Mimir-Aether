#!/usr/bin/env bash
set -euo pipefail
MIMIR_REPO_ROOT="${MIMIR_REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
QUEUE="$MIMIR_REPO_ROOT/docs/MIMIR_TASK_QUEUE.md"
CHAIN="$MIMIR_REPO_ROOT/docs/MIMIR_SELF_IMPROVEMENT_CHAIN.md"
id=$(grep -E '^\| \*\*SELF-' "$QUEUE" | grep '\[ \]' | head -1 | sed -n 's/.*\*\*\(SELF-[^*]*\)\*\*.*/\1/p' || true)
if [[ -z "$id" ]]; then
  echo "§10: no open [ ] (see SELF-LOOP or bridge §1)"
  exit 0
fi
echo "NEXT_TASK=$id"
echo "CHAIN=$CHAIN"
echo "Discipline: tier0 → commit → push → [x] → next grain without asking 刘哥."
awk -v id="$id" '$0 ~ "任务 " id {p=1} p{print} p && /^```$/ && n++>0 {exit}' "$CHAIN" 2>/dev/null || true
