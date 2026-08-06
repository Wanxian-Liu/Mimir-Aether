#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# wm-kpi-verify.sh — 世界模型 KPI 验证脚本（WM 存废讨论共识产物, 2026-08-03）
#
# 背景: surprise 流已停用（MIMIR_WM_*=0），代码/数据归档至
#       docs/archive/world-model-20260803/。本脚本提供 3 个 KPI 指标，
#       用于未来决定是否重启/迭代世界模型时的量化依据。
#
# 3 个 KPI:
#   KPI-1  预测工具采用率 (adoption rate): 预测的工具被实际采用的比例
#          → 闭环率。目标 ≥30%，否则预测器无实用价值
#   KPI-2  outcome reversal / 月: 真实学习事件（预期成功实际失败）频率
#          → 学习价值。历史值: 2 个月仅 1-2 次（近零）
#   KPI-3  行为改变计数: surprise 触发实际行为变化的次数
#          → 效用。历史值: 0（从未转化为行为）
#
# 数据源: 归档的 surprise_events.jsonl（只读，不修改）
# 用法:   scripts/wm-kpi-verify.sh [归档目录路径]
# 默认:   docs/archive/world-model-20260803/surprise_events.jsonl
# ═══════════════════════════════════════════════════════════════════════════════

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ARCHIVE_DIR="${1:-$REPO_ROOT/docs/archive/world-model-20260803}"
SURPRISE_FILE="$ARCHIVE_DIR/surprise_events.jsonl"

echo "════════════════════════════════════════════════════════"
echo " WM KPI 验证 — $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "════════════════════════════════════════════════════════"

# ── 前置检查 ────────────────────────────────────────────────
if [[ ! -f "$SURPRISE_FILE" ]]; then
    echo "❌ surprise_events.jsonl 不存在: $SURPRISE_FILE"
    echo "   （数据已归档或从未生成——surprise 流处于停用状态）"
    exit 2
fi

TOTAL=$(wc -l < "$SURPRISE_FILE")
echo ""
echo "数据源: $SURPRISE_FILE"
echo "总事件数: $TOTAL"

# ── KPI-1: 预测工具采用率 ──────────────────────────────────
# surprise 事件里 expected(预测工具名) ∩ actual(实际工具名) / expected
# 说明: 停用前的历史数据本身是"预测不准"的记录，采用率=1-误报占比。
# 事件 schema: {expected: 工具名文本, actual: 工具名文本, surprise_label, ...}
KPI1=$(python3 - "$SURPRISE_FILE" <<'PYEOF'
import json, sys
path = sys.argv[1]
hits = 0
total = 0
examples = []
with open(path) as f:
    for line in f:
        try:
            ev = json.loads(line)
        except Exception:
            continue
        exp = (ev.get("expected") or "").strip()
        act = (ev.get("actual") or "").strip()
        if not exp or not act:
            continue
        # 工具名比较（忽略大小写/空格）
        exp_l = exp.lower().replace(" ", "")
        act_l = act.lower().replace(" ", "")
        # 排除非工具名的事件（如 "operation success" 这类语义描述）
        if any(x in exp_l for x in ("success", "fail", "operation", "should", "expect")):
            continue
        total += 1
        if exp_l == act_l or exp_l in act_l or act_l in exp_l:
            hits += 1
        elif len(examples) < 3:
            examples.append(f"{exp}→{act}")
if total == 0:
    print("N/A (无工具名事件可统计)")
else:
    print(f"{hits}/{total} = {hits/total*100:.1f}%  [例: {' | '.join(examples) if examples else '无'}]")
PYEOF
)
echo ""
echo "── KPI-1  预测工具采用率 (adoption rate) ──────────────"
echo "   预测∩实际 / 预测总数 = $KPI1"
echo "   目标: ≥30%  判定: $([ "${KPI1%%/*}" = "N/A" ] && echo 'N/A(停用中)' || awk -v k="$KPI1" 'BEGIN{split(k,a,"/"); split(a[1],b," "); ok=(a[2]>0 && b[1]/a[2]>=0.30); print (ok?"✅ PASS":"❌ FAIL (低于30%: 预测器无实用价值)")}')"

# ── KPI-2: outcome reversal 事件数 ─────────────────────────
KPI2=$(python3 - "$SURPRISE_FILE" <<'PYEOF'
import json, sys
path = sys.argv[1]
count = 0
first_ts = None
last_ts = None
with open(path) as f:
    for line in f:
        try:
            ev = json.loads(line)
        except Exception:
            continue
        label = (ev.get("surprise_label") or ev.get("label") or "").lower()
        msg = (ev.get("message") or ev.get("surprise_message") or "").lower()
        if "outcome_reversal" in label or "outcome reversal" in label or "outcome reversal" in msg:
            count += 1
            ts = ev.get("timestamp") or ev.get("ts")
            if ts:
                if not first_ts: first_ts = ts
                last_ts = ts
print(f"{count} (首条: {first_ts or 'N/A'}, 末条: {last_ts or 'N/A'})")
PYEOF
)
echo ""
echo "── KPI-2  outcome reversal / 观察期 ───────────────────"
echo "   $KPI2"
echo "   历史基线: 2 个月仅 1-2 次 → 学习价值近零"

# ── KPI-3: 行为改变计数 ────────────────────────────────────
KPI3=$(python3 - "$SURPRISE_FILE" <<'PYEOF'
import json, sys
path = sys.argv[1]
count = 0
with open(path) as f:
    for line in f:
        try:
            ev = json.loads(line)
        except Exception:
            continue
        # 行为改变 = 事件里有 action_taken / behavior_change / corrective_action 等字段且非空
        for key in ("action_taken", "behavior_change", "corrective_action", "replan_triggered", "self_heal_applied"):
            v = ev.get(key)
            if v and v not in (False, None, "", [], {}):
                count += 1
                break
print(count)
PYEOF
)
echo ""
echo "── KPI-3  行为改变计数 ────────────────────────────────"
echo "   $KPI3 次 (surprise 触发实际行为变化)"
echo "   历史基线: 0 → 从未转化为行为"

echo ""
echo "════════════════════════════════════════════════════════"
echo " 结论指引:"
echo "   KPI-1 <30% 或 KPI-2 每月 <1 或 KPI-3 =0 → 维持停用状态"
echo "   若未来重启预测器，用本脚本做环比（停用前基线已存档）"
echo "════════════════════════════════════════════════════════"
