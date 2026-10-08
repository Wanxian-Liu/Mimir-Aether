---
name: mimiraether-full-suite-red-triage
description: 整仓 pytest「读数 + 红灯三分类」SOP——三臂设计（HEAD默认 / HEAD换env / baseline worktree）+ 定向 bisect 定出生点。触发词：整仓 pytest/全量测试/红灯三分类/既有红/真新引入/环境相关/红是不是我引入的。
category: mimiraether
triggers:
  - 整仓 pytest 未跑
  - 全量测试读数
  - 红灯三分类
  - 这条红是不是我引入的
  - 既有红 / 真新引入 / 环境相关
---

# 整仓 pytest 读数 + 红灯三分类

**目标**：把「仓库现在有多少红」变成可对账的读数，并把每条红钉到「出生点」，而不是猜。

## 0. 铁律

- **只测量，不修灯**。不许为数字好看改/删用例，**不许标 xfail/skip 清账**。
- 每条结论配「命令 + 数字」。禁「大概是既有问题」。
- 跑不完 ⇒ 落盘半段 + 交棒（跑到哪 / 剩哪些 / 下一步命令），**不许静默停**。

## 1. 跑之前：隔离（不隔离会 OOM 掉 gateway）

**一切重测试只走** `cd <repo> && bash scripts/pytest_isolated.sh tests -q --no-header -rf`
（内部 `systemd-run --user --scope -p MemoryMax=6G` 脱离 gateway cgroup；无 systemd-run 则 exit 97 拒跑）。

**但该脚本有两个已实测缺口，做环境臂/自证前必读**：

1. **重入不透传 `TMPDIR`**：重入行是 `env MIMIR_PYTEST_ISOLATED=1 HOME=.. PATH=..` ⇒ TMPDIR 被重置。
   凡「换 env 跑第二条臂」必须**自建 scope**：
   ```
   systemd-run --user --scope -q -p MemoryMax=6G -p TasksMax=1024 --unit=<unique> \
     env MIMIR_PYTEST_ISOLATED=1 TMPDIR=<scratch> HOME=$HOME PATH="$PATH" MIMIR_TIER0_PYTHON=<repo>/.venv/bin/python3 \
     bash <repo>/scripts/pytest_isolated.sh tests -q --no-header -rf
   ```
2. **`set -e` 让收尾自证在「红」时不可达**：脚本 `pytest` 行后 `rc=$?`，红即退出 ⇒ 末尾
   `[isolated] cgroup(后)=` / `MemoryCurrent(后)=` **永不打印**。判据：
   `grep -c 'cgroup(后)' <log>` 在红跑下正常应为 **0** ⇒ **别把「没这行」当异常**，也别指望它自证；
   隔离只能靠**首行** `[isolated] cgroup=` 不含 `mimiraether.service` 来验。

## 2. 三臂设计（缺一臂就有类别答不出）

| 臂 | 命令差异 | 回答的问题 |
|---|---|---|
| **A** | HEAD，默认 env | 当前红集合 |
| **B** | HEAD，**唯一变量** = 换一个 env（如 `TMPDIR`） | **乙·环境相关**（`A △ B`） |
| **C** | **改动前版本**（git worktree），其余同 A | **甲·既有红**（`A ∩ C`）与**丙·真新引入**（`A − C`） |

**外加对照臂 A2 = 与 A 完全同环境再跑一次**。
> **为什么必须有 A2**：A 与 B 的读数差（哪怕只是 skipped 数）会被顺手归因成「环境造成的」。
> A2 是判「这差异到底是不是环境」的**唯一控制组**。本 SOP 的作者就是在这一步抓到过一次假归因
> （A skipped=9 vs B=10 疑似 TMPDIR，A2 复跑 = 10 ⇒ 归因推翻，是运行间抖动、不是环境）。

**worktree 臂 C 的正确姿势**：

```
git worktree add /tmp/<x>/baseline-<sha> <改动前 sha>     # 不动主工作区
cd <worktree> && MIMIR_TIER0_PYTHON=<repo>/.venv/bin/python3 bash scripts/pytest_isolated.sh tests -q --no-header -rf
```

## 2.5 可移植性臂（`HOME` 变量）——**禁用同进程批跑**（2026-10-08 实测）

**症状**：你想测「哪些用例假设了操作者本机」，于是 `env HOME=<干净目录> pytest <N 个文件>`。
**血压陷阱**：读数不可信——因为 pytest **收集期会 import 所有测试模块**，模块 import 期的副作用会改变整个进程的 env。

