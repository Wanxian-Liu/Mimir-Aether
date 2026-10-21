# Chroma 写锁：保证什么、不保证什么

> **适用代码**：`tools/chroma_session_indexer.py::chroma_write_lock()` 及全部调用点。
> **基线**：`HEAD=56377e6`（RL-20261020-094 B9）。本文件只描述**现状**，不含改造计划。
> **写法约束**：每条陈述后括注 `文件:行号`，或给出可复跑命令 + 预期读数。二者皆无的句子不写。
> **不出现在本文件的数字**：不写（含「应该 / 大概 / 一般来说」）。

---

## 1. 保证什么

### 1.1 单次写操作互斥（跨进程 flock + 进程内 RLock 两层）

粒度 = **一次写操作**（一次批量 `upsert` / 一次 `delete`），不是整轮回填：

| 层 | 机制 | 出处 |
|---|---|---|
| 跨进程 | `fcntl.flock(fd, LOCK_EX \| LOCK_NB)`，50 ms 轮询 | `tools/chroma_session_indexer.py:164`、`:175` |
| 进程内 | `threading.RLock()`，同线程重入免费（深度计数），异线程先在此串行 | `:75`、`:226`、`:237-239` |

粒度取舍是**故意**的，代码注释原文：「Granularity: per write operation (one batch upsert / one delete),
NOT the whole backfill run -- a full rebuild must not starve the gateway writer for hours
(bounded lock budget, not an ever-held lock)」（`tools/chroma_session_indexer.py:29-31`）。

锁文件是**旁车**：`<mimir_home>/data/chroma_write.lock`，**不在** chroma 目录内
（`:39-41`、`:54-57`；用例 `tests/tools/test_chroma_write_lock.py:101-105` 断言
`"chroma_sessions" not in str(lock_path)`）。理由（`:39-41`）：chroma 目录会被复制/重建/替换，
锁必须比它活得久。

### 1.2 崩溃后无残留锁

flock 由内核在 fd 关闭时释放——正常退出、`SIGKILL`、显式 `LOCK_UN` 是同一机制，
所以**没有 stale-lock 回收器，也没有落盘的 "locked" 状态要清理**（`:36-38`）。

实测（§5.6 探针，两次复跑各 5 次）：`kill -9` 持有者后重新获取耗时
**trials 落在 0.0003 ~ 0.0006 s**（中位 0.0004 s / 0.0005 s）。

已死持有者留在锁文件里的 `token` 只是**过期文本**，不构成锁——互斥由 flock 判定，
不是由文件内容判定（`:156-176`）；`token` 只在 B4 用于报错点名（`:109-153`）。

### 1.3 锁文件被删 / 被换掉时不会锁到一个别人看不见的 inode

每次获取后写入 `nonce = "<pid>:<time_ns>"` 并立刻读回；读回值 ≠ 自己的 nonce ⇒ 判定路径已指向
别的 inode，`LOCK_UN` + `close` + 重开重试（`:96-97`、`:181-207`）。理由（`:82-84`）：
「inode numbers are reused on this filesystem, so st_ino alone cannot prove ownership」。

### 1.4 同线程嵌套不会因预算极小被判超时

`RLock.acquire()` 在当前线程已持有时立即返回 `True`，不走 deadline 路径（`:222-224`）。
用例 `test_same_thread_reentrant` 在 `MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S=0.001` 下跑两层嵌套
（`tests/tools/test_chroma_write_lock.py:151-163`）。

---

## 2. 不保证什么

**以下五条是设计边界，不是待办缺陷。** 踩到任一条都不是这把锁的 bug。

### 2.1 不保证会话级原子

`delete_session_chroma_documents()`（`:900-911`）先取锁删掉整会话文档、**随即还锁**；
重新嵌入 / `upsert` 是之后另一次取锁（`:789-790`）。两次取锁之间没有任何保护，
中间态（文档已删、新向量未写）对并发读者可见。

### 2.2 不保证 prune 无 TOCTOU

`prune_session_chroma_orphans()` 的**判别在锁外、删除在锁内**：

- 锁外读现状并算 `stale = have - wanted` —— `:954-971`；
- 锁内只做 `collection.delete(ids=stale)` —— `:976-977`。

因此「读到某 id 过期」到「真正删除」之间有窗口：若该 id 的源行在窗口内被重新写入
（doc id 形如 `{session}:{message_id}`，`message_id` 可复用），删除仍会执行 ⇒ **可能删掉一条活文档**。
锁保护的是「删除动作不与其他写并发」，**不是**「判别到删除之间世界不变」。

