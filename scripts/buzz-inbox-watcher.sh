#!/bin/bash
# Mimir Buzz收件箱增量唤醒——零token预扫描
# 原理: 行数 > 已处理游标(offset) → 有新消息 → POST /v1/runs 唤醒 → 派发成功推进 dispatched
# 无新消息 → 静默退出(零消耗)
# 修复问题池P0-2「webhook盲区: 刘哥不说话=Mimir永远不醒」——最后一公里(收件箱→运行)

# 2026-10-08 修（同类风险全量扫 · 入仓前清理）：默认值改 $HOME 相对，本地恒等。
OPENCLAW_DATA="${OPENCLAW_DATA:-$HOME/.openclaw/data}"
INBOX="${BUZZ_INBOX_MIMIR:-$OPENCLAW_DATA/buzz-inbox-mimir.jsonl}"
OFFSET_FILE="${BUZZ_INBOX_MIMIR_OFFSET:-$OPENCLAW_DATA/buzz-inbox-mimir.offset}"
LOCK="${BUZZ_INBOX_MIMIR_LOCK:-$OPENCLAW_DATA/buzz-inbox-mimir.waking}"
DISPATCHED_FILE="${BUZZ_INBOX_MIMIR_DISPATCHED:-$OPENCLAW_DATA/buzz-inbox-mimir.dispatched}"
# 2026-09-08 D4收件箱统一（四方审计卡）：从 ~/.buzz-nostr/state/ 迁至 ~/.openclaw/data/（四方唯一目录）
# 迁移逻辑：若新路径不存在且旧路径存在 → 合并旧文件内容到新路径（保历史·offset同名迁移）
GATEWAY="${MIMIR_GATEWAY_URL:-http://127.0.0.1:18999}"  # 可覆写：测试指向死端口以免真实派发

# 收件箱不存在=从没收到过消息 → 静默
[ -f "$INBOX" ] || exit 0

# 防重入: 上一轮唤醒还没跑完(锁<30min) → 不重复触发
if [ -f "$LOCK" ]; then
    lock_age=$(( $(date +%s) - $(stat -c %Y "$LOCK") ))
    [ $lock_age -lt 1800 ] && exit 0
    rm -f "$LOCK"  # 超30min视为死锁,清掉继续
fi

total=$(wc -l < "$INBOX")
[ -f "$OFFSET_FILE" ] && offset=$(cat "$OFFSET_FILE") || offset=0
[ -z "$offset" ] && offset=0
d_old=0
[ -f "$DISPATCHED_FILE" ] && d_old=$(cat "$DISPATCHED_FILE" 2>/dev/null || echo 0)
[ -z "$d_old" ] && d_old=0

# -- 轮转/截断检测（2026-10-06 23:26 实证：收件箱被裁剪归档 ⇒ 行号纪元重置）--
# 旧游标 > 新总行数时，任何「旧值 >= total」比较恒真 ⇒ 派发门控永久关闭（静默不唤醒）。
# 判据: total < max(offset,dispatched) ⇒ 视为新纪元，双游标归零并出声。
# 取向: 宁可一次重复处理，不可静默丢信（重复可去重，静默丢信无人知）。
max_old=$offset
[ "$d_old" -gt "$max_old" ] && max_old=$d_old
if [ "$total" -lt "$max_old" ]; then
    echo "$(date '+%F %T') ROTATION/TRUNCATION: total $total < max(offset=$offset, dispatched=$d_old)=$max_old ⇒ 行号纪元重置，双游标归零"
    echo 0 > "$OFFSET_FILE"
    echo 0 > "$DISPATCHED_FILE"
    offset=0
    d_old=0
fi

# 无增量 → 静默
[ "$total" -le "$offset" ] && exit 0

# ── RS2① 派发前查账（U15 账本级幂等 · 四方裁决 2026-09-13）─────────────────
# 治 INC-10：watcher 只看 offset，不看「已处理到哪」⇒ 同批新行被重复派发。
# 判据取账本**最后一次** `up to N`（非 grep -c 计数），N >= total 即视为已处理。
LEDGER="${BUZZ_INBOX_MIMIR_LEDGER:-${MIMIR_AETHER_HOME:-$HOME/.mimiraether}/logs/inbox-processed.log}"
LEDGER_HWM="${LEDGER}.hwm"
DEGRADE_MARK=""
if [ -f "$LEDGER" ]; then
    ledger_last=$(grep -ao 'up to [0-9][0-9]*' "$LEDGER" | tail -1 | grep -o '[0-9][0-9]*')
    ledger_lines=$(wc -l < "$LEDGER")
    hwm=0
    [ -f "$LEDGER_HWM" ] && hwm=$(cat "$LEDGER_HWM" 2>/dev/null || echo 0)
    [ -z "$hwm" ] && hwm=0
    if [ "$ledger_lines" -gt "$hwm" ]; then
        echo "$ledger_lines" > "$LEDGER_HWM" 2>/dev/null || true
    elif [ "$hwm" -gt 10 ] && [ "$ledger_lines" -lt $(( hwm / 2 )) ]; then
        echo "$(date '+%F %T') 账本损坏(fail-closed): 行数 $ledger_lines 低于高水位 $hwm 一半, 暂停派发等人工"
        exit 3
    fi
    # 2026-10-07 修: 原门控用「账本最后 up to N >= total」。账本编号是**跨纪元累计**
    # （旧收件箱 2026-10-06 23:26 被轮转归档后仍递增，实测 234 vs total 34）⇒ 该比较恒真
    # ⇒ 门控永久关闭、watcher 自动唤醒静默死。改判: 用**同纪元**的 dispatched 游标。
    if [ "$d_old" -ge "$total" ] && [ "$total" -gt 0 ]; then
        echo "$(date '+%F %T') 已派发到 dispatched=$d_old >= total $total → 不重复派发"
        exit 0
    fi
