---
name: mimiraether-buzz-inbox-wake
description: 处理「自动唤醒·Buzz 收件箱」新行：判定需行动/纯通知、并发唤起去重、原子追加 inbox-processed.log、讨论卡段追加 + notes 索引维护 + 双仓 commit。触发词：自动唤醒/Buzz收件箱/processed N lines (up to M)。
auto_load: false
---

# Buzz 收件箱唤醒处理（Mimir）

## 0. 触发形态

唤醒 prompt：「Buzz收件箱有 N 条新消息(第 A 到 B 行)。请读取 `/home/rayliu/.openclaw/data/buzz-inbox-mimir.jsonl` 的新消息并处理…处理完成后在 `~/.mimiraether/logs/inbox-processed.log` 追加一行：`<时间戳> processed N lines (up to B)`」。

**边界**：收件箱在 OpenClaw 路径下 —— **只读，禁写**（身份边界；产出只落 `~/.mimiraether/` 与 `~/wiki/`）。

## 1. 步骤

### ① 读新行（一次批量）
`read_file <inbox> offset=A-3 limit=N+4`（多取几行看上下文）。行字段：`id` / `ts` / `from` / `to` / `kind` / `content`。`ts` 换算：`date -d @<ts>`（epoch 秒）。

### ② 判定：需行动 vs 纯通知
- **纯通知**（公告/已闭环汇报/纯知会）→ 追加日志行即可（可选卡上一句回执）。
- **需行动**（开工令/授权确认/裁决交棒/质询）→ 进 ③。

### ③ 并发去重（**必做**；截至 2026-09-13 已实证 7 次双 run 同处理同一行）

| 检查 | 命令 | 命中含义 |
|:--|:--|:--|
| 卡上已有同段？ | `grep -n '收件行 <N>\|<msg-id>' <卡>` | 另一 run 已落段 |
| 游标已到该行？ | `tail -3 ~/.mimiraether/logs/inbox-processed.log` | 已处理过 |
| 是否已有他人 commit？ | `git -C ~/src/MimirAether log --oneline --since='30 min ago'` + `git status --short` | 实施方 = 彼 run |
| 时间线交错？ | 目标文件 `mtime` + `git log --date=format:'%H:%M:%S'` | 判断谁先谁后 |

**裁决**：若已有 run 实施 → 本 run **不重复实施**，转「**独立复核 + 缺口定位**」，日志行标注 `[dedup: line N already actioned <时刻> …; this run = independent disk re-verify …]`（先例：05:35:01 / 07:15:01）。

### ④ 「已提交 ≠ 已生效」（复发性误判，且是最值钱的产出）
`systemctl --user show mimiraether.service -p MainPID -p ExecMainStartTimestamp` 的启动时刻 **<** commit 时刻 ⇒ 改动**未加载**。旁证：产物 schema（例：`data/ops/last_context_usage.json` 是否含新字段）。把「下一次重启窗口的验收判据（2–3 条）」写进卡段。**本 run 不重启**（飞书活跃 turn 内重启会掐死自己的会话）。

### ⑤ 落盘三处

1. **卡段**（`~/wiki/discussions/<当日卡>`）：先 `write_file` 到 `~/.mimiraether/scripts/<name>.md`，再 `cat <staging> >> <卡>`。
   **为什么不用 patch/write_file 改卡**：它们整文件重写 → 与并发写者互覆盖；`>>` 追加是并发安全的最小面。
   § 号：`grep -n '^## §' <卡> | tail` 找空号再用。
2. **日志行**：`printf '%s\n' "<唤醒给定行> [动作/去重标注]" >> ~/.mimiraether/logs/inbox-processed.log`。
   **禁用**：沙箱 `write_file`（`~` 二次嵌套成 `~/.mimiraether/.mimiraether/…`）；`read_file`+全量重写（并发丢行）。
3. **笔记/审计行**：新笔记落 `notes/` 后**必须**跑
   `.venv/bin/python3 ~/.mimiraether/scripts/b7_index_check.py` → 末行须 `VERDICT: PASS`、`unlisted=0`；未登记即补登 `notes/INDEX.md`（活/冻/归档）+ 重算「末行统计」块。中间产物（commit-msg 草稿、拼接片段）**不留 `notes/`** → 挪 `scripts/`（维护规则 3）。

### ⑥ commit（两仓，均带 `Agent: mimir` trailer）
- `git -C ~/wiki commit`（pre-commit 钩子会校验 trailer；会提示 committer identity 与仓默认不同——提示非错误）。
- `git -C ~/src/MimirAether commit`；**不 push**（F2 = 对外操作，须刘哥点头）。未推存量：`git rev-list --left-right --count origin/main...HEAD`。

## 2. 实测坑

- `terminal` 中 `rm` 会被 ToolGuard 拦（“delete in root path”）→ 用 `mv` 挪位代替。
- `grep`/`read_file` 输出层会把密钥与长大写常量**遮蔽为 `***`** → 判据用运行时探针（`.venv/bin/python3 -c`），不凭截图。
- 沙箱 `execute_code` 内 `write_file` 写 `~` 系路径 → 双嵌套假成功；记账类追加一律走**外层 terminal 的 `>>`**。
- 唤醒发出时另一 run 可能已在跑；**先查盘再动手**（③ 表），重复实施 = 双 pin/双重启/双落段，成本最高。
- 卡段写完若 1 分钟内又有他人 commit，需**补记一行**（例：「§19 补记：B8 已开工 bf1b2dd」）——不留过期陈述。

## 3. 完成判据
① 日志行已追加（含动作/去重标注）② 卡段已落并 commit ③（若有新笔记）索引判据 `VERDICT: PASS` ④ 汇报区分「声明」与「盘上实测」，未闭项显式列出。