### 2.3 不保证跨主机

`flock` 是本机文件锁。共享文件系统（NFS 等）上的语义由内核与挂载参数决定，本仓不测、不承诺。

### 2.4 不保证「调用方一定加锁」

锁是**用则互斥**，不是强制注入：未加锁的写站点不会被运行时拒绝，只能靠判据在巡检时发现。
现在有两道：静态 AST（§4）+ 行为用例 `test_delete_path_blocks_while_lock_held`
（`tests/tools/test_chroma_write_lock.py:215-`，断言被阻塞调用方的耗时下界）。

### 2.5 不保证进程内报文的「线程名」是持有者的名字

进程内超时报文写 `holder=thread:<name> (same process)`，`<name>` 取自
`threading.current_thread().name`（`:233`）——即**等待方自己**的线程名，不是持有者线程名。
实测样例见 §5.4（waiter 跑在主线程 ⇒ 报文写 `thread:MainThread`）。
它只说明「同进程另一线程持锁」，**不能**据此定位具体是哪个线程。

---

## 3. 超时语义

### 3.1 预算来源

| 项 | 值 | 出处 |
|---|---|---|
| 环境变量 | `MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S` | `:61` |
| **默认值** | **60.0 秒** | `:46`（`DEFAULT_WRITE_LOCK_TIMEOUT_S = 60.0`） |
| 轮询间隔 | 0.05 s（50 ms） | `:47`（`_WRITE_LOCK_POLL_S = 0.05`） |

解析规则（`:60-72`）：

- 空 / 未设 ⇒ **60.0 s**；
- 可 `float()` ⇒ `max(0.0, 值)`——**负数夹到 0 ⇒ 立即超时**（不报错）；
- 不可 `float()` ⇒ `logger.warning` 后回落 **60.0 s**，**不抛错**。

复跑：`grep -n "_write_lock_timeout_s" tools/chroma_session_indexer.py` 应得 4 行
（定义 `:60` + 三处调用 `:171`、`:225`、`:238`）——**没有任何一处把默认值写成 60 以外的数**。

### 3.2 两路都抛同一个异常类型

两路都抛 `ChromaWriteLockTimeout(RuntimeError)`（`:50`），调用方一个 `except` 通吃：

| 路 | 触发点 | 报文骨架 | 出处 |
|---|---|---|---|
| 跨进程（flock） | `LOCK_NB` 撞 `EACCES/EAGAIN` 且过 deadline | `chroma write lock not acquired within <N.N>s (another process holds <path>) holder=<…>` | `:168-174` |
| 进程内（RLock） | `acquire(timeout=预算)` 返回 `False` | `chroma write lock not acquired within <N.N>s (another thread in this process holds it; same-process contention) holder=thread:<name> (same process)` | `:226-234` |
| 锁文件被反复替换 | nonce 校验失败且过 deadline | `chroma write lock file kept being replaced under us: <path> holder=<…>` | `:203-207` |

`holder=` 的形态（`:109-153`）：`pid=<pid> (alive) token=<pid>:<ns>` ·
`pid=<pid> (gone) token=<pid>:<ns>` · `pid=<pid> (unknown) token=…` / `unknown`。

**`(unknown)` 不是 `(gone)`**：procfs 不可用（容器 / `hidepid`）时报 `(unknown)`，
理由见注释原文「a false "gone" sends the responder hunting a live holder」（`:136-139`）。
持有者描述整体 best-effort：任何分支都返回字符串、**永不抛错**（`:117-118`、`:151-153`）——
不能因为诊断写不出来而掩盖原本的 `ChromaWriteLockTimeout`。

### 3.3 超时之后的行为由调用方决定，不由锁决定

锁只负责**抛**。各调用点保留既有 fail-open：捕获后记 `note_index_failure(...)` 并返回
（例：`:895-897`、`:909-911`、`:980-982`）——「拿不到锁 ⇒ 本轮跳过，不无限等」。

---

## 4. 覆盖判据

**脚本**：`~/.mimiraether/gates/verify_chroma_write_coverage.py`（不在本仓 git 内，见 §4.3）。

**当前读数（本轮实跑）**：`guards=10 unguarded=0 nullable=1 guards_real=9` → **`rc=2`**（nullable 告警）；
`--selftest` **9/9 arms passed**。