**本仓实活**：`tests/security/test_least_privilege.py:14-18` 在 import 期执行
```python
os.environ["HOME"] = pwd.getpwuid(os.getuid()).pw_dir   # 复位为 passwd 库真值
```
⇒ 只要它被收集（与目标文件同一批跑），其后**运行时**解析 `HOME` 的用例就改用真 HOME ⇒ **假绿**。
实测：`tests/tools/test_memory_hygiene_gate.py` 单文件跑 = `1 failed`，与上述文件同批跑 = `passed`（两种顺序都一样——是**收集期**污染，不是运行顺序）。

**正确姿势（逐文件独立进程臂）**：
```
for f in <信号面内的文件…>; do
  rm -rf /tmp/clean-home; mkdir -p /tmp/clean-home
  env HOME=/tmp/clean-home <repo>/.venv/bin/python3 -m pytest "$f" -q --tb=no -p no:cacheprovider 2>&1 | tail -1
done
```
- 每个文件独立进程 ⇒ 无跨文件 env 泄漏；每轮重建干净 HOME ⇒ 无残留。
- **负控必做**：同式去掉 `env HOME=` 再跑一遍，应全绿；两臂差 = 真·HOME 假设红集。
- 判「套件是否 hermetic」的探针 = **同一文件单跑 vs 与他文件同跑** 的读数差（不是覆盖率）。

**同族坑（Q1 类）**：`grep -c 'reason='` **不是** skip 合规判据——`pytest.skip("msg")` 的首位置参数即 reason，关键字口径恒得 0（假阴性，本仓实测 0/13 vs 真值 13/13）。要判合规，解析**首个字符串字面量**的前缀（如 `DATA:` / `GIT:`），别匹配 `reason=`。

## 3. worktree 臂的两个「测量工件」——必须先排除，否则会误报回归

1. **路径派生型断言会翻**：凡「项目根只读 / 路径白名单」这类用 `_project_root()`（由**代码位置**派生）
   的用例，在 worktree（落在数据根白名单内）会绿↔红翻转。典型：`tests/security/test_least_privilege.py::test_project_write_denied`。
   ⇒ 只红在 C 的这类用例要**单列为「测量工件」**，不计入甲/乙/丙（如有需要，同时覆写 `MIMIR_REPO_ROOT`）。
2. **外仓资产不在 git 里**：`~/.mimiraether/scripts/*.sh`、`~/.mimiraether/logs/*`、`~/.openclaw/**`
   被仓库测试直接读时，**改前改后都红**（变量不在 git 差分内），会把「昨天刚漂移」读成「一直就红」。
   ⇒ 凡 A、C 都红但**首因与仓库无关**的条目，必须**读该外仓文件的 mtime/内容**再定性
   （实测例：watcher 脚本 mtime 当日 01:03 已改门控语义，测试没跟）。

## 4. 钉出生点：定向 bisect（比「既有」有用得多）

「既有红（改动前就有）」往往**不等于「老」**——可能只比你这轮早一天。
做法：拿**受影响的测试文件**（不是整仓）在候选 commit 上各跑一次（秒级）：

```
git worktree add /tmp/<x>/bisect-wt <推测起点~1>
git -C /tmp/<x>/bisect-wt checkout -q <commit> && cd /tmp/<x>/bisect-wt && \
MIMIR_TIER0_PYTHON=<repo>/.venv/bin/python3 bash scripts/pytest_isolated.sh <受影响文件...> -q --no-header -rf
```

- 绿→红的那一跳就是**引入 commit**，把它写进报告（附首因）。
- 顺带产出「丙」的可信度：若大族出生于昨日某 commit，说明**债还在流血**，不是历史包袱。

## 5. 抽取型 harness 漂移：别当产品 bug

有一类测试从生产源码**抽代码块再 `exec`**（锚点如 `_final_content = ""` → `if _result.interrupted:`）。
生产块长大后会引用方法体符号（`self`、`logger.warning`、新局部函数），而 harness 的 exec 命名空间没跟上 ⇒
报 `NameError: name 'self' is not defined` / `AttributeError: '_Logger' object has no attribute 'warning'`，
**伪文件名形如 `<core_loop.py:1054-branch>`** ⇒ 读起来像产品 bug，实为**测试基础设施失配**。
判据：报错行号指向引擎**源码行**、且该用例的 `_extract_branch()` 自身锚点断言**全部通过**。

