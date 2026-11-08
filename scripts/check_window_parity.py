#!/usr/bin/env python3
"""闸 A：SLO 看板 ② 与 ⑤ 两段必须数到同一批 turn（2026-11-08）

## 为什么要有这道闸

看板同一个窗口印出两个不同的 turn 数。实证定位到两个轴各差一处：

| 段 | 读数函数 | 数据源（改前） | 窗口边界（改前） |
|:--|:--|:--|:--|
| ② 滚动窗口 | parse_log(days) | open(LOG_FILE) 单文件 | ts >= now - days*24h（168h 滚动）|
| ⑤ 效率段 | _efficiency_stats(days) | glob(LOG_GLOB) 含 agent.log.1/2/3 轮转档 | day >= (now-days).strftime('%Y-%m-%d')（日历日字符串）|

两个轴都不一致 => 两个数不可比，但看板把它们并列在同一份报告里，读者会当成同口径。

## 2026-11-08 D1/D2 修法（裁决后执行）

- D2 数据源：② 改为与 ⑤ 同为 `agent.log*`（含轮转档）
- D1 窗口：⑤ 改为滚动小时窗（与 ② 同界 168h），不再按日历日字符串比
=> 两轴收敛后，两段读数**应当逐字相等**，本闸才有鉴别力。

## 判据存活性

TURN_RE 与 EFF_TURN_RE 实测命中同一批行（168h 窗口内 turn=1746 / eff=1746 / both=1746）
=> 「两数应当相等」成立。若两条正则分家，probe_same_line_class() 会先红，
不会把「指标不同」误报成「漂移」。

## rc 语义（三态 · D3 2026-11-08）

- `0` 一致（含「数据源存在但窗口内无采样点」⇒ 两边同为 0）
- `1` 不一致 = 口径漂移
- `2` **无法判定**：空目录 / 日志真空（0 行）/ 读盘或导入故障

**数据缺失禁落 0**：无文件、无行都必须 rc=2 —— 旧实现下「两边都是 0」会被印成 PASS，
把「仪表没接上数据」读成「口径一致」（假绿），这正是本闸要防的主要事故。
"""
import importlib.util
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_slo():
    spec = importlib.util.spec_from_file_location(
        "slo_dashboard", REPO / "scripts" / "slo_dashboard.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["slo_dashboard"] = mod
    spec.loader.exec_module(mod)
    return mod


slo = _load_slo()


@contextmanager
def _frozen_lines():
    """一次性快照：本次判定只读一遍日志，两段各在**同一份**行上计数。

    为什么必须有它（2026-11-08 复跑反馈实证）：闸不是原子快照 —— ② 与 ⑤ 各自
    重新 `_iter_log_lines()`，两段之间 gateway 若又写进一条 turn，⑤ 就比 ② 多一条
    ⇒ delta=+1 ⇒ 报 DRIFT（假红）。同一天里同一检查器一会儿红一会儿绿，红的时候
    说明不了任何事。只共享 anchor 只封得住「窗口边界滑移」，封不住「运行期追加」；
    封追加只能靠**读一份**。
    """
    lines = list(slo._iter_log_lines())
    saved = slo._iter_log_lines
    slo._iter_log_lines = lambda: iter(lines)
    try:
        yield lines
    finally:
        slo._iter_log_lines = saved


def measure(days=7, anchor=None, between=None):
    """返回 (② 数到的 turn 数, ⑤ 数到的 turn 数)。

    两条不变量（假红的两个来源，逐条封死）：
    1. **单锚点**：一次运行只取一次 now()，显式传给两段 —— 两段 cutoff 同界；
    2. **单快照**：两段读同一份行列表 —— 两段之间新写入的 turn 不参与本次判定。

    `between` 仅供控制组打桩：第一段算完、第二段算之前执行（模拟「两段之间插入
    一条 turn」），真实路径传 None。
    """
    if anchor is None:
        anchor = slo.datetime.now()   # ← 全函数只有这一处取 now()
    with _frozen_lines():
        turns, _sessions = slo.parse_log(days, anchor=anchor)
        if between is not None:
            between()
        eff_turns, _single, _ptok = slo._efficiency_stats(days, anchor=anchor)
    return len(turns), sum(eff_turns.values())


def source_presence():
    """数据源在场判据——返回 (文件数, 总行数)。D3：任一为 0 = 无法判定。"""
    files = slo._log_source_files()
    lines = 0
    for _ in slo._iter_log_lines():
        lines += 1
    return len(files), lines


def evaluate(days=7, between=None):
    """单点判定（main 与 selftest 共用）——返回 (rc, n_rolling, n_bucket, detail)。"""
    n_files, n_lines = source_presence()
    if n_files == 0:
        return (2, None, None,
                "无法判定：数据源为空目录（glob 无文件——日志未生成或被清理）")
    if n_lines == 0:
        return (2, None, None,
                "无法判定：日志真空（%d 个文件 0 行——无采样点可比）" % n_files)
    try:
        n_rolling, n_bucket = measure(days, between=between)
    except Exception as exc:  # 仪表故障 != 漂移 != 数据缺失
        return (2, None, None,
                "无法判定：读盘/导入故障 %s: %s" % (type(exc).__name__, exc))
    if n_rolling == n_bucket:
        detail = "一致" if n_rolling else "一致（数据源存在，但窗口内无采样点）"
        return (0, n_rolling, n_bucket, detail)
    return (1, n_rolling, n_bucket, "偏离")


def _turn_line(ts, tid="aaaaaaaa", n=1):
    """造一行能被 TURN_RE 与 EFF_TURN_RE 同时命中的日志行。"""
    return (f"{ts.strftime('%Y-%m-%d %H:%M:%S')},000 INFO agent.agent_loop: "
            f"[{tid}] turn {n}: api=1.0s, 1 tools, total=2.0s\n")


class _FakeDatetime(datetime):
    """冻结 now()，否则控制组判别力随跑测试的钟点漂移。"""

    _frozen = datetime(2026, 11, 8, 10, 0, 0)

    @classmethod
    def now(cls, tz=None):
        return cls._frozen


@contextmanager
def _fixture(files, frozen_now=None):
    """把 LOG_FILE / LOG_GLOB 指到临时目录，跑完还原（不污染真实读数）。"""
    saved = (slo.LOG_FILE, slo.LOG_GLOB, slo.datetime)
    tmp = tempfile.mkdtemp(prefix="slo_parity_")
    try:
        for name, content in files.items():
            Path(tmp, name).write_text(content, encoding="utf-8")
        slo.LOG_FILE = os.path.join(tmp, "agent.log")
        slo.LOG_GLOB = os.path.join(tmp, "agent.log*")
        if frozen_now is not None:
            _FakeDatetime._frozen = frozen_now
            slo.datetime = _FakeDatetime
        yield tmp
    finally:
        slo.LOG_FILE, slo.LOG_GLOB, slo.datetime = saved


def probe_same_line_class():
    """判据存活性：两条正则必须命中同一批行，否则「应相等」前提不成立。"""
    n_turn = n_eff = n_both = 0
    for line in slo._iter_log_lines():
        a = bool(slo.TURN_RE.search(line))
        b = bool(slo.EFF_TURN_RE.match(line))
        n_turn += a
        n_eff += b
        n_both += (a and b)
    return n_turn, n_eff, n_both


def selftest():
    """三态 + 两向自检。返回 rc（0 全过 / 1 有控制组不符预期）。"""
    now = datetime(2026, 11, 8, 10, 0, 0)
    results = []  # (名字, 期望 rc, 实得 rc, 期望 n 对, 实得 n 对)

    # 正控：单文件 + turn 在窗口内 => 两段一致，rc=0
    with _fixture({"agent.log": _turn_line(now - timedelta(hours=3))}, now):
        rc, a, b, _d = evaluate(7)
    results.append(("正控 单文件+窗口内 应一致 rc=0", 0, rc, (1, 1), (a, b)))

    # 抖动负控一（2026-11-08 复跑反馈 · 你抓到的那次假红）：两段之间插入一条新 turn
    # 快照不成立时 ⑤ 会比 ② 多一条 => delta=+1 => 假 DRIFT。修后仍须 rc=0。
    with _fixture({"agent.log": _turn_line(now - timedelta(hours=3))}, now) as _tmp:
        def _inject(_d=_tmp):
            with open(os.path.join(_d, "agent.log"), "a", encoding="utf-8") as fh:
                fh.write(_turn_line(now - timedelta(hours=1), tid="cccccccc"))
        rc, a, b, _d = evaluate(7, between=_inject)
    results.append(("抖动负控 两段间插入 1 条 turn 应仍一致 rc=0", 0, rc, (1, 1), (a, b)))

    # 抖动负控二：让 now() 每次调用前进 2h（模拟两次独立取锚）。
    # 一行落在 now-167h：对 anchor=now 在窗内、对 anchor=now+2h 已在窗外
    # => 两段各取现在时 delta=-1（假 DRIFT）。单锚点后两段同界 => 一致。
    class _AdvancingDatetime(datetime):
        _n = 0

        @classmethod
        def now(cls, tz=None):
            cls._n += 1
            return now + timedelta(hours=(cls._n - 1) * 2)

    with _fixture({"agent.log": _turn_line(now - timedelta(hours=167))}, None):
        slo.datetime = _AdvancingDatetime
        rc, a, b, _d = evaluate(7)
    results.append(("抖动负控 两次取锚各不同 应仍一致 rc=0", 0, rc, (1, 1), (a, b)))

    # D2 收档正控：主档 + 轮转档都在窗口内 => 两边都要数到 2（改前 ② 只数 1）
    with _fixture({
        "agent.log": _turn_line(now - timedelta(hours=3)),
        "agent.log.1": _turn_line(now - timedelta(hours=4), tid="bbbbbbbb"),
    }, now):
        rc, a, b, _d = evaluate(7)
    results.append(("D2 收档同源 应一致 rc=0", 0, rc, (2, 2), (a, b)))

    # 负控（造 1 条偏差）：大写 tid 行 => TURN_RE 不命中，EFF_TURN_RE 命中 => 偏离 rc=1
    with _fixture({
        "agent.log": _turn_line(now - timedelta(hours=3)),
        "agent.log.1": _turn_line(now - timedelta(hours=4), tid="AAAAAAAA"),
    }, now):
        rc, a, b, _d = evaluate(7)
    delta = None if (a is None or b is None) else b - a
    results.append(("负控 造 1 条偏差 应 rc=1", 1, rc, 1, delta))

    # D3 负控一：空目录（无文件）=> 无法判定 rc=2，绝不是 0
    with _fixture({}, now):
        rc, a, b, _d = evaluate(7)
    results.append(("D3 负控 空目录 应 rc=2", 2, rc, (None, None), (a, b)))

    # D3 负控二：日志真空（文件存在但 0 行）=> 无法判定 rc=2
    with _fixture({"agent.log": ""}, now):
        rc, a, b, _d = evaluate(7)
    results.append(("D3 负控 日志真空 应 rc=2", 2, rc, (None, None), (a, b)))

    # 边界：数据存在但窗口内无采样点 => 两边同为 0，判一致 rc=0（不是无法判定）
    with _fixture({"agent.log": _turn_line(datetime(2020, 1, 1, 0, 0, 0))}, now):
        rc, a, b, _d = evaluate(7)
    results.append(("边界 窗口内无采样点 应一致 rc=0", 0, rc, (0, 0), (a, b)))

    # 判据存活性：两条正则须命中同一批行
    n_turn, n_eff, n_both = probe_same_line_class()
    same = (n_turn == n_eff == n_both) and n_turn > 0
    results.append(("判据 两正则同行类", True, same, True, same))

    ok = True
    for name, want_rc, got_rc, want_n, got_n in results:
        passed = (want_rc == got_rc) and (want_n == got_n)
        flag = "PASS" if passed else "FAIL"
        print(f"[{flag}] {name}: want_rc={want_rc} rc={got_rc} want_n={want_n} n={got_n}")
        ok = ok and passed
    print(f"selftest: {sum(1 for r in results if r[1] == r[2] and r[3] == r[4])}/{len(results)} PASS")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    days = 7
    for i, a in enumerate(argv):
        if a == "--days" and i + 1 < len(argv):
            days = int(argv[i + 1])
    rc, n_rolling, n_bucket, detail = evaluate(days)
    if rc == 2:
        print(f"[口径一致闸] rc=2 {detail}")
        return 2
    print(f"[口径一致闸] ② parse_log({days}) n={n_rolling}")
    print(f"[口径一致闸] ⑤ _efficiency_stats({days}) n={n_bucket}")
    print(f"[口径一致闸] delta={n_bucket - n_rolling:+d}")
    if rc == 0:
        print(f"[口径一致闸] PASS 两段同源同界（{detail}）")
        return 0
    print("[口径一致闸] DRIFT 两段读数不等 —— 数据源或窗口边界不一致"
          "（② agent.log* + 168h 滚动 / ⑤ agent.log* + 168h 滚动）")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