**判据锚点**：`sha256=ed0c63b8bdb97f69bd6d4d0b8b7432c6914af80ee7e9fd2d059a2e3424f2df32`（896 行，2026-10-22）——上句读数属于这一版判据；换版必换 sha，读者据此判定读数归属。

**`guards=10` 里有 1 处是 nullable，不许藏**：第 3 格（`tools/chroma_guard.py:121`，内嵌探针）词法上有 `with`，但它在锁导入失败时把锁名绑成 `contextlib.nullcontext`（§4.1）⇒ **运行时可能无锁**。
`guards_real=9 = guards − nullable` 才是真正有锁的站点数；`nullable>0 ⇒ rc=2`（不是 rc=0）。

| # | 站点 | 操作 | 状态 |
|---|---|---|---|
| 1 | `scripts/chroma_backfill_full.py:235` | `col.delete` | guarded |
| 2 | `scripts/chroma_backfill_full.py:260` | `col.delete` | guarded |
| 3 | `tools/chroma_guard.py:121` | `chromadb.PersistentClient` | guarded **[embedded]** · **nullable** |
| 4 | `tools/chroma_session_indexer.py:790` | `collection.upsert` | guarded |
| 5 | `tools/chroma_session_indexer.py:815` | `chromadb.PersistentClient` | guarded |
| 6 | `tools/chroma_session_indexer.py:908` | `collection.delete` | guarded |
| 7 | `tools/chroma_session_indexer.py:977` | `collection.delete` | guarded |
| 8 | `tools/session_search_indexer.py:639` | `col.delete` | guarded |
| 9 | `tools/session_search_indexer.py:861` | `col.delete` | guarded |
| 10 | `tools/session_search_indexer.py:1025` | `collection.delete` | guarded |

表内行号是**被覆盖的调用行**，比 `with chroma_write_lock():` 那行大 1（例：`:789 with` → `:790 upsert`）。

### 4.1 为什么纯 AST 会漏一处

`tools/chroma_guard.py::_PROBE_SRC` 是一段**字符串常量**（`:103` 起）。里面的
`chromadb.PersistentClient(path=root)`（字符串内第 121 行）由
`subprocess.run([sys.executable, "-c", _PROBE_SRC])` 在子进程执行（`:148`），是真实写路径，
但函数体 AST 里看不到它。判据对此做**递归 `ast.parse` 字符串常量**，命中后标 `[embedded]`；
`--selftest` 的 `arm=embedded_python_source` 就是它的负控（3 站点、故意留 2 处未加锁 ⇒ `rc=1`）。

该内嵌源码在 `chroma_write_lock` 导入失败时退化为 `nullcontext` 并记 `lock=unavailable`
（`tools/chroma_guard.py:112-115`）——探针**宁可不加锁也要能跑**（它本身只读，目的是探测降级态）。

### 4.2 判据自身可信度（两向）

`--selftest` 9 臂 = 该放行的放行 + 该拦的拦住，缺一臂即判据不可信：
6 个基础臂（下 6 行）+ 3 个结构性臂（`scope_disclosure` / `nullable`（含 5 个子例，其中 2 个是「不该报 nullable」的假阳性负控、1 个验嵌套 try 深度）/ `cwd_default`）。逐字输出（2026-10-22 实跑；绝对 home 路径按公开仓规则掩为 `$HOME`，其余逐字）：

```
arm=lock_in_upsert expected_rc=0 actual_rc=0 sites=1 unguarded=0 nullable=0 PASS
arm=unlocked_delete expected_rc=1 actual_rc=1 sites=1 unguarded=1 nullable=0 PASS
arm=comment_and_plain_string expected_rc=0 actual_rc=0 sites=1 unguarded=0 nullable=0 PASS
arm=nested_other_with expected_rc=1 actual_rc=1 sites=1 unguarded=1 nullable=0 PASS
arm=same_name_other_types expected_rc=0 actual_rc=0 sites=1 unguarded=0 nullable=0 PASS
arm=embedded_python_source expected_rc=1 actual_rc=1 sites=3 unguarded=2 nullable=0 PASS
arm=scope_disclosure_explicit_root expected_rc=1 actual_rc=1 first_line='scan_root=/tmp/tmp_ikploqp/arm7_repo_copy' note=no PASS
arm=scope_disclosure_last_resort expected_first_line=scan_root=$HOME/src/MimirAether actual='scan_root=$HOME/src/MimirAether' warn=yes PASS
arm=nullable[nullable_fallback] expected_rc=2 actual_rc=2 sites=1 guards=1 unguarded=0 nullable=1 PASS
arm=nullable[nullable_not_present] expected_rc=0 actual_rc=0 sites=1 guards=1 unguarded=0 nullable=0 PASS
arm=nullable[nullcontext_other_name] expected_rc=0 actual_rc=0 sites=1 guards=1 unguarded=0 nullable=0 PASS
arm=nullable[nullcontext_multi_hop_alias] expected_rc=2 actual_rc=2 sites=1 guards=1 unguarded=0 nullable=1 PASS
arm=nullable[nullcontext_nested_try] expected_rc=2 actual_rc=2 sites=1 guards=1 unguarded=0 nullable=1 PASS
arm=cwd_default_negative_control expected_rc=1 actual_rc=1 first_line='scan_root=/tmp/tmp_ikploqp/arm9_repo_copy' note=yes PASS
selftest: 9/9 arms passed
```

