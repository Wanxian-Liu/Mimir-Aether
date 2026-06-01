#!/usr/bin/env bash
# coverage_ratchet.sh — Compare current coverage against baseline
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASELINE_DOC="$REPO_ROOT/docs/phase0/eng-wf-coverage-baseline.md"
TEMP=$(mktemp)

# Run coverage
bash "$REPO_ROOT/scripts/coverage_baseline.sh" 2>&1 | tee "$TEMP"

# Extract current TOTAL %
CURRENT=$(grep 'TOTAL' "$TEMP" | awk '{print $NF}' | tr -d '%')
# Extract baseline TOTAL %
if [ -f "$BASELINE_DOC" ]; then
    BASELINE=$(grep 'TOTAL' "$BASELINE_DOC" | grep -oP '\d+(?=%\))')
else
    echo "WARNING: No baseline doc at $BASELINE_DOC"
    BASELINE=0
fi

echo ""
echo "=== Coverage Comparison ==="
echo "Baseline: ${BASELINE}%"
echo "Current:  ${CURRENT}%"
if [ "$CURRENT" -lt "$BASELINE" ] 2>/dev/null; then
    echo "❌ REGRESSION: Coverage dropped from ${BASELINE}% to ${CURRENT}%"
    exit 1
else
    DELTA=$((CURRENT - BASELINE))
    echo "✅ ${DELTA}% improvement (or unchanged)"
fi

rm -f "$TEMP"
