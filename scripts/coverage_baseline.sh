#!/usr/bin/env bash
# coverage_baseline.sh — Run pytest with coverage for agent/gateway/tools
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Coverage Baseline ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
echo ""

PYTHON_BIN="${REPO_ROOT}/.venv/bin/python3"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

"${PYTHON_BIN}" -m pytest \
  --cov=agent --cov=gateway --cov=tools \
  --cov-config=.coveragerc \
  --cov-report=term-missing \
  tests/ \
  2>&1

echo ""
echo "=== Done ==="
