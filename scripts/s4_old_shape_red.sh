#!/usr/bin/env bash
# S4 旧形态必红对照（twin-arm）：临时还原 **补丁前** 的 gateway/cron_mixin.py，
# 跑 S4 回归用例的两臂，期望 A 臂 FAILED（证明用例真的抓得住旧形态，不是恒绿），
# 随后**无条件**还原补丁版（trap EXIT，中途出错也还原）。
#
# 用法：bash scripts/s4_old_shape_red.sh
# 预期读数：`2 failed, 1 passed`（A 臂 = 空正文一条都不投递；E 臂 = deliver=local 时 HOME
#   收不到告警；D 臂 = 成功空正文静默，两版都过）。
# 2026-10-06 复核 #1 补：E 臂原先新旧都红（HOME 通道在用例里根本解析不出来）⇒ 放大器失效；
#   现在 HOME 走 config.yaml 源，E 臂才成为真判别器。
#
# 坑（首版踩过 · 留档）：不能用 `git show HEAD:$F` —— S4 补丁一提交，HEAD 就含补丁了，
# 于是"旧形态"跑的是补丁版 ⇒ 2 passed 全绿 = 空跑（判据假绿）。必须按内容定位引入 S4 的
# 那个 commit，再取其**父提交**版本。
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
F=gateway/cron_mixin.py
cd "$REPO" || exit 1

S4_COMMIT=$(git log --format=%H -S'S4 (2026-10-06' -- "$F" | tail -1)
if [ -z "$S4_COMMIT" ]; then
  echo "[old-shape] 找不到引入 S4 标记的 commit -- 无法构造对照臂"; exit 1
fi
echo "[old-shape] S4 引入提交 = ${S4_COMMIT:0:8}；取其父版本做对照"

BAK=$(mktemp "${TMPDIR:-/tmp}/cron_mixin.s4.XXXXXX.py")
cp "$F" "$BAK"
restore() { cp "$BAK" "$F"; rm -f "$BAK"; echo "[restore] 补丁版已还原"; }
trap restore EXIT

git show "${S4_COMMIT}^:$F" > "$F" || { echo "git show failed"; exit 1; }
echo "[old-shape] 对照版 S4 marker count: $(grep -c 'S4 (2026-10-06' "$F")  (期望 0)"

bash scripts/pytest_isolated.sh tests/gateway/test_s4_cron_failure_speaks.py -q \
  -k "failure_with_empty_body or ok_with_empty_body or deliver_local_failure" 2>&1 \
  | grep -E "FAILED|^[.F]+$|passed|failed" | tail -5