### 4.3 已知边界：判据脚本不在版本控制里

`git ls-files | grep verify_chroma_write_coverage` = **0 行**；磁盘上只有
`~/.mimiraether/gates/verify_chroma_write_coverage.py` 一份。⇒ **只 clone 本仓的人无法复跑本判据**，
必须从运行机取该文件。这是当前事实，不是建议。

重跑命令: `cd ~/src/MimirAether && ~/src/MimirAether/.venv/bin/python3 ~/.mimiraether/gates/verify_chroma_write_coverage.py`
复算数字: 首行 `scan_root=$HOME/src/MimirAether`、末行 `guards=10 unguarded=0 nullable=1 guards_real=9` 且 **`rc=2`**（nullable 告警，不再假装 rc=0）；加 `--selftest` ⇒ `selftest: 9/9 arms passed` 且 `rc=0`

负控（副本，判据不许被骗绿）：
重跑命令: `C=$(mktemp -d) && cp -a ~/src/MimirAether/{tools,scripts} $C/ && cd $C && ~/src/MimirAether/.venv/bin/python3 ~/.mimiraether/gates/verify_chroma_write_coverage.py`
复算数字: 首行 `scan_root=$C`（此前会扫默认真仓、读绿）；拆掉一处 `with chroma_write_lock():` ⇒ `guards=9 unguarded=1`、`rc=1`

---

## 5. 实测读数

统一形状：「命令 → 读数」。§5.1 / §5.4 / §5.5 是本文件作者本轮复跑所得；
§5.2 / §5.3 的历史读数来自 commit message / 代码注释 / 用例 docstring（每条给出复取命令）。

### 5.1 SIGKILL 释放时延

命令：§5.6 探针 `arm 1`（杀持有者再抢锁，5 次 × 2 轮）。

```
run1: sigkill_release_s trials = [0.0006, 0.0005, 0.0005, 0.0005, 0.0004]
      sigkill_release_s min = 0.0004 median = 0.0005
run2: sigkill_release_s trials = [0.0006, 0.0004, 0.0004, 0.0003, 0.0003]
      sigkill_release_s min = 0.0003 median = 0.0004
```

用例上界：`test_sigkill_holder_releases_the_lock` 断言 `< 1.5 s`
（`tests/tools/test_chroma_write_lock.py:137-148`）——实测比该上界小三个数量级。

### 5.2 临界区收缩（B2：嵌入移出锁）

复取命令：`git log -1 --format=%B 7ed66a0`。原文读数：

- 改前：128 文档批 `collection.upsert` 在锁内惰性解析嵌入 ⇒ 持锁 **35.1 s / 35.2 s**
  （单条消息 0.343 s）；
- 改后：嵌入在取锁前完成，锁只覆盖写；探针三臂持锁 **6.51 s / 0.07 s / 6.51 s**
  （两进程臂向量 `max|delta| = 5e-08`）。

即同一批的**锁内**耗时从 ~35 s 级降到 ~0.07 s 级。

### 5.3 进程内等待上界（B3 前 vs 后）

- B3 前：`MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S=0.3` 预算下**实测等 1.80 s** 才拿到锁——
  预算被静默穿透且无日志（`tools/chroma_session_indexer.py:221-222` 注释）。
- 用例 docstring 对同一现象的另一种量法：「with a 0.3s budget and a 2.5s holder it returned
  after ~1.8s with the lock in hand」（`tests/tools/test_chroma_write_lock.py:271-273`）。
