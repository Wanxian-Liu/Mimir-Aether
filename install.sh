#!/usr/bin/env bash
# MimirAether installer — one-shot setup for fresh machines
set -euo pipefail

echo "=== MimirAether Installer ==="

# 1. Python check
if ! command -v python3.11 &>/dev/null && ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 required (3.11+ recommended)"; exit 1
fi
PY=$(command -v python3.11 || command -v python3)
echo "Using Python: $($PY --version)"

# 2. Virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating venv..."
    "$PY" -m venv .venv
fi
source .venv/bin/activate

# 3. Dependencies
echo "Installing dependencies..."
pip install --quiet -r requirements.txt 2>/dev/null || pip install --quiet -r requirements-ci.txt

# 4. Runtime home (data root — keeps repo clean, 12-factor style)
MIMIR_HOME="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
mkdir -p "$MIMIR_HOME"

# 5. Config from template (never overwrite existing)
if [ ! -f "$MIMIR_HOME/config.yaml" ]; then
    cp config.example.yaml "$MIMIR_HOME/config.yaml"
    echo "Config template installed at $MIMIR_HOME/config.yaml — EDIT IT (add your API key)"
else
    echo "Config exists, skipped."
fi

# 6. Env file
if [ ! -f "$MIMIR_HOME/.env" ]; then
    cp .env.example "$MIMIR_HOME/.env"
    echo "Env template installed at $MIMIR_HOME/.env — EDIT IT"
fi

echo ""
echo "=== Done ==="
echo "Next steps:"
echo "  1. Edit $MIMIR_HOME/config.yaml   (set your LLM api_key)"
echo "  2. Edit $MIMIR_HOME/.env          (optional overrides)"
echo "  3. Run:  python api_service.py    (starts gateway on 127.0.0.1:18999)"
echo "  Docs:   docs/MIMIR_ACTIVATE.md"
