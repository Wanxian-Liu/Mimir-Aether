# [DORMANT] mimiraether-buzz-inbox-wake

**沉寂时间**: 2026-11-21T06:40:45.305433+00:00
**原始分类**: mimiraether
**描述**: 处理「自动唤醒·Buzz 收件箱」新行：判定需行动/纯通知、并发唤起去重、原子追加 inbox-processed.log、讨论卡段追加 + notes 索引维护 + 双仓 commit。触发词：自动唤醒/Buzz收件箱/processed N lines (up to M)。
**触发阈值**: 60天未触碰

---

## 技能要点

## 2.40 「同席并行双写」：动手前先查卡内是否已有本席段（2026-10-19 行 249 实证 · 本族第二十一 run）

**场景**：唤醒称「第 250 到 250 行」（单行），实读真新 = 账本 `up to 244` 之后的 **245-251**（7 行）；其中行 249 = `kind=1` `from=hermes`「Mimir 全面审计·被审方 DBRE」派单。

**踩坑（本轮实犯）**：同一派单**已有另一 run 在写**（同卡 `## 八、Mimir 回段` + `【END-MIMIR-DBRE】` 哨兵，先我数分钟 commit）。我未察，另起 `## Mimir（被审方 …）` 段 ⇒ 卡内同席**两段并存**；且我早段的「`record_pending_delete` 唯一生产调用点 = orphan_scan」断言**错**——grep 面只写了 `agent/ tools/ scripts`，真调用点在**仓库根** `mimir_state.py:1032`。

**三条前置判据（写卡前必跑，一条不过先别写）**：

1. **同席段是否已在**：`grep -n '^## .*[Mm]imir\|^### mimir\|END-MIMIR' <卡>` —— 命中即已有本席段，**改为该段内 patch 追加**，禁新开段。
2. **哨兵之后不写**：`【END-<seat>】` 之后**禁**追加（破坏派单方结束语义）；要补就插在哨兵**之前**。
3. **grep 面必须含仓库根**：`grep -rn --include=*.py <符号> agent tools scripts .`——缺 `.` 会漏根目录大件（`mimir_state.py` / `gateway/run.py`），**本轮假断言的唯一成因**。

**去重收口（已犯之后的修法）**：删自己那段（`MIMIR_ALLOW_SECTION_DELETE=1 git commit`，只允许删**本席**重复段，删他席禁），保留他 run 更精确的结论；把自己**唯一新增读数**（本轮 = 入口契约负控：`resume_pending_indexes(like_db=<Path>)` 静默 `{"error":"like_db has no db_path"}` 且 pending 不清）以一行插进已有段哨兵**之前**。

**另记（机制读数）**：空跑闸只认 `write_file`/`patch` 落到**交付面**（`~/wiki/discussions`、`~/.hermes/inbox`）——写 `~/.mimiraether/tmp/**` **不解闸**（本轮连报 6 次）；`terminal` 里 `cat >> <卡>` 也**不算**写（闸仍判只读）⇒ 落盘一律用 `patch`。

# Buzz 收件箱唤醒处理（Mimir）

## 2.39 「kind=1 派单型唤醒 · 交付物已在原会话闭环」⇒ `handled-elsewhere`：判据锚「交付物 mtime > 派单 ts」（2026-10-13 行 196-197 实证 · 本族第二十 run）

**场景**：唤醒称「197 条新消息（第 1 到 197 行）」= **全量误报**（行号跨纪元累计）；账本末条 `up to 195` ⇒ 真新只有 196-197。两行 = `kind=1` · `from=hermes` 派单（四方会议·审计轮审 loki / 面 A 离线影子实验审计），**均已在原会话闭环**（卡段 + 回执在盘）。

**四条结构判据（不读 payload 措辞）**：

1. **真新行数 = 账本 `up to M` 之后**：按 `logs/inbox-processed.log` 末条起算，**不是**唤醒里的 `1..N`（§8 游标同纪元——行号跨纪元累计 ⇒ 唤醒全量必然误报）。
2. **交付物双证在盘**：卡段（段标题原文 + `grep -c '^### mimir'` 计数）**∧** 回执文件存在。
3. **时序（不可省）**：回执 mtime **>** 派单 ts——本轮 196: `01:32:52 > 01:25:13`（+7m39s）· 197: `02:07:39 > 02:00:47`（+6m52s）⇒ 断裂面为空。**只看「文件存在」不够**（旧同名件会假过）。
4. **两字段**：两回执 `重跑命令:` / `复算数字:` / `冒烟档位:` 各 ≥1。

**处置 = 零动作 + 判定件 + 日志行**（不重做、不投箱——再投一次 = 亲手复现噪音

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-buzz-inbox-wake")` 即可自动唤醒。