- B3 后（§5.4 本轮实测）：0.3 s 预算 ⇒ **0.300 s** 抛 `ChromaWriteLockTimeout`，不再穿透。

### 5.4 超时报文样例（本轮实测，逐字）

探针：§5.6（持有者为子进程 / 同进程另一线程），`MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S=0.3`。
异常类型固定为 `ChromaWriteLockTimeout(RuntimeError)`（`:50`）。两次复跑逐字输出：

跨进程：

```
run1: xproc_elapsed_s = 0.302
      xproc_msg = chroma write lock not acquired within 0.3s (another process holds /tmp/b5-lock-probe-i22fjm87/data/chroma_write.lock) holder=pid=799660 (alive) token=799660:1792601305797393604
run2: xproc_elapsed_s = 0.303
      xproc_msg = chroma write lock not acquired within 0.3s (another process holds /tmp/b5-lock-probe-bt5fl0oh/data/chroma_write.lock) holder=pid=801487 (alive) token=801487:1792601402035239499
```

进程内：

```
run1: thread_elapsed_s = 0.300
      thread_msg = chroma write lock not acquired within 0.3s (another thread in this process holds it; same-process contention) holder=thread:MainThread (same process)
run2: thread_elapsed_s = 0.301
      thread_msg = chroma write lock not acquired within 0.3s (another thread in this process holds it; same-process contention) holder=thread:MainThread (same process)
```

两处报文都在预算（0.3 s）附近抛出（0.300 ~ 0.303 s），而**不是**在默认 60 s——说明预算真的生效。
`holder=pid=… (alive)` 的 pid 是持有者子进程，`(alive)` 与该进程当时仍在相符（§2.5 说明
`holder=thread:` 的名字取自等待方）。

### 5.5 默认值实读（本轮实测）

命令（在仓根跑；四行输出对应四条解析规则）：

```bash
cd ~/src/MimirAether && ~/src/MimirAether/.venv/bin/python3 - <<'PY'
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "src" / "MimirAether"))
os.environ.pop("MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S", None)
import tools.chroma_session_indexer as csi
print("DEFAULT_WRITE_LOCK_TIMEOUT_S =", csi.DEFAULT_WRITE_LOCK_TIMEOUT_S)
print("unset      ->", csi._write_lock_timeout_s())
os.environ["MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S"] = "12.5"
print("env=12.5   ->", csi._write_lock_timeout_s())
os.environ["MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S"] = "not-a-number"
print("env=bad    ->", csi._write_lock_timeout_s())
PY
```

读数（逐字）：

```
DEFAULT_WRITE_LOCK_TIMEOUT_S = 60.0
unset      -> 60.0
env=12.5   -> 12.5
env=bad    -> 60.0
（stderr 同行: bad MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S='not-a-number', using 60.0s）
```

⇒ 文档写的默认值（60.0 s，§3.1）与代码实际值一致；非法值回落默认且不抛错，与 §3.1 解析规则一致。
（§5.6 探针只覆盖前两行：`DEFAULT_WRITE_LOCK_TIMEOUT_S = 60.0` 与 `unset_reads = 60.0`。）

### 5.6 复跑探针（整段可直接跑，不写生产数据）

所有臂都把 `MIMIR_AETHER_HOME` 指向临时目录，锁文件落在临时目录下，不碰线上 chroma。

