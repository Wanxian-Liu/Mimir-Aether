#!/usr/bin/env bash
# pi-env-audit.sh — pi 扩展环境三口径对照审计
# 防止"查错包名→结论不存在"事故重演（2026-08-02 PiCrew 教训）
#
# 用法: ./pi-env-audit.sh [package-name]   默认 pi-crew
# 三口径:
#   1. 注册  pi list                       （settings.json 注册表）
#   2. 安装  ls ~/.pi/agent/npm/node_modules/<pkg>  （磁盘实际存在）
#   3. 真名  npm view <pkg> version        （npm registry，须用真名）
# 铁律: 任一口径不一致 = 需调查，禁止直接下"不存在/未安装"结论。
set -uo pipefail

PKG="${1:-pi-crew}"
PI_BIN="${PI_BIN:-/home/rayliu/.bun/bin/pi}"
NODE_MODULES="${HOME}/.pi/agent/npm/node_modules"

echo "=== pi 环境三口径审计: ${PKG} ==="
echo "时间: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo

# ── 口径1: 注册（pi list / settings.json）──
if "${PI_BIN}" list 2>/dev/null | grep -q "${PKG}"; then
  REG="已注册"
  REG_DETAIL=$("${PI_BIN}" list 2>/dev/null | grep "${PKG}" | head -1 | tr -s ' ')
else
  REG="未注册"
  REG_DETAIL="pi list 无 ${PKG} → 需执行 pi install npm:${PKG}"
fi

# ── 口径2: 安装（node_modules 磁盘存在）──
if [ -d "${NODE_MODULES}/${PKG}" ]; then
  INST="已安装"
  VER=$(grep '"version"' "${NODE_MODULES}/${PKG}/package.json" 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  MTIME=$(stat -c '%y' "${NODE_MODULES}/${PKG}" 2>/dev/null | cut -d'.' -f1)
  INST_DETAIL="v${VER:-?} @ ${MTIME}"
else
  INST="未安装"
  INST_DETAIL="ls ${NODE_MODULES}/${PKG} 不存在"
fi

# ── 口径3: registry 真名（npm view）──
REG_VER=$(npm view "${PKG}" version 2>/dev/null)
if [ -n "${REG_VER}" ]; then
  REGISTRY="registry 有"
  REGISTRY_DETAIL="npm view ${PKG} → v${REG_VER}"
else
  REGISTRY="registry 无"
  REGISTRY_DETAIL="npm view ${PKG} → 404（可能查错名！用 npm search ${PKG} 找真名，勿直接下'不存在'结论）"
fi

# ── 输出对照表 ──
printf '%-16s %-10s %s\n' "口径" "状态" "详情"
printf '%-16s %-10s %s\n' "----------------" "----------" "------------------------------------------"
printf '%-16s %-10s %s\n' "① 注册 pi list"  "${REG}"       "${REG_DETAIL}"
printf '%-16s %-10s %s\n' "② 安装 node_modules" "${INST}"  "${INST_DETAIL}"
printf '%-16s %-10s %s\n' "③ registry npm view" "${REGISTRY}" "${REGISTRY_DETAIL}"

echo
# ── 综合判定 ──
OK="已注册 已安装 registry 有"
STATE="${REG} ${INST} ${REGISTRY}"
if [ "${STATE}" = "${OK}" ]; then
  echo "判定: ✅ 三口径一致 — ${PKG} 完全就绪"
  exit 0
else
  echo "判定: ⚠ 口径不一致 — ${PKG} 未完全就绪（不一致=需调查，禁止下'不存在'结论）"
  exit 1
fi
