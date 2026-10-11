#!/usr/bin/env bash
# 单一真源漂移检测（SSOT drift check）—— 只读 · 零写入
#
# 真源表：~/wiki/discussions/_单一真源总表.md §1
# 用法：bash ~/.mimiraether/scripts/check_ssot_drift.sh
# 输出：每行 `KEY=value`；末行 rc=0（全一致）/ rc=1（至少一行漂移）
#
# 判据语义（为什么这样判）：
#   - 本脚本**只报事实**（一致/不一致/缺失），**不**自动同步 —— 同步属结构决策（见总表 §5）。
#   - 「一致」= 两份内容逐字节相同；「漂移」= 都存在但不同；「缺失」= 真源不存在（P0）。
#   - 真源行取自总表 §1 的「真源根」列；派生物行取自「其余副本」列。
set -uo pipefail

HOME_DIR="${HOME:-/home/rayliu}"
MIMIR_ROOT="$HOME_DIR/.mimiraether"
REPO_ROOT="$HOME_DIR/src/MimirAether"

fail=0
emit() { printf '%s\n' "$1"; }

# 比较两文件：same / drift / missing
cmp_pair() {
  local label="$1" truth="$2" deriv="$3"
  if [ ! -e "$truth" ]; then
    emit "${label}_truth=missing"; fail=1; return
  fi
  if [ ! -e "$deriv" ]; then
    emit "${label}_deriv=missing"; fail=1; return
  fi
  if cmp -s "$truth" "$deriv"; then
    emit "${label}=same"
  else
    emit "${label}=drift"; fail=1
  fi
}

# ---- 1. SOUL.md（真源 = 数据根）----
cmp_pair "soul" "$MIMIR_ROOT/SOUL.md" "$REPO_ROOT/SOUL.md"

# ---- 2. AGENTS.md（真源 = 仓内）----
cmp_pair "agents" "$REPO_ROOT/AGENTS.md" "$MIMIR_ROOT/AGENTS.md"

# ---- 3. cron/jobs.json（真源 = 数据根；仓内是冻结残件，只报存在性）----
if [ -e "$MIMIR_ROOT/cron/jobs.json" ]; then
  emit "cron_jobs_truth=present"
else
  emit "cron_jobs_truth=missing"; fail=1
fi
if [ -e "$REPO_ROOT/cron/jobs.json" ]; then
  emit "cron_jobs_repo_stale_copy=present"
else
  emit "cron_jobs_repo_stale_copy=absent"
fi

# ---- 4. 技能目录（真源 = 仓内；只比数量，不做逐文件 diff）----
count_skills() {
  local d="$1"
  [ -d "$d" ] || { printf '0'; return; }
  find "$d" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l | tr -d ' '
}
src_n="$(count_skills "$REPO_ROOT/skills/mimiraether")"
dep_n="$(count_skills "$MIMIR_ROOT/skills/mimiraether")"
emit "skills_src_dirs=$src_n"
emit "skills_deployed_dirs=$dep_n"
if [ "$src_n" != "$dep_n" ]; then
  emit "skills=count_mismatch"; fail=1
else
  emit "skills=count_same"
fi

# ---- 5. 密钥件（安全面：只报存在性，**绝不**比较内容）----
if [ -e "$MIMIR_ROOT/.env" ]; then
  emit "env_truth=present"
else
  emit "env_truth=missing"
fi

emit "rc=$fail"
exit "$fail"
