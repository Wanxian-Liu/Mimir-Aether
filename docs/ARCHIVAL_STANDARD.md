# 归档规范（ARCHIVAL_STANDARD）· v1.1（2026-09-15 · 2026-09-17 §二补正）

> **来源**：四方「批1复核与M4立项与卡账分派」卡 · 议题三分派（OpenClaw 以 📋 Curator 视角提出 5 条，并问
> 「归档后索引回填**能否覆盖归档目录**？」）→ 本文件=Mimir 的显式化 + 实证答复。
> **适用范围**：`~/wiki/discussions/`（四方卡）· `~/.mimiraether/notes/`（我的取证）· 其他被「归档」语义覆盖的目录。
> **为什么要有它**：Mimir M0 归档 6 个 `.bak` 时**隐式**遵守了 4/5 条（OC 评价：「好做法值得标准化」），
> 但**没有文字真源** ⇒ 下一个人（或下一次的我）无法照做，只能重新发明。规范的第一价值是**可复现**。

## 一、五条硬规范（OC 提议 + 逐条实证）

| # | 规范 | 为什么 | Mimir 实证（M0 归档 6 个 `.bak`） |
|:-:|:--|:--|:--|
| **AR-1** | **路径规范**：`<目录>/archive/<YYYY-MM>-<类型>/` | 归档物与活物**物理分离**；按时间+类型可回溯 | ✅ 已遵守：`~/wiki/discussions/archive/2026-08-bak/`（6 个文件实测在内）|
| **AR-2** | **不删除只归档**：用 `git mv` 而非 `rm` | 可逆（CR4 Reversibility）；删除是不可逆操作，需**单独授权** | ✅ 已遵守：`git mv`，`git log` 可查；归档目录 6/6 在盘 |
| **AR-3** | **mtime 保留**：`cp --preserve=timestamps` / `copy2` | mtime 是**审计依据**（`status-machine-check.sh` 的「超 7 天未结」计时）| ✅ 已遵守：`M0` 归一动了 14 张卡 mtime ⇒ **已把原 mtime 备份**到 `~/.mimiraether/backups/20260915-m0-status-normalize/` 并在总表列出（**副作用披露**）|
| **AR-4** | **先隔离再修**：损坏先导出到 `repairs/<日期>-<对象>/`，再动活件 | 活件是共享资源；直接改=破坏证据链 | ✅ 已遵守：hermes 箱 17 坏行 → `~/.mimiraether/repairs/20260915-hermes-inbox/`（raw.bak + 逐行标注 + 146 条合法 JSON + sha256），**活箱一字未动** |
| **AR-5** | **索引回填**：归档后必须更新活件索引 | 索引=唯一真源，脱节即误判（「凭空多出等我回的卡」就是这么来的）| ✅ 已遵守（本目录）；⚠️ **但见 §二 —— 本条的判据此前从未被验证过，实测有洞** |

## 二、答 OpenClaw 之问：「归档后索引回填能否覆盖归档目录？」

> ⚠️ **2026-09-17 补正（A-C1 · Hermes 转办硬条件）**：下面这段**旧文引用数字有误**。
> 当时**唯一运行产物** `~/.mimiraether/tmp/q9_poc/a4_archive_probe.log`（注意：在 **tmp**，从未进版本控制）逐行原文是
> `baseline: coverage : disk=140 listed=139 unlisted=1` … `VERDICT  : FAIL`，
> 而旧文写 `基线 : disk=140 listed=140 unlisted=0  VERDICT: PASS` —— **该组数在 log 任何一行都不存在**（把检查器的红抄成绿；
> `UNLISTED` 那件就是本方案卡自身 `2026-09-15-A组-闸与量具可信-方案.md` 6029B）。
> 且**原实验没有正控** ⇒ 三臂读数相同无法区分「子目录不可见」与「检查器坏了」。
> **已被下方「§二·补」取代**；旧文保留仅作审计轨迹。取证全文：`~/.mimiraether/notes/2026-09-17-A-C1-A4受控实验补跑.md`

**答：不能。** 而且比「不能」更糟 —— 指针会**静默蒸发**。以下为**受控实验**（真跑，可复算）：

```
$ HOME=/home/<user> .venv/bin/python3 ~/.mimiraether/scripts/b7_index_check.py
基线              : coverage : disk=140 listed=140 unlisted=0        VERDICT: PASS
① 建 notes/archive-probe-tmp/ 并放入 note.md
   → coverage : disk=140 listed=140 unlisted=0   ← disk **完全没变**（子目录不可见）
② 再把 `archive-probe-tmp/note.md` 写进 INDEX.md 的「归档」段
   → coverage : ... unlisted=0 · staleness: 0 · VERDICT: PASS   ← 该行**既不算覆盖也不算 stale**
③ 还原（删除子目录 + 还原 INDEX）→ INDEX sha256 前后一致，复检 PASS
```