### 5.1 修法配方（2026-10-07 实证 · 族1 14 红 → 0 · 只动 setup）
1. `_Logger` 桩补 `warning/info/debug`（`error` 语义不变）——失败第 2 跳（except 体内再抛 AttributeError）就死在这。
2. 补 `_HarnessSelf`（`_resolved_max_turns=None` / `max_iterations=<int>`）+ ns 键 `"self"` / `"session_id"`。
3. 补模块级助手（如 `_b3_flush_half_segment`）**受控桩**（返回 `None`）——真实现会在测试期**真写盘**（框架代写半段）污染工作区；其自身由专属单测覆盖。
4. **假绿必查**：锚内新增的**观测段**（B4 `agent.run_health.record_run_exit`）越线时走 `logger.error("[RUN_HEALTH_ALERT] …")`
   ⇒ 既让 `assert not lg.errors` 类臂**误红**，又让 `assert lg.errors` 类正控被**冒名送假绿**。
   处置 = 用产品自带回滚开关（`MIMIR_RUN_HEALTH=0` · `agent/run_health.py:27` 文档化）在 autouse fixture 里关观测，**不改断言**。
5. 三条证据缺一不可：① 旧 ns 复现红 → 新 ns 绿（setup 敏感性）② 受控差分（破坏被判据 ⇒ **读数必须变**，防空跑探针）③ 逐条引用源改动 `commit + 行号` 说明「旧 setup 为何过期」（拒「默默改断言」）。

### 5.2 L2 异源复核三判据（2026-10-07 实证 · 修完之后「谁来验」）

修完只算 **L1 自证**（自报读数）；完工须过 L2 = 他者重跑。复核方**不重写修复**，只重跑三判据：

```bash
# ① 聚焦：受影响文件（快，~4s）
cd /home/rayliu/src/MimirAether && TMPDIR=/tmp env HOME=/home/rayliu bash scripts/pytest_isolated.sh \
  <受影响文件...> -q --no-header -rf 2>&1 | tail -3
# ② 整仓两环境（A: TMPDIR=/tmp；B: 默认不覆写）——两读必须逐条相同
cd /home/rayliu/src/MimirAether && TMPDIR=/tmp env HOME=/home/rayliu bash scripts/pytest_isolated.sh tests -q --no-header 2>&1 | tail -1
# ③ 正控可反转：抽块三臂差分（残契约 ⇒ 报错；完整契约 ⇒ 明示；同一块 1 token 差分 ⇒ 读数必须变）
```
③ 的现成探针：`~/.mimiraether/tmp/probe_family1_reversal.py`（import 测试模块 → `_live()` → 自建 ns 三臂）。
**判据：三臂读数互异**（如全同 ⇒ 探针空跑/恒绿，同 `2c0b303` 第 4 种死法）。
⚠ `pytest_isolated.sh ... | tail -1` 的末行是 `[isolated] gateway MemoryCurrent(后)=…`，
**pytest 汇总行不是最后一行** ⇒ 要 `grep -E '[0-9]+ (failed|passed|skipped)'` 或先重定向到文件再读。

### 5.3 并发 run 撞同一单（双路唤醒）：先探活，再决定写不写

同一派单行可能被**两个 run 并行消费**（游标"读取"与"推进"之间没有原子认领步）。
开工与**每次写盘前**都探活一次：

```bash
tail -300 ~/.mimiraether/logs/agent.log | grep -oE '\[[0-9a-f]{8}\]' | sort | uniq -c | sort -rn   # ≥2 条 trace = 并发
ls -lt --time-style=+%H:%M:%S /home/rayliu/.hermes/inbox/ | head -3                                  # 对侧是否已投回执
```
- 命中 ⇒ **只做增量**：不覆盖/不删对侧产物，改写「独立复核回执」（L2）+ 双路唤醒记录；对侧段与产物一律保留。
- 自己写盘前先做**幂等自检**（如 `git diff | grep -c <自己的新符号>` = 0 才落笔），避免与对侧交叉污染。
- 按 `AGENTS §5.1` 第 2 级上报（**改机制**：认领即原子推进游标 / flock 关键区），不是再提醒一次。
- 别用 `pgrep -f <脚本名>` 或 `ps -eo cmd | grep <脚本名>` 判对侧是否在跑——**命令行含脚本名即自匹配**
  （连"等待对侧跑完再开跑"的看门循环都会自我死等）；判活改用「记下 PID 后 `ps -p`」或读日志末行。

## 6. 出场（报告骨架 + 回执）

报告必含：① 跑命令原文（逐字可复制）② 三臂表（总数/passed/failed/error/skipped/耗时/rc + 原始日志路径）
③ 对照基准 sha + `git diff --stat <base>..HEAD` ④ 三分类（每类带读数，**空类也要给空集判据**如 `A − C = ∅`）
⑤ 要修清单**按族**（根因/影响面/修法预估/是否本仓责任）⑥ 真缺陷单列（可见不修）⑦ 边界声明
⑧ 回执契约两字段：`重跑命令:` / `复算数字:`（逐字，含全角冒号）。

**回执给复核方的第一条命令 = 整仓那一条**（复核方重跑对账），不是 grep 中间产物。
