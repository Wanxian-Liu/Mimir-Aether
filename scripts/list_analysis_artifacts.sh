#!/usr/bin/env bash
# List post-close analysis artifacts under $MIMIR_AETHER_HOME (IQ-EVO-13).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DAYS=7
while [[ $# -gt 0 ]]; do
  case "$1" in
    --days)
      DAYS="${2:?--days requires a number}"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--days N]"
      echo "  Lists analysis_artifacts newer than N days (default 7)."
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${MIMIR_AETHER_HOME:-}" ]]; then
  # shellcheck source=/dev/null
  if [[ -f "$ROOT/scripts/start.sh" ]]; then
    # shellcheck disable=SC1091
    source "$ROOT/scripts/start.sh" 2>/dev/null || true
  fi
fi

HOME_DIR="${MIMIR_AETHER_HOME:-${HERMES_HOME:-$HOME/.mimiraether}}"
ART_DIR="$HOME_DIR/data/analysis_artifacts"

if [[ ! -d "$ART_DIR" ]]; then
  echo "analysis_artifacts: (missing) $ART_DIR"
  exit 0
fi

echo "MIMIR_AETHER_HOME=$HOME_DIR"
echo "analysis_artifacts (mtime -${DAYS}d):"
find "$ART_DIR" -maxdepth 1 -type f -name '*.json' -mtime "-${DAYS}" -printf '%T@ %TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null \
  | sort -rn \
  | awk '{ $1=""; sub(/^ /,""); print }' \
  || find "$ART_DIR" -maxdepth 1 -type f -name '*.json' -mtime "-${DAYS}" -print | sort -r

COUNT="$(find "$ART_DIR" -maxdepth 1 -type f -name '*.json' -mtime "-${DAYS}" 2>/dev/null | wc -l | tr -d ' ')"
echo "---"
echo "count (last ${DAYS}d): ${COUNT}"