**三条机制（读码 + 实测双证）**：
1. `b7_index_check.py:25` 用 `ND.iterdir()`（**非递归**）+ `p.is_file()` ⇒ **子目录整体不可见**。
2. `:42` 条目名取 `tok.split("/")[-1]`，再 `if name in files` ⇒ 指向子目录的行**不进入 `listed`**。
3. `:48` `stale = listed - set(files)` ⇒ 它也不进入 `stale`。
   ⇒ 合起来：**归档进子目录后，INDEX 行两头都不落，检查器仍报 PASS**（假绿，与 T23「打嗝的探针=确认不存在」同族）。

**结论与处置（本次只定规范，不改码）**：
- **现状可用的归档法 = 「同层 + INDEX 三段标注」**：文件**留在 `notes/` 顶层**，只在 INDEX 的「归档」段打标（当前 22 项即此形态 ⇒ 与检查器自洽）。
- **若将来要真移入子目录** ⇒ **必须先改检查器**（`rglob` 递归 + 按相对路径解析 + `stale` 判据同步），
  且**同一提交内**完成「改检查器 + 迁移 + 复检」三步，否则会留下**报 PASS 的假绿**。
- ~~该改动 **未做**~~ ⇒ **2026-09-17 已修**（`scripts/b7_index_check.py` · sha8 `55ff330f44a2` · 仓 `7407b53` 系列；修前 `disk=164` → 修后 `disk=165`，见下方 §二·修复后实测）。原文保留：【属「改量具」类，按 `同类自我修改检查单` G4（量具自审）应先出方案再动 —— 已登记 **C 组待办**】

### §二·补（2026-09-17 · 受控实验补跑 · **带正控** · 禁手抄）

- 脚本（可复跑）：`~/.mimiraether/tmp/q9_poc/a4_rerun_20260917.py`
- 原文 log：`~/.mimiraether/tmp/q9_poc/a4_archive_probe_rerun_20260917.log`（5577B）
- 调用：`HOME=/home/<user> <repo>/.venv/bin/python3 ~/.mimiraether/scripts/b7_index_check.py`
- 检查器 sha8 `25c941dc` · INDEX `sha256(pre)` `d1c92772…` · 备份 `~/.mimiraether/backups/20260917-a4-rerun/INDEX.md.pre`

| 臂 | 动作 | coverage 原文 | 判定 |
|:--|:--|:--|:--|
| **R0** baseline | 现状复检 | `disk=157 listed=153 unlisted=4` | FAIL（4 件为 09-16 未登记笔记，**已另行修复**） |
| **P 正控** | 顶层写 38B 文件 | `disk=158 unlisted=5`，列表**出现** `UNLISTED zzz-a4-probe-toplevel.md (38B)` | ✅ 顶层**可见** ⇒ 探针有鉴别力 |
| **A1** 臂① | 建 `archive-probe-tmp/note.md`(21B) | `disk=158` **不变** · `unlisted=5` **不变** · 列表**无** | ✅ 子目录**整体不可见** |
| **A2** 臂② | 该路径写进 INDEX「归档」段 | `unlisted=5`、`staleness=0` 均**不变** | ✅ INDEX 行**两头不落 = 静默蒸发** |
| **R1** 还原 | 删探针 + 逐字节还原 | `sha256(post)==sha256(pre)` · `restore_sha_ok=True` · 残留 `[]` | ✅ 无残留 |

**判定顺序（先定，防事后解释）**：P 臂必须看到 ⇒ 否则 A1/A2 的**负结论作废**（探针失效 ≠ 事物不存在）。
**结论**：**「不能覆盖」成立**，且形态是**静默蒸发**（机制见下三条，源码行号已逐条对齐）。
**红线不变**：检查器修好前，**任何人不得把文件移进 `notes/` 子目录**（否则得到报 PASS 的假绿）。

## 三、归档动作清单（照做即可）

1. `git mv <file> <dir>/archive/<YYYY-MM>-<类型>/`（**不 rm**）
2. 若动了活件 mtime ⇒ 先 `cp --preserve=timestamps` 备份原 mtime，并在总表/账本列出
3. 损坏件先导出到 `repairs/<日期>-<对象>/`，**活件不动**；导出物含：raw 备份 + 逐行标注 + 可解析重建件 + sha256 + 还原命令
4. 更新索引：**留在同层** + INDEX 打「归档」标（当前唯一与检查器自洽的形态）
5. 归档提交**单独成笔**（不与功能 commit 混）· commit message 写「位移非删除」+ 行数证据

