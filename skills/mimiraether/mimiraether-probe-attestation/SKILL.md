---
name: mimiraether-probe-attestation
description: RS17 探针自证闸——凡声明类结论（未生效/为 0/缺失/从未/not found）落盘前必须附「控制组通过的探针自证」。触发词：探针/自证/UNVERIFIED/误报/为 0/未生效/缺失/验证失败/负结论/grep 计数。是「探针失效被读成事实」这一类误报的机制化修复（非意志）。
---

# 探针自证闸（Probe Attestation Gate · RS17）

## 什么时候用（触发）

**只要你要说出一句"否定/缺失"的结论**，就先用它：

- 「X **未生效** / **未装载** / **没跑**」
- 「Y **为 0** / **0 次** / **从未**发生」
- 「Z **缺失** / **不存在** / **not found** / **查无**」
- 任何 `grep -c` / `awk` / `ls` / 计数类探针的**输出即结论**的场合

**不适用**：正向结论（"已生效/有 3 条"）不必自证；但若正向结论也靠脚本计数，同样建议自证。

## 为什么必须机制化（不要靠记性）

实证：2026-09-12 我命名了「探针未验证就下结论」，随后**两天重犯 14 次**。历史误报：
- 未转义 `[COMPRESS-RESULT]` 当正则（真行名是 `[COMPRESS] result`）→ 假计数 0
- `awk '$2>="13:53:54"'` 按**字典序**比时刻 → 跨天误计
- `ls` 空输出被读成"文件不存在"（`~` 展开问题）

共同结构：**探针失效 → 输出被当成事实**。命名失败 ≠ 修好失败。

## 怎么用（三步）

```bash
cd ~/src/MimirAether
./.venv/bin/python -m agent.probe_attest \
  --claim '<你要说的结论>' \
  --probe 'grep -c "PATTERN" {INPUT}' \
  --positive <已知为真的样本> \
  --negative <已知为假的样本> \
  --target  <真实样本>
# exit 0 = VERIFIED（可当事实用）
# exit 3 = UNVERIFIED（不许当事实用，只能标 UNVERIFIED）
```

**控制组语义**（这是全部价值所在）：

| 组 | 输入 | 期望 | 含义 |
|:--|:--|:--|:--|
| positive | **已知为真**的样本 | `seen` | 探针能看到"有" |
| negative | **已知为假**的样本 | `none` | 探针能看到"没有" |
| target | 真实样本 | —— | 只有前两组都合格，这行才可信 |

- **正控失败** = 探针在已知有货的样本上都报空 ⇒ 探针坏了（**与真实样本说什么无关**）
- **负控失败** = 恒真探针（如 `echo 1`）
- 三类结构性无效：无 `{INPUT}` 占位符 / 正负控样本相同 / 空探针

## 关键陷阱（都是实测踩过的）

1. **控制样本必须自己先验证**。我曾拿"真实文件第一行"当已知为真样本——那行其实是 rollback 行，正控当场失败。**控制样本本身也是一个未验证假设**，先 `grep -c` 自检（应为 1 / 0）再用。
2. **格式要对齐**。真实台账是 `{"outcome": "applied"}`（带空格），我手写的紧凑 JSON `{"outcome":"applied"}` 不匹配 → 正控失败。**用 `grep -m1` 从真实数据里摘样本**，别手写。
3. **`grep -c` 返回单个 `0` 视为 `none`**（见 `observe()` 口径）；多行输出为 `seen`。
4. **不要为了过关把探针放宽**——那正是"闸门越调越松"的老病（同 Loki Q1）。先判探针是否有效，再判结论。
5. `--list N` 读台账；台账是 **append-only JSONL**，四方可审计。
6. **正控载体必须"先证其存在"**。我填了 `gateway/verify_before_report_guard.py`（该路径**不存在**，真实是 `agent/` 与 `scripts/` 各一份）⇒ `rc=2` / `observed=none` ⇒ **positive_control_failed → UNVERIFIED**。
   用前先 `grep -rl '<TOKEN>' <repo> --include=*.py` 把真实载体**打出来再填**，别凭记忆写路径。
7. **绝对路径，禁用 `~`**。沙箱内 `~` 展开成 mimir home ⇒ `~/.mimiraether/...` 被拼成
   `<home>/.mimiraether/.mimiraether/...` **假路径**，于是**所有**相关探针整齐返回 `0`。
   **这是最阴的失败形态**：错路径的报错长得像"确认为空"。`grep -c` 的 `0` 是全库最不可信的数字。
8. **统计"闸拦了几次"时不要 `grep 'probe-attest'`**——日志里**永远**命中 0（假的 0）。
   拦截经旧 guard 出口落盘，横幅文字是 `[BLOCKED:verify-before-report]`。
   正确探针二选一：`grep -c 'BLOCKED:verify-before-report' <log>`，或读台账 `source` 字段
   （`probe_attest` = CLI 自测；`verify_before_report_guard` = 进程内拦截）。
   **同理：不要把自己按设计意图拼出来的横幅文字当日志原文引用。**

