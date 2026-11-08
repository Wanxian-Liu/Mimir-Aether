"""闸 A 用例（2026-11-08 · D1/D2/D3 口径统一后重写）

控制组分工（每一组都防一个具体的假绿/假红）：

| 用例 | 防什么 |
|:--|:--|
| 正控 单文件窗口内 | 闸恒红（实现坏了永远报不等） |
| D2 收档同源 | ② 偷回单文件口径（改前 ② 只数 1，⑤ 数 2） |
| 负控 造 1 条偏差 | 闸对真实偏离失明（漂移报不出来） |
| D3 空目录 / 日志真空 | **数据缺失被印成 0 = 假绿**（本次 D3 的主目标） |
| 边界 窗口内无采样点 | 把「没流量」误判成「无法判定」 |
| rc 报出层两向 | main() 接线短路（永远 rc=0 或永远 rc≠0） |
| 真实日志 ratchet | 两段在真数据上必须相等（改前 1472 vs 1806 的已知漂移） |
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import check_window_parity as gate  # noqa: E402


NOW = datetime(2026, 11, 8, 10, 0, 0)


def test_positive_control_single_file_recent_agrees():
    """正控：隔离单文件 + 窗口内 ⇒ 两段都数到 1、rc=0。

    防「闸恒红」——若闸实现坏了永远报不等，它就红。
    """
    with gate._fixture({"agent.log": gate._turn_line(NOW - timedelta(hours=3))}, NOW):
        rc, rolling, bucket, _detail = gate.evaluate(7)
    assert (rolling, bucket) == (1, 1)
    assert rc == 0


def test_d2_rotation_files_counted_by_both():
    """D2 正控：主档 + 轮转档都在窗口内 ⇒ 两段都必须数到 2（同源）。

    改前 ② 只 open(LOG_FILE)=1、⑤ glob=2 ⇒ delta=1；这条锁住「② 别偷回单文件口径」。
    """
    with gate._fixture({
        "agent.log": gate._turn_line(NOW - timedelta(hours=3)),
        "agent.log.1": gate._turn_line(NOW - timedelta(hours=4), tid="bbbbbbbb"),
    }, NOW):
        rc, rolling, bucket, _detail = gate.evaluate(7)
    assert (rolling, bucket) == (2, 2)
    assert rc == 0


def test_negative_one_line_drift_detected():
    """负控（造 1 条偏差）：大写 tid 行只有 ⑤ 命中 ⇒ 两段差 1 ⇒ 必须 rc=1。

    这是「闸有鉴别力」的最小样本：不是造两套窗口，而是造**同一份数据里 1 行不可比**。
    """
    with gate._fixture({
        "agent.log": gate._turn_line(NOW - timedelta(hours=3)),
        "agent.log.1": gate._turn_line(NOW - timedelta(hours=4), tid="AAAAAAAA"),
    }, NOW):
        rc, rolling, bucket, _detail = gate.evaluate(7)
    assert bucket - rolling == 1
    assert rc == 1


def test_d3_empty_dir_is_undecidable_not_zero():
    """D3 负控一：空目录（glob 无文件）⇒ rc=2，**绝不是 0**。

    这是本次最重要的一条：旧实现下空目录会被印成「PASS 两段同源同界」（两边都 0），
    把「仪表没接上数据」读成「口径一致」= 假绿。
    """
    with gate._fixture({}, NOW):
        rc, rolling, bucket, detail = gate.evaluate(7)
    assert rc == 2, detail
    assert (rolling, bucket) == (None, None)


def test_d3_log_vacuum_is_undecidable_not_zero():
    """D3 负控二：文件在但 0 行（日志真空）⇒ rc=2，不是 0。"""
    with gate._fixture({"agent.log": ""}, NOW):
        rc, rolling, bucket, detail = gate.evaluate(7)
    assert rc == 2, detail
    assert (rolling, bucket) == (None, None)


def test_boundary_no_sample_in_window_is_agreement():
    """边界：数据存在但窗口内无采样点 ⇒ 两边同为 0，判一致 rc=0（不是无法判定）。"""
    with gate._fixture({"agent.log": gate._turn_line(datetime(2020, 1, 1, 0, 0, 0))}, NOW):
        rc, rolling, bucket, _detail = gate.evaluate(7)
    assert (rolling, bucket) == (0, 0)
    assert rc == 0


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
    """rc 报出层负控：漂移必须变成 rc=1（selftest 验 measure 层，本条验 main 接线）。"""
    with gate._fixture({
        "agent.log": gate._turn_line(NOW - timedelta(hours=3)),
        "agent.log.1": gate._turn_line(NOW - timedelta(hours=4), tid="AAAAAAAA"),
    }, NOW):
        assert gate.main([]) == 1


def test_main_rc_reports_agreement():
    """rc 报出层正控：两段一致必须 rc=0（防 main() 接线短路成永远非 0 ⇒ 恒红）。"""
    with gate._fixture({"agent.log": gate._turn_line(NOW - timedelta(hours=3))}, NOW):
        assert gate.main([]) == 0


def test_main_rc_reports_undecidable_on_empty_dir():
    """rc 报出层 D3：空目录必须 rc=2（不是 0 也不是 1）。"""
    with gate._fixture({}, NOW):
        assert gate.main([]) == 2


def test_live_log_parity():
    """真实日志上两段必须相等（ratchet）。

    改前实测 ② n=1472 / ⑤ n=1806（delta +334）；D1+D2 收敛后必须 delta=0。
    数据源不存在时本闸应报 rc=2 —— 因此本条在无日志环境会红，这是**有意的**：
    真数据 parity 不能被「没数据」蒙过去。
    """
    rc, rolling, bucket, detail = gate.evaluate(7)
    assert rc == 0, f"rc={rc} {detail} ② n={rolling} ⑤ n={bucket}"
    assert rolling == bucket
