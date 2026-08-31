#!/usr/bin/env bash
# Validate M4 HTTP fixtures + classification tests (no network).
# After editing fixtures/m4_http/*.json, run this or full ./run_ralph_tier0.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "M4 fixtures: ${ROOT}/fixtures/m4_http/"
PYTHON_BIN="${ROOT}/.venv/bin/python3"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi
"${PYTHON_BIN}" -m pytest -q agent/test_m4_auxiliary_http_slice.py
echo "OK — fixtures and offline classification tests passed."
