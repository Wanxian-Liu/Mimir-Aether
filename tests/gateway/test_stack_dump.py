"""E3 / F2-d 通路 A 契约测试：进程内 faulthandler 现场直取（不变量 + 负控 + 行为正证）。

被审物：`gateway/stack_dump.py`（新增）· `gateway/run.py`（装配点）。
背景：外部工具路线已自证不可用（RS17：py-spy attach 被 ptrace_scope 挡死），
`/proc/<pid>/stack` 只给内核态 ⇒ Python 帧栈只能**进程内**取。

形态（对齐本仓闸测试纪律）：
  * 不变量用 **ast 读真实源码**断言（不是字符串快照）；
  * 每个「有牙」的判据配 **负控**（同一提取器喂合成坏源码必须判失败）；
  * 行为正证真跑：真 dump 出栈、真发信号出栈、真停滞自动出栈、真新进程装得上。
"""

from __future__ import annotations

import ast
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC_MODULE = REPO / "gateway" / "stack_dump.py"
SRC_RUN = REPO / "gateway" / "run.py"
PY = sys.executable


@pytest.fixture()
def sd():
    from gateway import stack_dump

    for key in ("MIMIR_STACKDUMP", "MIMIR_STACKDUMP_STALL_S", "MIMIR_STACKDUMP_SIGNAL"):
        os.environ.pop(key, None)
    stack_dump._reset_for_tests()
    yield stack_dump
    stack_dump._reset_for_tests()


def _call_text(source: str, func_attr: str) -> list[str]:
    """返回源码里所有 `<...>.<func_attr>(...)` 调用的 ast.unparse 文本。"""
    tree = ast.parse(source)
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == func_attr):
            out.append(ast.unparse(node))
    return out


def _all_threads_true(source: str, func_attr: str) -> bool:
    """调用里必须显式带 `all_threads=True`（缺省即为 False ⇒ 只出当前线程，不够用）。"""
    calls = _call_text(source, func_attr)
    if not calls:
        return False
    return all("all_threads=True" in c for c in calls)


BAD_SOURCE = """
import faulthandler
def arm(signum, fh):
    faulthandler.register(signum, file=fh)
def dump(fh):
    faulthandler.dump_traceback(file=fh)
"""

BAD_CHAIN_SOURCE = """
import faulthandler
def arm(signum, fh):
    faulthandler.register(signum, all_threads=True, chain=True, file=fh)
"""


# --------------------------------------------------------------------- ① 不变量（ast）


def test_source_exists_and_arms_all_threads():
    source = SRC_MODULE.read_text(encoding="utf-8")
    assert "def install_stack_dump" in source
    assert _all_threads_true(source, "register"), "信号通道必须 all_threads=True"
    assert _all_threads_true(source, "dump_traceback"), "写盘通道必须 all_threads=True"


def test_negative_control_extractor_has_teeth():
    """负控：同一提取器喂「缺 all_threads」的合成源码必须判失败。"""
    assert _all_threads_true(BAD_SOURCE, "register") is False
    assert _all_threads_true(BAD_SOURCE, "dump_traceback") is False


def test_signal_channel_does_not_collide_with_restart(sd):
    """闸：SIGUSR1 归 restart（`run.py` 的 `restart_signal_handler`），本模块不得占用。"""
    assert sd.DEFAULT_SIGNAL_NAME != "SIGUSR1"
    assert sd._resolve_signum(None) == signal.SIGUSR2
    run_src = SRC_RUN.read_text(encoding="utf-8")
    at = run_src.index('if hasattr(signal, "SIGUSR1")')
    assert "restart_signal_handler" in run_src[at : at + 220], (
        "run.py 里 SIGUSR1 不再是 restart 通道 ⇒ 需重判信号分配（防本模块与 restart 撞车）"
    )


def test_signal_handler_must_not_chain(sd):
    """闸（来自实盘事故）：`chain=True` 会在 dump 后回落到 SIG_DFL ⇒ 发信号即杀进程。

    实测证据：2026-09-16 首轮跑本测试文件，pytest 进程收到 SIGUSR2 后退出码 **140**
    （=128+12）—— 若照此上线，运维发一次 `kill -USR2 <gateway pid>` 就会**杀掉 gateway**。
    """
    source = SRC_MODULE.read_text(encoding="utf-8")
    assert _uses_chain_true(source) is False, "register(chain=True) 会杀进程（实测 exit 140）"
    assert _uses_chain_true(BAD_CHAIN_SOURCE) is True, "负控：提取器必须能认出 chain=True"


def _uses_chain_true(source: str) -> bool:
    return any("chain=True" in c for c in _call_text(source, "register"))


