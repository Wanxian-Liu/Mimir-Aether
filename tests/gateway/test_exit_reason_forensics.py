"""退出取证（2026-09-27）用例。

背景：``data/gateway_state.json`` 是**单槽** —— 新进程启动即覆盖 gateway_state /
exit_reason，导致 18:33 与 19:03 两次自退在事后无法定因（只剩新进程的 running）。
本模块补一条 append-only 历史，本文件钉住它的三条性质：追加不覆盖、坏行不抛、失败静默。
"""
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_HOME", raising=False)
    import gateway.exit_record as er

    return er, tmp_path


def test_records_are_appended_not_clobbered(home):
    er, _ = home
    er.record_exit_event(exit_reason="first", signal_name="SIGTERM", source="signal:SIGTERM")
    er.record_exit_event(exit_reason="second", signal_name=None, source="unspecified")
    lines = er.history_path().read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2, lines
    assert json.loads(lines[0])["exit_reason"] == "first"
    assert json.loads(lines[1])["exit_reason"] == "second"
    assert er.read_last_exit()["exit_reason"] == "second"


def test_fields_capture_forensic_context(home):
    er, _ = home
    rec = er.record_exit_event(
        exit_reason="Gateway restart requested",
        signal_name="SIGUSR1",
        source="signal:SIGUSR1",
        restart_requested=True,
        active_agents=2,
    )
    for key in ("ts", "pid", "ppid", "signal", "source", "exit_reason",
                "restart_requested", "active_agents", "uptime_s", "rss_peak_mb"):
        assert key in rec, key
    assert rec["signal"] == "SIGUSR1"
    assert rec["restart_requested"] is True
    assert rec["pid"] == os.getpid()
    assert rec["uptime_s"] is None or rec["uptime_s"] >= 0


def test_never_raises_when_home_unwritable(tmp_path, monkeypatch):
    """停机路径上的异常绝不允许冒泡 —— 失败静默返回 None。"""
    import gateway.exit_record as er

    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(blocker / "nested"))
    assert er.record_exit_event(exit_reason="boom") is None
    assert er.read_last_exit() is None


def test_read_last_exit_tolerates_corrupt_tail(home):
    er, _ = home
    er.record_exit_event(exit_reason="ok")
    with open(er.history_path(), "a", encoding="utf-8") as fh:
        fh.write("{not json" + chr(10))
    assert er.read_last_exit() is None
    assert len(er.history_path().read_text(encoding="utf-8").strip().splitlines()) == 2


def test_summarize_is_single_line(home):
    er, _ = home
    rec = er.record_exit_event(exit_reason="r", signal_name="SIGTERM", source="signal:SIGTERM")
    s = er.summarize(rec)
    assert chr(10) not in s and "SIGTERM" in s and "signal:SIGTERM" in s
    assert er.summarize(None) == "no exit record yet"


# ---------------- 鉴别力差分：单槽 state 真丢现场，append-only 历史不丢 ----------------
def test_differential_single_slot_loses_forensics(home):
    er, tmp = home
    er.record_exit_event(exit_reason="why did I die", signal_name="SIGTERM", source="signal:SIGTERM")

    state = tmp / "data" / "gateway_state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"gateway_state": "stopped", "exit_reason": "why did I die"}),
                     encoding="utf-8")
    # 模拟下一次启动：单槽文件被新进程覆盖 ⇒ 该文件已不可用于回溯
    state.write_text(json.dumps({"gateway_state": "running", "exit_reason": None}), encoding="utf-8")
    assert json.loads(state.read_text(encoding="utf-8"))["exit_reason"] is None
    # 而 append-only 历史仍在（这正是本模块存在的理由）
    assert er.read_last_exit()["exit_reason"] == "why did I die"


# ---------------- 结构闸：接线顺序 / 信号名绑定 ----------------
def test_stop_path_records_before_clobbering_state():
    src = (REPO / "gateway" / "session_mixin.py").read_text(encoding="utf-8")
    assert src.index("record_exit_event(") < src.index('_update_runtime_status("stopped"')


def test_signal_handler_binds_signal_name():
    src = (REPO / "gateway" / "run.py").read_text(encoding="utf-8")
    assert "loop.add_signal_handler(sig, _make_stop_handler(sig))" in src
    block = src[src.index("def _make_stop_handler"): src.index("def restart_signal_handler")]
    assert "_exit_signal_name" in block and "_exit_source" in block


def test_adapter_fatal_paths_tag_source():
    src = (REPO / "gateway" / "health_mixin.py").read_text(encoding="utf-8")
    assert src.count('self._exit_source = "adapter_fatal"') == 2


def test_startup_echo_present():
    src = (REPO / "gateway" / "run.py").read_text(encoding="utf-8")
    assert "Previous gateway exit record" in src


def test_home_delegates_to_single_source(home):
    """数据根必须走 mimir_constants.get_mimir_home（单一真源）。

    首版在此处独立复刻了 env 解析链 ⇒ 裸读旧键 ⇒ 被 IND-02 契约闸
    （tests/contract/test_runtime_path_independence_ind02.py）拦下、Tier-0 Gate2 转红。
    本臂钉住「同一真源」这件事，避免再次分叉。
    """
    er, tmp = home
    from mimir_constants import get_mimir_home

    assert er._home() == str(get_mimir_home())
    assert er._home() == str(tmp)
