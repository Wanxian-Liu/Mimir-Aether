#!/usr/bin/env bash
# Minimal smoke: project home resolves via MIMIR_AETHER_HOME without relying on ~/.openclaw.
# Run from repo root, or set MIMIR_AETHER_HOME to repo root explicitly.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export MIMIR_AETHER_HOME="${MIMIR_AETHER_HOME:-$ROOT}"
export HERMES_HOME="${HERMES_HOME:-$MIMIR_AETHER_HOME}"

echo "MIMIR_AETHER_HOME=$MIMIR_AETHER_HOME"
echo "HERMES_HOME=$HERMES_HOME"

python3 <<'PY'
from pathlib import Path
import os
import importlib

root = Path(os.environ["MIMIR_AETHER_HOME"]).resolve()
from mimir_constants import get_mimir_home

assert get_mimir_home().resolve() == root, (get_mimir_home(), root)
print("ok: get_mimir_home matches MIMIR_AETHER_HOME")

from mimiraether_constants import get_mimiraether_home

assert get_mimiraether_home().resolve() == root
print("ok: get_mimiraether_home matches")

from mimicore.config.model_defaults import get_model

print("ok: mimicore get_model ->", get_model())

import mimir_constants
import gateway.sticker_cache as sc

importlib.reload(mimir_constants)
importlib.reload(sc)
expected = root / "data" / "sticker_cache.json"
assert sc.CACHE_PATH.resolve() == expected.resolve(), (sc.CACHE_PATH, expected)
print("ok: sticker_cache path ->", sc.CACHE_PATH)
PY

echo "smoke_mimir_home: all checks passed"