else
    # 降级放行：自主唤醒通路不得因账本缺失而整体停摆（P0-2 立项初衷）；
    # 重复派发由 run 侧语义去重兜底（INC-10 实证）。同流写可见标记行供度量窗计数。
    DEGRADE_MARK=" [降级: 未经账本去重]"
    echo "$(date '+%F %T') DEGRADED dispatch (ledger missing: $LEDGER, dedup not applied)" >> "$LEDGER" 2>/dev/null || true
fi

# ── T7-F1 原子认领（2026-10-07）：同一行只能被一个 run 取到 ─────────────────
# 治 TOCTOU：原「读三游标 → 决策 → POST → 写 dispatched」之间无互斥，两个消费者
# 可同时取到同一行（2026-10-07 02:44/02:45 实证：api run 9f313cb9 与 watcher run
# 5ee412bb 并行消费同一派单行 ⇒ 算力双付）。认领 = flock 关键区内 read+比对+原子写回。
# 2026-10-08 修（CI Only-Red 根因）：不再写死家目录；与 gateway/inbox_claim_gate.py
# 的 _home() 制对齐 —— 两侧须指向同一认领器，路径由 MIMIR_AETHER_HOME 单一控制。
MIMIR_HOME_DIR="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
CLAIM_TOOL="${BUZZ_INBOX_MIMIR_CLAIM_TOOL:-$MIMIR_HOME_DIR/scripts/buzz_inbox_claim.py}"
OWNER="watcher-$$-$(date +%s)"
CLAIM_RC=99
if [ -f "$CLAIM_TOOL" ]; then
    claim_out=$(python3 "$CLAIM_TOOL" reserve --owner "$OWNER" 2>&1); CLAIM_RC=$?
    case $CLAIM_RC in
        0)  # 认领成功：区间以认领器为准（dispatched 已在关键区内原子推进）
            c_start=$(printf '%s\n' "$claim_out" | awk '/^CLAIMED/ {print $3; exit}')
            c_end=$(printf '%s\n' "$claim_out" | awk '/^CLAIMED/ {print $4; exit}')
            if [ -n "$c_start" ] && [ -n "$c_end" ]; then offset=$(( c_start - 1 )); total=$c_end; fi
            ;;
        1)  exit 0 ;;   # 无增量 → 静默（零 token 预扫描语义保持）
        2)  echo "$(date '+%F %T') 认领被他人持有(HELD) ⇒ 不重复派发: ${claim_out:0:160}"; exit 0 ;;
        *)  echo "$(date '+%F %T') 认领失败 rc=$CLAIM_RC ⇒ 降级旧路径（无原子认领）: ${claim_out:0:160}"; CLAIM_RC=99 ;;
    esac
else
    echo "$(date '+%F %T') 认领器缺失($CLAIM_TOOL) ⇒ 降级旧路径（无原子认领，重复派发风险）"
fi

new_count=$(( total - offset ))

# 唤醒Mimir: 处理收件箱新消息(offset+1 到 total)
resp=$(curl -s -m 10 -X POST "$GATEWAY/v1/runs" \
    -H "Content-Type: application/json" \
    -d "{\"input\": \"【自动唤醒】Buzz收件箱有 ${new_count} 条新消息${DEGRADE_MARK}(第 $((offset+1)) 到 ${total} 行)。【B5段界】本段一段一任务·每段≤60 步：到 60 步或轮次 80% 仍未落盘 ⇒ 先落半段（骨架+已确证+未闭项清单）再交棒，不得跑到轮次顶才产出。请读取 $INBOX 的新消息并处理: 需要行动的执行(四方接棒/查证/落盘), 纯通知的跳过。处理完成后在 ~/.mimiraether/logs/inbox-processed.log 追加一行: $(date '+%F %T') processed $new_count lines (up to $total)。\", \"metadata\": {\"source\": \"buzz-inbox-watcher\", \"segment_policy\": \"B5: one-task-per-segment,<=60 turns,flush-half-segment\"}}")

# 202/200 = 接受 → 推进offset+落锁防重入
if echo "$resp" | grep -qE '"(status)":\s*"(started|running|completed)"'; then
    echo "$total" > "$DISPATCHED_FILE"   # 派发游标；offset 由 run 侧 buzz_inbox_close.py 闭环推进
    date +%s > "$LOCK"
    # 认领落地（清 per-run claim 记录 + 台账行）；失败不致命，认领仍由 dispatched 兜底
    [ "$CLAIM_RC" = 0 ] && python3 "$CLAIM_TOOL" commit --owner "$OWNER" >/dev/null 2>&1
    echo "$(date '+%F %T') 唤醒成功: ${new_count}条新消息 → Mimir (dispatched $d_old→$total; offset 待 run 侧闭环)"
else
    # 派发失败 ⇒ 回滚认领（仅当无人推进时），使下一次 watcher 能重试；禁静默丢信
    if [ "$CLAIM_RC" = 0 ]; then
        rb=$(python3 "$CLAIM_TOOL" abort --owner "$OWNER" 2>&1)
        echo "$(date '+%F %T') 认领回滚: ${rb:0:160}"
    fi
    echo "$(date '+%F %T') 唤醒失败(gateway未接受), offset不推进下次重试: ${resp:0:120}"
fi
