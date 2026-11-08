"""闸 A 用例（2026-11-08）：② 与 ⑤ 同 days 下读数必须相等。

三个控制组证明闸**有鉴别力**（该红能红、该绿能绿、两轴分得开），
一个 ratchet 用例锁住真实数据的已知漂移（修好后会自动变 XPASS 逼人摘标记）。
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import check_window_parity as gate  # noqa: E402


NOW = datetime(2026, 11, 8, 10, 0, 0)


def test_positive_control_single_file_recent_agrees():
    """正控：隔离单文件 + 窗口内 ⇒ 两轴都不触发 ⇒ 必须相等。

    这条防「闸恒红」——若闸实现坏了永远报不等，它就红。
    """
    with gate._fixture({"agent.log": gate._turn_line(NOW - timedelta(hours=3))}, NOW):
        rolling, bucket = gate.measure(7)
    assert rolling == bucket == 1


def test_negative_window_axis_detected():
    """负控一（窗口轴）：turn 在 168h 外但同一日历日内 ⇒ 必须被检出不等。

    173h 前 = 11-01 05:00（相对 11-08 10:00）：② 按 168h 丢，⑤ 按日期 >= 11-01 收。
    """
    with gate._fixture({"agent.log": gate._turn_line(datetime(2026, 11, 1, 5, 0, 0))}, NOW):
        rolling, bucket = gate.measure(7)
    assert rolling == 0
    assert bucket == 1
    assert rolling != bucket


def test_negative_source_axis_detected():
    """负控二（数据源轴）：轮转档里有 turn ⇒ 必须被检出不等。

    ② 只 open(LOG_FILE) 读到 1；⑤ glob 到 agent.log* 读到 2。
    """
    with gate._fixture({
        "agent.log": gate._turn_line(NOW - timedelta(hours=3)),
        "agent.log.1": gate._turn_line(NOW - timedelta(hours=4), tid="bbbbbbbb"),
    }, NOW):
        rolling, bucket = gate.measure(7)
    assert rolling == 1
    assert bucket == 2


def test_both_empty_is_agreement():
    """边界：两边都是 0 必须判一致（防「空窗口恒红」把无数据读成漂移）。"""
    with gate._fixture({"agent.log": gate._turn_line(datetime(2020, 1, 1, 0, 0, 0))}, NOW):
        rolling, bucket = gate.measure(7)
    assert rolling == bucket == 0


def test_both_regexes_hit_same_line_class():
    """判据存活性：两条正则必须命中同一批行。

    否则「两数应相等」这个前提本身不成立，闸 A 就成了拿两个不同指标比大小。
    """
    n_turn, n_eff, n_both = gate.probe_same_line_class()
    assert n_turn > 0, "日志里没有 turn 行 —— 判据无法自证"
    assert n_turn == n_eff == n_both


def test_selftest_all_green():
    """把 --selftest 全跑一遍（命令行口径与用例口径必须一致）。"""
    assert gate.selftest() == 0


def test_main_rc_reports_drift():
    """rc 报出层负控（2026-11-08 统筹席指出：selftest 只验到 measure 层）：漂移必须变成 rc=1。

    selftest / measure 用例断言的是 `a != b`（漂移**数得出来**）；
    本条断言的是 `main()` 的 rc（漂移**报得出来**）——两件事，中间隔着 main() 的打印与 return 接线。
    """
    with gate._fixture({"agent.log": gate._turn_line(datetime(2026, 11, 1, 5, 0, 0))}, NOW):
        assert gate.main([]) == 1


def test_main_rc_reports_agreement():
    """rc 报出层正控：两段一致必须 rc=0（防 main() 接线短路成永远非 0 ⇒ 恒红）。"""
    with gate._fixture({"agent.log": gate._turn_line(NOW - timedelta(hours=3))}, NOW):
        assert gate.main([]) == 0


@pytest.mark.xfail(
    strict=True,
    reason="已知漂移：② 单文件+168h滚动 vs ⑤ glob含转档+日历日字符串。"
           "修好后本用例会 XPASS ⇒ suite 变红 ⇒ 必须摘掉本标记（ratchet）。",
)
def test_live_log_parity():
    """真实日志上两段必须相等。当前不成立（1353 vs 1687）——这就是要修的东西。"""
    rolling, bucket = gate.measure(7)
    assert rolling == bucket, f"② n={rolling} != ⑤ n={bucket}"