## 闸门行为（守着我，不靠我记）

- 挂在 `agent/verify_before_report_guard.py::should_block_finish()`，**在**"调过工具就放行"那条旧判据**之前**（否则永远够不着——探针本来就要调工具）
- 命中声明类结论 + 本轮无自证 ⇒ **拦一次**，注入 `[BLOCKED:probe-attest]` 专用提示（含 CLI 用法）
- 反死锁：同轮已有该标记 ⇒ 不再拦（放行但**自动落一条 UNVERIFIED**）
- 台账：`~/.mimiraether/data/ops/probe_attest.jsonl`

| env | 默认 | 作用 |
|:--|:--|:--|
| `MIMIR_PROBE_ATTEST` | `1` | 总开关 |
| `MIMIR_PROBE_ATTEST_MODE` | `nudge` | `off` / `nudge`（拦一次） / `hard`（每次都拦） |
| `MIMIR_PROBE_ATTEST_TTL` | `900` | 自证有效窗口（秒） |

**回滚**：`MIMIR_PROBE_ATTEST=0`（秒级，无需回退代码）。

## 实战补充（2026-09-14 · 闸**拦住了我自己的汇报正文**）

真实发生：我把 RS18/RS11 两条结论整理成汇报时，**闸在飞书回复上直接 `[BLOCKED:probe-attest]`** ——
因为汇报里含有「unlisted=0 / 命中 0 / NULL=0 / 连续相同=0」等否定句。这不是误拦，这是**正确拦截**：
汇报正文**也是一个"声明类结论的出口"**。

**纪律**：**落汇报 / 落卡之前，先把该文本里所有否定句自证跑完**（不是"发出去被拦再补"）。

### 三种可复用的控制组造法（找不到样本时）

| 场景 | positive（须 seen） | negative（须 none） | target |
|:--|:--|:--|:--|
| 令牌存在性（"X 未装载"） | 已知存在令牌（如 `wake_gate`） | 不可能令牌（如 `ZZQ_IMPOSSIBLE_TOKEN_9137`） | 被质疑令牌（如 `DUP-REPLY`） |
| **聚合类判据**（"unlisted=0 / 无 FAIL"） | 判据字符串本身（`PASS`） | 不可能判据（`ZZQ_IMPOSSIBLE_VERDICT`） | 反向判据（`FAIL`） |
| 盘上**找不到**已知为真样本 | **自己合成**（脚本加 `--selftest` 造夹具，如造一个含 2 条连续相同消息的 jsonl，期望输出 `1`） | 不存在的文件/路径 | 真实样本 |

**要点**：第 3 行是通用解 —— "已知为真"的样本可以**造**，而且**合成正控往往比真实样本更有鉴别力**（因为你能控制它必然为真）。

### 一次跑多条

四条声明 = 四条 `probe_attest` 调用（同一台账 append-only），**逐条留 verdict**，再把
`verdict + positive/negative observed + target` **贴进报告**。范例（本日实录）：

```
索引机械检查 unlisted=0   : VERIFIED  pos=seen(PASS) neg=none  target=none(FAIL)
DUP-REPLY 未装载          : VERIFIED  pos=seen(wake_gate) neg=none  target=none
fts5 NULL hash = 0        : VERIFIED  pos=seen(ALL) neg=none  target=none
raw jsonl 连续相同 = 0     : VERIFIED  pos=seen(合成夹具) neg=none  target=none
```

**注意**：target 的 `none` **不等于**"没做事" —— 只有在正控 `seen` + 负控 `none` 都合格时，
target 的 `none` 才读作"该模式确实不存在"。

## 闸的盲区与加固（2026-09-14 · T9/T10 —— 闸自己也会被绕过）

**已修（commit `395d2d4`）**：三条结构性判据，全部落 `attest()`，判 `UNVERIFIED` 且 reason 可区分：

| reason | 触发条件 | 修前后果 |
|:--|:--|:--|
| `vacuous_expectations` | `expect_positive == expect_negative` | **死探针也 VERIFIED**（空洞控制组）|
| `control_is_target` | `target == positive` | 同义反复：用被测对象自证被测对象 → **VERIFIED** |
| `target_reuses_negative` | `target == negative` | 目标未经独立测量（单独 reason 便于审计）|

**修前实测（六例）**：死探针 + 两边期望都写 `none` = **VERIFIED**；`--positive` 与 `--target` 同一路径 = **VERIFIED**。
修后：B=`vacuous_expectations`、C=`control_is_target`、C2=`target_reuses_negative`；
**合规对照仍 VERIFIED**（未过度拦截）；常量输出仍 `negative_control_failed`。

