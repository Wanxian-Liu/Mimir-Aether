"""退出表补盲区（2026-09-28）用例。

背景：``record_exit_event`` 只在进程**自己的停机路径**上被调用 ⇒ 对
SIGKILL/OOM（不可捕获信号）天然全盲。实测 2026-09-27 22:49:50 gateway 被
cgroup OOM 杀掉：journal 有 "killed by the OOM killer" + "Failed with result
'oom-kill'"，而退出表 **0 行**。本文件钉住对账函数三条性质：
缺行能补、有行不重、坏行不炸。
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

UNIT = "mimiraether.service"


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_HOME", raising=False)
    import gateway.exit_record as er

    return er, tmp_path


def _jl(epoch: int, msg: str) -> str:
    return json.dumps({"__REALTIME_TIMESTAMP": str(epoch * 1000000), "MESSAGE": msg})


OOM_AT = 1790554560
OOM_KILLER = _jl(OOM_AT, UNIT + ": A process of this unit has been killed by the OOM killer.")
OOM_RESULT = _jl(OOM_AT + 1, UNIT + ": Failed with result 'oom-kill'.")
OOM_PEAK = _jl(
    OOM_AT + 1,
    UNIT + ": Consumed 2h 7min 52.118s CPU time, 4.0G memory peak, 408.0K memory swap peak.",
)


def _reader(lines):
    def _r(unit, since_epoch, limit):
        return list(lines)

    return _r


def _prewrite(er, epoch: int, reason: str) -> None:
    """预写一条「运行时自己记过」的行。"""
    path = er.history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "ts_epoch": epoch,
                    "ts": "2026-09-27T22:49:00+0800",
                    "event": "exit",
                    "pid": 91870,
                    "source": "signal:SIGTERM",
                    "exit_reason": "Gateway restart requested",
                }
            )
            + chr(10)
        )


# ---------------------------------------------------------------- 正控：缺行能补
def test_missed_oom_is_reconciled(home):
    """journal 有 OOM、表里没有 ⇒ 必须补一行（本条是本文件的**正控**）。"""
    er, _ = home
    added = er.reconcile_from_journal(
        unit=UNIT, read_lines=_reader([OOM_KILLER, OOM_RESULT, OOM_PEAK])
    )
    assert len(added) == 1, added
    rec = added[0]
    assert rec["exit_reason"] == "oom-kill"
    assert rec["source"] == "journal-reconcile"
    assert rec["rss_peak_mb"] == 4096.0  # "4.0G memory peak"
    assert rec["pid"] is None  # 死法不可捕获 ⇒ 无 pid 可记
    assert "不可捕获信号" in rec["note"]
    rows = er.read_records()
    assert len(rows) == 1 and rows[0]["exit_reason"] == "oom-kill"


def test_parse_merges_oom_pair_into_one_event(home):
    """OOM killer 行 + Failed with result 行 ⇒ 合并成 1 个事件，不重复。"""
    er, _ = home
    ev = er.parse_journal_exits([OOM_KILLER, OOM_RESULT, OOM_PEAK])
    assert len(ev) == 1, ev
    assert ev[0]["reason"] == "oom-kill"
    assert ev[0]["ts_epoch"] == OOM_AT


# ------------------------------------------------------- 负控：有行不重（差分对）
def test_already_recorded_event_is_not_duplicated(home):
    """表里那条时间点已有记录 ⇒ 不得重复补。与上条构成**受控差分对**。"""
    er, _ = home
    _prewrite(er, OOM_AT + 1, "Gateway restart requested")
    added = er.reconcile_from_journal(unit=UNIT, read_lines=_reader([OOM_KILLER, OOM_RESULT]))
    assert added == [], added
    assert len(er.read_records()) == 1


def test_idempotent_second_call_adds_nothing(home):
    """幂等：连调两次，第二次必须 0 补。"""
    er, _ = home
    first = er.reconcile_from_journal(unit=UNIT, read_lines=_reader([OOM_KILLER]))
    second = er.reconcile_from_journal(unit=UNIT, read_lines=_reader([OOM_KILLER]))
    assert len(first) == 1 and second == []
    assert len(er.read_records()) == 1


def test_event_outside_window_is_still_added(home):
    """窗口外的记录不构成覆盖 ⇒ 仍应补（钉住 window 语义，防「一键静默」）。"""
    er, _ = home
    _prewrite(er, OOM_AT - 4000, "Gateway restart requested")
    added = er.reconcile_from_journal(
        unit=UNIT, read_lines=_reader([OOM_KILLER]), window_s=180
    )
    assert len(added) == 1, added


# ---------------------------------------------------------------- 健壮性
def test_empty_journal_writes_nothing(home):
    er, _ = home
    assert er.reconcile_from_journal(unit=UNIT, read_lines=_reader([])) == []
    assert not er.history_path().exists()


def test_malformed_lines_are_skipped(home):
    er, _ = home
    added = er.reconcile_from_journal(
        unit=UNIT,
        read_lines=_reader(["", "not json{", "[1,2]", json.dumps({"MESSAGE": "hello"})]),
    )
    assert added == []


def test_message_as_byte_array_is_decoded(home):
    """journald 的 MESSAGE 可能是字节数组（非 str）。"""
    er, _ = home
    line = json.dumps(
        {
            "__REALTIME_TIMESTAMP": str(OOM_AT * 1000000),
            "MESSAGE": list(
                (UNIT + ": Failed with result 'oom-kill'.").encode("utf-8")
            ),
        }
    )
    added = er.reconcile_from_journal(unit=UNIT, read_lines=_reader([line]))
    assert len(added) == 1 and added[0]["exit_reason"] == "oom-kill"


def test_bad_reader_never_raises(home):
    """journalctl 抛异常（无 systemd / 权限不足）⇒ 静默 0 补，绝不炸启动路径。"""
    er, _ = home

    def _boom(unit, since_epoch, limit):
        raise RuntimeError("no journalctl")

    assert er.reconcile_from_journal(unit=UNIT, read_lines=_boom) == []


def test_records_readable_after_reconcile(home):
    """补入的行必须能被 read_last_exit / summarize 正常消费（回显路径）。"""
    er, _ = home
    er.reconcile_from_journal(unit=UNIT, read_lines=_reader([OOM_KILLER, OOM_PEAK]))
    last = er.read_last_exit()
    assert last and last["exit_reason"] == "oom-kill"
    assert "oom-kill" in er.summarize(last)


def test_startup_path_calls_reconcile(home):
    """接线闸：启动路径必须真调对账 —— 否则模块再正确，表也会重新变盲区。"""
    import inspect

    import gateway.run as gr

    src = inspect.getsource(gr)
    assert "reconcile_from_journal()" in src, "启动路径未调用对账（表会重新变盲区）"
    assert "Reconciled missed exit from journal" in src, "对账结果未回显（静默补行）"
