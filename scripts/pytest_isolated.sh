#!/usr/bin/env bash
# pytest_isolated.sh — 让 pytest 跑在**独立 cgroup**，保护 gateway 的 4G 限额
#
# 事故背景（2026-09-27 22:49:50）：在 gateway 自己的 cgroup 内跑整仓 pytest
#   （1365 用例 · 872s · 内存峰值 4.0G）⇒ cgroup OOM ⇒ **主进程被 SIGKILL**。
#   该次死法在退出表里为 0 行（SIGKILL 不可捕获），只能靠 journal 记账定因。
#
# 用法：
#   bash scripts/ pytest_isolated.sh                  # 跑整仓 tests@
#   bash scripts/ pytest_isolated.sh tests/tools -q   # 透传给 pytest
#   bash scripts/ pytest_isolated.sh --tier0          # 跑仓根 run_ralph_tier0.sh
#
# 可调：MIMIR_PYTEST_MEM_MAX（默认 6G） · MIMIR_PYTEST_TASKS_MAX（默认 1024）
#       MIMIR_TIER0_PYTHON（解释器，默认 .venv/bin/python3）
#
# 判据（自证）：输出 `[isolated] cgroup=` **不含** mimiraether.service，
#   且 gateway 的 MemoryCurrent 跑测前后不明显增长。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MEM_MAX="${MIMIR_PYTEST_MEM_MAX:-6G}"
TASKS_MAX="${MIMIR_PYTEST_TASKS_MAX:-1024}"

PY="${MIMIR_TIER0_PYTHON:-$ROOT_DIR/.venv/bin/python3}"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3 || echo python3)"; fi

me_cg() { cut -d: -f3 /proc/self/cgroup 2>/dev/null || echo ""; }
gw_mem() {
  local v
  v="$(systemctl --user show mimiraether -p MemoryCurrent --value 2>/dev/null || echo "")"
  if [[ -z "$v" || "$v" == "[not set]" ]]; then echo "n/a"; else echo "$((v / 1048576))M"; fi
}

CG="$(me_cg)"
echo "[isolated] cgroup=${CG:-unknown}"
echo "[isolated] gateway MemoryCurrent(前)=$(gw_mem)"

# ---- 在 gateway cgroup 内 ⇒ 经 systemd-run 脱离后再跑（一次性重入）----
if [[ "${MIMIR_PYTEST_ISOLATED:-}" != "1" ]]; then
  if [[ "$CG" == *mimiraether.service* ]]; then
    if ! command -v systemd-run >/dev/null 2>&1; then
      echo "[isolated] 致命：在 gateway cgroup 内且无 systemd-run ⇒ 拒绝以该状态跑重测试" >&2
      echo "           （不修则整仓 pytest 会再次 OOM 掉主进程；2026-09-27 已发生一次）" >&2
      exit 97
    fi
    UNIT="mimir-pytest-$(date +%Y%m%d-%H%M%S)"
    echo "[isolated] 在 gateway cgroup 内 ⇒ systemd-run --user --scope 脱离（unit=${UNIT}, MemoryMax=${MEM_MAX}）"
    exec systemd-run --user --scope --collect --quiet \
      --unit="$UNIT" \
      -p MemoryMax="$MEM_MAX" \
      -p MemorySwapMax=0 \
      -p TasksMax="$TASKS_MAX" \
      env MIMIR_PYTEST_ISOLATED=1 HOME="$HOME" PATH="$PATH" \
      bash "$0" "$@"
  fi
  echo "[isolated] 已在 gateway cgroup 之外，无需脱离"
fi

# ---- 真正执行 ----
if [[ "${1:-}" == "--tier0" ]]; then
  shift
  echo "[isolated] 模式=tier0（run_ralph_tier0.sh）"
  bash "$ROOT_DIR/run_ralph_tier0.sh" "$@"
  rc=$?
else
  if [[ $# -eq 0 ]]; then set -- tests/; fi
  echo "[isolated] 模式=pytest · 解释器=$PY · 参数=$*"
  "$PY" -m pytest "$@"
  rc=$?
fi

echo "[isolated] cgroup(后)=$(me_cg)"
echo "[isolated] gateway MemoryCurrent(后)=$(gw_mem)"
exit "$rc"