**输出契约（必读）**：探针 stdout 必须是 **0/1 或 `grep -c` 的计数** —— `observe()` 把 `0`/空读作 `none`，**其余一律 `seen`**。
- ❌ `test -e {INPUT} && echo seen || echo none` —— 字面量 `none` 被读成 **seen** ⇒ 负控必失（09-14 因此误伤 2 条自证）
- ✅ `test -e {INPUT} && echo 1 || echo 0`

**三条硬约束**：① 两控制组样本必须不同 ② 期望值必须不同 ③ 目标样本不得兼作控制样本。

**残余风险（未修，须人工守）**：判据只比**样本字符串**。若 target 与 positive 是**不同路径、同一内容**，闸检测不到（须读文件内容才能判）⇒ 此情形请人工确认目标样本独立。

**夹具自身也要过契约**：第一次取证时我把 `target` 与 `negative` 都设成同一个"不存在的路径"，六例**全被判 `control_is_target`** —— 取证被自己的夹具污染。**造夹具前先满足三条硬约束。**

## 取证纪律

- 自证成功的记录要**贴在报告里**（`verdict` + 两个控制组的 observed + target）
- 自证失败时，**先怀疑探针，再怀疑结论**——绝大多数时候是探针
- 探针自纠要**写进当日 notes**：失败模式 + 对策（否则下次重犯）

## 调用载体（实测坑）

**必须**以模块方式跑（`agent/types.py` 会遮蔽 stdlib `types`）：

```bash
cd ~/src/MimirAether && ./.venv/bin/python -m agent.probe_attest ...
```

直跑脚本路径 `python3 agent/probe_attest.py` ⇒ `ImportError: cannot import name 'GenericAlias' from partially initialized module 'types'`（circular import）。

另注：`python3 -c '...'` 被 `exec_mixin` 的 **DENY 白名单**拦截（`dangerous command pattern 'python3 -c'`，全库已出现 ≥2 次）⇒
需要内联 Python 时，**写成 `.py` 脚本落盘再跑**。

## 闸的语义边界（2026-09-14 · T22 —— `VERIFIED` 是对**探针**的，不是对 claim 的）

实测：一条「收件箱 X 之后无新条目」的否定声明，正/负控**都过**（探针确有鉴别力）⇒ CLI 打 `verdict: VERIFIED`，
而同一行的 `target: observed=seen(49)` **恰好证伪了这条 claim**。
⇒ 读者必须**同时读 `target`**：`VERIFIED` 只保证「这不是一支坏探针」，**不保证「结论为真」**。
> 提案（未落地）：CLI 增 `claim_polarity` —— negative claim 遇 `target=seen` 应判 `CONTRADICTED`，而非 `VERIFIED`。

## 陷阱：`ts` 单位混用（比「缺字段」更阴——不报错，只静默错）

同一个 `jsonl` 实测 116 行内含 **三种形态**：10 位 epoch 秒 60 条 / 13 位 epoch 毫秒 49 条 / ISO 字符串 7 条。
只把「数字」直接比大小的探针，会把 2026-08 的**毫秒**条目读成「晚于今天 cutoff」⇒ **报 49，真值 0**（49 全是假阳性）。
修法：**比较前先归一化单位**（`v > 1e11 ⇒ v/1000`），并用**判别力夹具**验证：同一条 2026-08 毫秒条目 `v1→1 / v2→0`。
一句话：**跨时间比较前，先问「单位归一了吗」。**

## 陷阱：文本 grep 计数 ≠ 结构语义

`grep -c '"last_run_at": null'` 在真文件上返回 **0**，而 `json.load` 解析后该字段确实是 `None` ——
因为那个作业**整个键都不存在**（`j.get("k")` 返回 None 与「键存在且值为 null」是两回事）。
⇒ **结构断言优先用 Python 解析 + 显式判据**（`"k" not in j` vs `j.get("k") is None`）；grep 只用于**版式已确认**的场景。

## 同步方向的元陷阱（2026-09-14 · T22 当场重犯）

`skill_manage(action='patch')` 写 **repo 侧**（`~/src/MimirAether/skills/...`）。若照旧文 `cp home→repo` 同步，
会**把刚才的 patch 抹掉**（本次已发生一次：patch 成功 → `cp home→repo` → 改动消失，且 `diff -q` 还报「一致」= 假绿）。
**正确顺序**：`skill_manage` 改 → `grep` 关键串确认 repo 侧**在** → `cp repo→home` → `grep` 确认 home 侧**在** → 才 commit。
⇒ **`diff -q` 只能证明两侧相同，不能证明「相同的是新版」**。

## 相关文件

- 模块：`agent/probe_attest.py`
- 测试：`tests/agent/test_probe_attest.py`（27 例，含 09-13 误报回归；已登记 Gate2）
- 设计文档（两方案对比与合并）：`~/.mimiraether/notes/2026-09-14-RS17-probe-attestation-two-plans.md`
