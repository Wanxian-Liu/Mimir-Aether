#!/usr/bin/env python3
"""闸 A：SLO 看板 ② 与 ⑤ 两段在同一 days 参数下必须数到同一批 turn（2026-11-08）

## 为什么要有这道闸

看板同一个「近 7 天」印出两个不同的 turn 数。实证定位到两个轴各差一处：

| 段 | 读数函数 | 数据源 | 窗口边界 |
|:--|:--|:--|:--|
| ② 滚动窗口 | parse_log(days) | open(LOG_FILE) 单文件 | ts >= now - days*24h（168h 滚动）|
| ⑤ 效率段 | _efficiency_stats(days) | glob(LOG_GLOB) 含 agent.log.1/2/3 轮转档 | day >= (now-days).strftime('%Y-%m-%d')（日历日字符串）|

两个轴都不一致 => 两个数不可比，但看板把它们并列在同一份报告里，读者会当成同口径。

## 判据存活性

TURN_RE 与 EFF_TURN_RE 实测命中同一批行（全量 132464 行，各 12252，交集 12252）
=> 「两数应当相等」成立。若两条正则分家，--selftest 的 line-class 检查会先红，
不会把「指标不同」误报成「漂移」。

## rc 语义（三态：漂移 != 仪表故障）

0 一致（含两边都 0，防恒红） / 1 不一致 = 口径漂移 / 2 读盘或导入故障
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


def measure(days=7):
    """返回 (② 数到的 turn 数, ⑤ 数到的 turn 数)。"""
    turns, _sessions = slo.parse_log(days)
    eff_turns, _single, _ptok = slo._efficiency_stats(days)
    return len(turns), sum(eff_turns.values())


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
    """两向 + 两轴自检。返回 rc（0 全过 / 1 有控制组不符预期）。"""
    now = datetime(2026, 11, 8, 10, 0, 0)
    results = []

    # 正控：隔离单文件 + turn 在 24h 内 => 两轴都不触发，必须一致
    with _fixture({"agent.log": _turn_line(now - timedelta(hours=3))}, now):
        a, b = measure(7)
    results.append(("正控 单文件+近窗口 应一致", a, b, a == b))

    # 负控一（窗口轴）：173h 前 = 落在 168h 外，但日期 11-01 >= 11-01 落在日历窗内
    #   ② 丢 / ⑤ 收 => 必须不等
    with _fixture({"agent.log": _turn_line(datetime(2026, 11, 1, 5, 0, 0))}, now):
        a, b = measure(7)
    results.append(("负控一 窗口轴 应不一致", a, b, a != b))

    # 负控二（数据源轴）：主档 1 条 + 轮转档 1 条，都在 24h 内
    #   ② 只读主档=1 / ⑤ glob 到 2 => 必须不等
    with _fixture({
        "agent.log": _turn_line(now - timedelta(hours=3)),
        "agent.log.1": _turn_line(now - timedelta(hours=4), tid="bbbbbbbb"),
    }, now):
        a, b = measure(7)
    results.append(("负控二 数据源轴 应不一致", a, b, a != b))

    # 边界：两边都 0 必须判一致（防「空窗口恒红」的反向假绿/假红）
    with _fixture({"agent.log": _turn_line(datetime(2020, 1, 1, 0, 0, 0))}, now):
        a, b = measure(7)
    results.append(("边界 双向零数据 应一致", a, b, a == b))

    # 判据存活性：两条正则须命中同一批行
    n_turn, n_eff, n_both = probe_same_line_class()
    same = (n_turn == n_eff == n_both) and n_turn > 0
    results.append(("判据 两正则同行类", n_turn, n_eff, same))

    ok = True
    for name, a, b, passed in results:
        flag = "PASS" if passed else "FAIL"
        print(f"[{flag}] {name}: a={a} b={b}")
        ok = ok and passed
    print(f"selftest: {sum(1 for r in results if r[3])}/{len(results)} PASS")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    days = 7
    for i, a in enumerate(argv):
        if a == "--days" and i + 1 < len(argv):
            days = int(argv[i + 1])
    try:
        n_rolling, n_bucket = measure(days)
    except Exception as exc:  # 仪表故障 != 漂移
        print(f"[口径一致闸] rc=2 读盘/导入故障: {type(exc).__name__}: {exc}")
        return 2
    delta = n_bucket - n_rolling
    print(f"[口径一致闸] ② parse_log({days}) n={n_rolling}")
    print(f"[口径一致闸] ⑤ _efficiency_stats({days}) n={n_bucket}")
    print(f"[口径一致闸] delta={delta:+d}")
    if n_rolling == n_bucket:
        print("[口径一致闸] PASS 两段同源同界")
        return 0
    print("[口径一致闸] DRIFT 两段读数不等 —— 数据源或窗口边界不一致"
          "（②单文件+168h滚动 / ⑤glob含转档+日历日字符串）")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
