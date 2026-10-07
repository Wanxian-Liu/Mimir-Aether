#!/usr/bin/env bash
# Q6-2 文档/技能写死阈值数字扫描 —— **出声不阻断**（2026-10-07 · A6 后续 Q6 落地 · 刘哥批）
#
# 来源（口径不是我发明的）：A6 压缩闭环审计会 Q6-2（OpenClaw 妹妹出的 grep）：
#   grep -rnE '(300000|350000|120000|80000|30万|12万)' <repo>/skills <repo>/docs
# 语义：写死数字 != 立刻错——它是**分叉源**（数字写死 = 必然过期 ⇒ 阈值又变成两个真源，A6 根因）。
#   ⇒ 只要求「可见」，不阻断任何既有门禁（本脚本恒 rc=0；无命中/有命中都算跑完）。
# 处置（人工/技能侧）：把写死的数字换成「怎么查现值」的命令：
#   bash /home/rayliu/.mimiraether/scripts/threshold_ledger_check.sh
# 退出码：0 = 扫描跑完 · 2 = 仪表故障（扫描面全不存在——刻意与「无命中」区分，防假绿）
set -u
REPO_SCAN="${REPO_SCAN:-/home/rayliu/src/MimirAether}"
# 两条分离（2026-10-07 实测修）：数字版本必须带 \b 词界——否则 120000 会命中 1200000、
#   80000 会命中 1800000/480000（本机实测：mlops 技能文档 3 处此类假阳性）。
#   中文版本（30万/12万…）不能带尾 \b：万 非 ASCII 词字符，尾 \b 会恒不匹配。
NUM_PATTERN='\b(300000|350000|120000|80000|200000|300000|200_000|300_000)\b'
CJK_PATTERN='(30万|35万|12万|20万|8万)'
SURFACES=("$REPO_SCAN/skills" "$REPO_SCAN/docs")

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
found=0
for d in "${SURFACES[@]}"; do
  [ -d "$d" ] || continue
  found=1
  grep -rnE -I -- "$NUM_PATTERN" "$d" 2>/dev/null >> "$TMP" || true
  grep -rnE -I -- "$CJK_PATTERN" "$d" 2>/dev/null >> "$TMP" || true
done
if [ "$found" = "0" ]; then
  echo "[阈值写死扫描 · Q6-2] 仪表故障: 扫描面全不存在 (${SURFACES[*]})"
  exit 2
fi
HITS=$(wc -l < "$TMP" | tr -d ' ')
echo "[阈值写死扫描 · Q6-2] 命中 ${HITS} 处写死阈值数字（出声不阻断）· 面: ${SURFACES[*]}"
if [ "$HITS" -gt 0 ]; then
  head -8 "$TMP" | sed 's/^/  · /'
  [ "$HITS" -gt 8 ] && echo "  · …（余 $((HITS-8)) 处）"
  echo "  处置: 写死数字=分叉源 ⇒ 改成查现值: bash /home/rayliu/.mimiraether/scripts/threshold_ledger_check.sh"
fi
exit 0
