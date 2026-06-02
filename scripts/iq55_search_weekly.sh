#!/usr/bin/env bash
# IQ55-10d: Weekly search-first audit snapshot
# Writes to data/ops/search-first-weekly.json for SELF-LOOP consumption.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPS_DIR="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}/data/ops"
mkdir -p "$OPS_DIR"

OUTPUT="$OPS_DIR/search-first-weekly.json"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cd "$REPO_ROOT"
python3 scripts/search_first_audit.py 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
summary = {
    'timestamp': '$TIMESTAMP',
    'recall_total': data.get('recall_candidates_total', 0),
    'violation_rate': data.get('violation_rate'),
    'filtered_recall_total': data.get('filtered_recall_candidates_total', 0),
    'filtered_violation_rate': data.get('filtered_violation_rate'),
    'sample_size': data.get('sample_size', 0),
    'filtered_sample_size': data.get('filtered_sample_size', 0),
}
with open('$OUTPUT', 'w') as f:
    json.dump(summary, f, indent=2)
print(f'Wrote {len(json.dumps(summary))} bytes to $OUTPUT')
print(f'  filtered_violation_rate={summary[\"filtered_violation_rate\"]}')
"

echo "search_first_audit weekly snapshot done: $(date -u)"
