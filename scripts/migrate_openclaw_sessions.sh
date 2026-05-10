#!/usr/bin/env bash
# One-time migration: copy legacy OpenClaw session files into MimirAether data layout.
# Usage:
#   MIMIR_AETHER_HOME=/path/to/MimirAether ./scripts/migrate_openclaw_sessions.sh
set -euo pipefail
ROOT="${MIMIR_AETHER_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"
OPENCLAW="${OPENCLAW_HOME:-$HOME/.openclaw}"
SRC_SESSIONS="$OPENCLAW/sessions"
DST_SESSIONS="$ROOT/data/sessions"
if [[ ! -d "$SRC_SESSIONS" ]]; then
  echo "No source directory: $SRC_SESSIONS (set OPENCLAW_HOME if non-default)"
  exit 0
fi
mkdir -p "$DST_SESSIONS"
echo "Syncing $SRC_SESSIONS -> $DST_SESSIONS"
rsync -a "$SRC_SESSIONS/" "$DST_SESSIONS/"
echo "Done. Ensure gateway uses sessions_dir under project (default: data/sessions)."