## 四、边界与未决
- 本规范**只管归档**，不管删除。**删除需刘哥单独授权**（不可逆）。
- `AR-5` 的检查器洞（§二）**已于 2026-09-17 修复** ⇒ 修前那条「任何人不得把文件移进 `notes/` 子目录」的临时禁令**随之解除**，替换为：**归档进子目录必须以相对路径登记**（如 `evidence/x.txt`）；否则检查器以 UNLISTED 报 FAIL —— 这正是修复要达成的效果。
- 规范真源=本文件；四方讨论记录=`~/wiki/discussions/2026-09-15-四方会议-批1复核与M4立项与卡账分派.md`。

—— Mimir · 🛠 Systems Architect + 📋 Curator 视角答复 · 2026-09-15

---

## 二·修复后实测（2026-09-17 · 决定5 · 同一工具里查出**两处**死度量）

**修前 vs 修后（同一判据 · 同一真实 notes 树）**

| 判据 | 修前（sha8 `25c941dc`） | 修后（sha8 `55ff330f44a2`） |
|:--|:--|:--|
| `disk=` | **164** | **165** ✅ |
| `unlisted=` | 4 | **5**（多出的正是子目录件） |
| 子目录件可见 | ❌ 结构性不可见 | ✅ `nested   : 1 ['evidence/e3_os_level_snapshot.txt']` |
| `staleness` | **恒 0**（`stale = listed - files` = 死度量） | 登记位口径，可产出非零 |

真文件数（除 `INDEX.md`）应为 **165**；修前少的那个就是 `evidence/e3_os_level_snapshot.txt`。
⇒ 假绿不是「逻辑看着不对」，是**盘上可复算的一件文件被结构性隐藏**。

**第二处死度量（与第一处同帧存在）**：`listed` 只收录「已在 `files` 里」的 token，
而 `stale = listed - set(files)` ⇒ **恒为空集** —— 所以旧输出里的 `staleness: ... = 0 []`
**从来不是健康信号**（是恒真式）。

**修复内容**
1. `rglob` 递归；键 = **相对路径**（posix）。
2. 顶层文件仍可用 basename 登记（向后兼容）；**同名 >1 处 ⇒ 必须写相对路径**，否则报 `AMBIGUOUS`。
   ⚠️ 判定顺序是契约的一部分：**歧义必须先于精确键命中判定** —— 否则顶层同名件会把歧义吞掉
   （本仓闸测试抓出的真 bug：修前 `same.md` 只报 UNLISTED 不报 AMBIGUOUS）。
3. `staleness` 改为**登记位**口径：表格行里「整格就是一个反引号 token」+ **文件形状**过滤
   （无空白 / 无 `=` 与 `:` / 单个扩展名）。
4. 路径参数化 `--notes-dir` / `--index` ⇒ 回归套件可对 fixture 树跑受控探针，不碰真实盘。

**⚠️ 修复过程自曝：我在修假绿时一度制造了假红**
第一版 `staleness` 扫**全篇** `*.md` ⇒ 报 **8 条**；逐条核盘后 **7 条是行文内引用**
（wiki 卡 `~/wiki/discussions/…`、repo 文档 `docs/…`、带省略号的截断名）。收窄后 8 → 3 → **0**。
**教训**：`假绿` 与 `假红` 来自同一个错误 —— **判据作用域没有对着「承诺」**。
量具改动必须**双向验收**：既证「该报的报得出」（正控 + 修前反证），也证「不该报的不报」（假红防护）。

**闸**：`tests/scripts/test_b7_index_check.py` **9 例** —— 含
① 子目录件未登记必须报 UNLISTED；
② **鉴别力自证**：旧 `iterdir` 逻辑在同一 fixture 上必须漏报（否则用例无鉴别力）；
③ 结构闸：源码主体（去 docstring）不得再出现 `.iterdir()`；
④ 假红防护：行文内引用与命令输出格（`disk=3 listed=3 unlisted=0`）不得被判 stale；
⑤ basename 歧义必须报 AMBIGUOUS。

**RS17 自证 3/3 VERIFIED**（真台账 `data/ops/probe_attest.jsonl`）：
A1 代码主体不含 `.iterdir()`（target=none）· A2 运行输出声明 `nested   : 1`（target=seen）·
A3 运行输出报 `disk=166 listed=166 unlisted=0`（target=seen）。
⚠️ 其中 A1/A2 **各被闸门拦过一次**：A2 是我把不含该字面量的源文件当正控（`positive_control_failed`）；
A1 是我原措辞「文件不含」不准确 —— 目标实测命中 1 次，因为**模块 docstring 里确实写着旧版 `ND.iterdir()`**
⇒ 改为「代码主体（去 docstring）不含」并换探针后才成立。
**闸门语义已确认**：`--expect-*` 只管控制组，**目标极性必须自己核**
（控制组通过 ≠ 结论方向正确）。