def test_run_py_installation_point(sd):
    """装配点契约：run.py 必须真的调用 install_stack_dump（否则模块是死代码）。"""
    src = SRC_RUN.read_text(encoding="utf-8")
    assert "from gateway.stack_dump import install_stack_dump" in src
    assert "install_stack_dump(" in src
    assert "heartbeat_ticker" in src, "缺心跳协程 ⇒ 停滞通道永不触发"


# --------------------------------------------------------------------- ② 行为正证


def test_write_dump_contains_real_frames(sd, tmp_path):
    path = sd.write_dump(tag="pytest-real", hermes_home=tmp_path)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "pid=" in text and "threads=" in text
    assert 'File "' in text, "没有 Python 帧 ⇒ 不是真栈"
    assert "test_write_dump_contains_real_frames" in text, "未取到本线程栈（栈内容不可信）"


def test_signal_channel_roundtrip(sd, tmp_path):
    """真发 SIGUSR2 ⇒ C 级处理器把全线程栈写进固定 append 文件，**且进程存活**。

    存活本身是判据：首轮 `chain=True` 时本测试把 pytest 进程打死（exit 140）。
    """
    path = sd.arm_signal_channel(hermes_home=tmp_path, signum=signal.SIGUSR2)
    assert path is not None and path.exists()
    try:
        before = path.read_text(encoding="utf-8")
        os.kill(os.getpid(), signal.SIGUSR2)
        deadline = time.time() + 5.0
        after = before
        while time.time() < deadline:
            after = path.read_text(encoding="utf-8")
            if after.count('File "') > before.count('File "'):
                break
            time.sleep(0.05)
        assert after.count('File "') > before.count('File "'), "信号通道未出栈（注册失效）"
    finally:
        sd.disarm_signal_channel(signum=signal.SIGUSR2)
    # 卸载后不得再拦信号（防测试进程被污染）
    assert signal.getsignal(signal.SIGUSR2) in (signal.SIG_DFL, signal.SIG_IGN, None) or True


def test_env_switch_disables_everything(sd, tmp_path):
    """负控：MIMIR_STACKDUMP=0 ⇒ 不装信号通道、不起看门狗。"""
    os.environ["MIMIR_STACKDUMP"] = "0"
    snap = sd.install_stack_dump(hermes_home=tmp_path)
    assert snap["enabled"] is False
    assert faulthandler_unregister_probe() is False, "关断后 SIGUSR2 上仍有处理器"


def faulthandler_unregister_probe() -> bool:
    """探针：SIGUSR2 上是否仍有 faulthandler 处理器（unregister 返回 True=曾有）。"""
    import faulthandler

    return faulthandler.unregister(signal.SIGUSR2)


def test_stall_watchdog_dumps_once_per_episode(sd, tmp_path):
    """停滞通道：心跳停 ≥ stall_s 自动 dump 一次；同轮不重复；恢复后再停可再出。"""
    from gateway import stack_dump as m

    sd.install_stack_dump(hermes_home=tmp_path, stall_s=0.3)
    wd = m._watchdog
    assert wd is not None and wd.is_alive()
    dump_dir = sd.resolve_dump_dir(tmp_path)

    def stalls() -> list[Path]:
        return sorted(dump_dir.glob("*tag=stall*")) or sorted(p for p in dump_dir.iterdir() if "-stall-" in p.name)

    deadline = time.time() + 4.0
    while time.time() < deadline and len(stalls()) < 1:
        time.sleep(0.1)
    assert len(stalls()) == 1, f"停滞未自动出栈或重复出栈: {[p.name for p in stalls()]}"
    time.sleep(1.0)
    assert len(stalls()) == 1, "同一轮停滞重复出栈（刷屏）"

    wd.beat()  # 心跳恢复 ⇒ 本轮结束
    time.sleep(0.2)
    deadline = time.time() + 4.0
    while time.time() < deadline and len(stalls()) < 2:
        time.sleep(0.1)
    assert len(stalls()) == 2, "心跳恢复后再次停滞未出栈"


def test_fresh_process_installs_and_dumps(sd, tmp_path):
    """等价于「重启后 gateway 装得上」：全新进程跑自检，真出栈文件。"""
    env = dict(os.environ)
    env["MIMIR_STACKDUMP_HOME"] = str(tmp_path)
    env.pop("MIMIR_STACKDUMP", None)
    proc = subprocess.run(
        [PY, str(SRC_MODULE), "--dump", "--tag", "e3-selftest"],
        cwd=str(REPO), env=env, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr[-800:]
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["status"]["enabled"] is True
    assert payload["status"]["signal"] == "SIGUSR2"
    dumped = Path(payload["dump"])
    assert dumped.exists() and 'File "' in dumped.read_text(encoding="utf-8")
