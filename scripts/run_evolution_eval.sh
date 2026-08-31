#!/usr/bin/env bash
# IEVO-04 — Industrial evolution eval: 20-query memory retrieval + baseline compare.
#
# Usage (from repo root):
#   ./scripts/run_evolution_eval.sh
#   ./scripts/run_evolution_eval.sh --baseline docs/phase0/memory-retrieval-benchmark-20260524.json  # legacy (no semantic gate)
#
# Requires: $MIMIR_AETHER_HOME/data/sessions_search.db (run backfill / gateway indexing first).
# Optional: scripts/backfill_chroma_sessions.py for semantic_hit_rate leg (SEM-04).
# Writes: $MIMIR_AETHER_HOME/data/evolution_eval/memory-retrieval-<UTC>.json
#         $MIMIR_AETHER_HOME/data/evolution_eval/memory-retrieval-latest.json
#
# Exit: 0 = benchmark + compare pass; 1 = regression vs baseline; 2 = missing inputs.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# IEVO-04 FIX (议题六真根因): 评测必须跑在项目 venv 下。裸 python3 = 系统
# python (/usr/bin/python3, 无 torch/sentence-transformers) -> embedding 解析
# 静默降级 hash(384) vs collection bge-m3(1024) 维度不匹配 -> semantic_hit_rate
# 假 0.0。统一用 ${ROOT}/.venv/bin/python3，缺失即 fail-fast。
PYTHON_BIN="${ROOT}/.venv/bin/python3"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "run_evolution_eval: FATAL missing ${PYTHON_BIN} (venv with torch+sentence-transformers required)" >&2
  exit 2
fi

BASELINE="${ROOT}/docs/phase0/memory-retrieval-benchmark-20260526.json"
SKIP_COMPARE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --baseline)
      BASELINE="${2:?}"
      shift 2
      ;;
    --skip-compare)
      SKIP_COMPARE=1
      shift
      ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${MIMIR_AETHER_HOME:-}" ]]; then
  export MIMIR_AETHER_HOME="${HOME}/.mimiraether"
fi

DATA_DIR="${MIMIR_AETHER_HOME}/data"
LIKE_DB="${DATA_DIR}/sessions_search.db"
OUT_DIR="${DATA_DIR}/evolution_eval"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_JSON="${OUT_DIR}/memory-retrieval-${STAMP}.json"
LATEST_JSON="${OUT_DIR}/memory-retrieval-latest.json"
COMPARE_JSON="${OUT_DIR}/memory-retrieval-compare-${STAMP}.json"

if [[ ! -f "${LIKE_DB}" ]]; then
  echo "run_evolution_eval: missing ${LIKE_DB}" >&2
  echo "hint: gateway indexing or scripts/backfill_sessions_search.py" >&2
  exit 2
fi

if [[ ! -f "${BASELINE}" ]]; then
  echo "run_evolution_eval: missing baseline ${BASELINE}" >&2
  exit 2
fi

mkdir -p "${OUT_DIR}"

echo "=== IEVO-04 memory retrieval benchmark ==="
echo "home=${MIMIR_AETHER_HOME}"
echo "like_db=${LIKE_DB}"
echo "out=${OUT_JSON}"

"${PYTHON_BIN}" "${ROOT}/scripts/run_memory_retrieval_benchmark.py" --json-out "${OUT_JSON}"
cp -f "${OUT_JSON}" "${LATEST_JSON}"
chmod 644 "${OUT_JSON}" "${LATEST_JSON}" 2>/dev/null || true
echo "latest=${LATEST_JSON}"

if [[ "${SKIP_COMPARE}" -eq 1 ]]; then
  echo "=== skip-compare: done ==="
  exit 0
fi

echo "=== compare vs baseline ${BASELINE} ==="
"${PYTHON_BIN}" "${ROOT}/scripts/compare_memory_retrieval_baseline.py" \
  "${OUT_JSON}" \
  --baseline "${BASELINE}" \
  --json-out "${COMPARE_JSON}"
RC=$?
echo "compare_json=${COMPARE_JSON}"
exit "${RC}"