```bash
cd ~/src/MimirAether && ~/src/MimirAether/.venv/bin/python3 - <<'PY'
import os, signal, statistics, subprocess, sys, tempfile, threading, time
from pathlib import Path
REPO = Path.home() / "src" / "MimirAether"
sys.path.insert(0, str(REPO))
HOLD = ("import sys,time\nsys.path.insert(0,%r)\nimport tools.chroma_session_indexer as csi\n"
        "with csi.chroma_write_lock():\n    print('held',flush=True)\n    time.sleep(float(sys.argv[1]))\n") % str(REPO)
tmp = Path(tempfile.mkdtemp(prefix="b5-lock-probe-"))
os.environ["MIMIR_AETHER_HOME"] = str(tmp)
import tools.chroma_session_indexer as csi

def hold(sec):
    env = dict(os.environ); env["MIMIR_AETHER_HOME"] = str(tmp); env["MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S"] = "30"
    p = subprocess.Popen([sys.executable, "-c", HOLD, str(sec)], cwd=str(REPO), env=env, stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "held"; return p

print("lock_file =", csi.chroma_write_lock_path())
print("DEFAULT_WRITE_LOCK_TIMEOUT_S =", csi.DEFAULT_WRITE_LOCK_TIMEOUT_S)
print("poll_s =", csi._WRITE_LOCK_POLL_S, "unset_reads =", csi._write_lock_timeout_s())
lat = []
for _ in range(5):
    p = hold(30); p.send_signal(signal.SIGKILL); p.communicate(timeout=30)
    os.environ["MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S"] = "5"
    t0 = time.monotonic()
    with csi.chroma_write_lock(): pass
    lat.append(time.monotonic() - t0)
print("sigkill_release_s trials =", [round(x,4) for x in lat], "median = %.4f" % statistics.median(lat))
p = hold(30)
try:
    os.environ["MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S"] = "0.3"; t0 = time.monotonic()
    try:
        with csi.chroma_write_lock(): pass
    except csi.ChromaWriteLockTimeout as e:
        print("xproc_elapsed_s = %.3f" % (time.monotonic()-t0)); print("xproc_msg =", e)
finally:
    os.environ["MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S"] = "30"; p.kill(); p.communicate(timeout=30)
held, rel = threading.Event(), threading.Event()
def th_hold():
    with csi.chroma_write_lock(): held.set(); rel.wait(10)
th = threading.Thread(target=th_hold, name="probe-holder", daemon=True); th.start()
assert held.wait(5.0)
os.environ["MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S"] = "0.3"; t0 = time.monotonic()
try:
    with csi.chroma_write_lock(): print("thread_arm = NO TIMEOUT (unexpected)")
except csi.ChromaWriteLockTimeout as e:
    print("thread_elapsed_s = %.3f" % (time.monotonic()-t0)); print("thread_msg =", e)
finally:
    os.environ["MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S"] = "30"; rel.set(); th.join(timeout=10)
PY
```

预期读数 = §5.1 / §5.4 / §5.5 三个读数块；`lock_file` 应指向 `/tmp/b5-lock-probe-*/data/chroma_write.lock`。

### 5.7 用例（基线，不许退化）

重跑命令: `cd ~/src/MimirAether && env -u MIMIR_CHROMA_INCREMENTAL ~/src/MimirAether/.venv/bin/python3 -m pytest tests/tools/test_chroma_write_lock.py tests/tools/test_chroma_session_indexer.py -q`
复算数字: `26 passed`（本轮实测 26 passed, 1 warning in 12.49s）

（`env -u MIMIR_CHROMA_INCREMENTAL` 是必要的：交互 shell 可能继承 `MIMIR_CHROMA_INCREMENTAL=0`，
会让「默认 True」类断言假红。）

---

## 6. 改动史

| 阶段 | commit | 内容 | 复取命令 |
|---|---|---|---|
| B0 | `c5dc61b` | 立闸：跨进程 flock 旁车锁 + `ChromaWriteLockTimeout`；2/4 进程互斥实测由 46/128 重叠窗口 → 0 | `git log -1 --format=%B c5dc61b` |
| B1 | `a3a8a57` | 收口 6 处未加锁 delete/probe 站点：`guards=4 unguarded=6` → `guards=10 unguarded=0` | `git log -1 --format=%B a3a8a57` |
| B2 | `7ed66a0` | 嵌入计算移出锁（锁只覆盖写）：锁内 35.1 s/35.2 s → ~0.07 s | `git log -1 --format=%B 7ed66a0` |
| B3 | `2e92c75` | 进程内 `RLock` 等待加 deadline（此前 `acquire()` 无超时，实测 1.80 s vs 0.3 s 预算） | `git log -1 --format=%B 2e92c75` |
| B4 | `ffbbe75` | 超时报文点名持有者（`holder=pid=… (alive\|gone\|unknown) token=…` / `holder=thread:…`） | `git log -1 --format=%B ffbbe75` |
| B6 | — | 运行态生效：以上代码已 commit，**运行态以重启为准**（`PENDING-SMOKE`，本文件不声明重启已完成） | `git rev-parse HEAD` |
| B9 | —（判据不在 git 内，见 §4.3） | 判据三缺陷修复：nullable 锁单列 + `rc=2`、`--root` 缺省改扫 cwd、两向自检 7→9 臂；判据 sha256 锚点 `ed0c63b8bdb9…` | `sha256sum ~/.mimiraether/gates/verify_chroma_write_coverage.py` |

**当前 HEAD = `56377e6`**；本文件所在工作区改动仅 `docs/chroma_write_lock.md`。
