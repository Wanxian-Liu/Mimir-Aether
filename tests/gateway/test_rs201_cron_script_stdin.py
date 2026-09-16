"""RS20.1 P0 契约测试：cron 脚本执行器必须显式 `stdin=DEVNULL`（把「恰好对的默认」变成不变量）。

背景（盘上实证，非推断）：`gateway/cron_mixin.py::execute_cron_job._run_cron_script` 的
`subprocess.Popen` 此前**不传 stdin** ⇒ 子进程继承 gateway 的 fd0。现网该 unit 恰好是
`StandardInput=null` 所以「交互式阻塞」不可达 —— 但这只依赖启动方式不变。
受控复现（`~/.mimiraether/notes/2026-09-15-RS20.1-方案-sh挂死根治.md`）：**带正确 shebang 的脚本照样挂死**
（`read`/`script`/`ssh` 等命令等 stdin EOF 永久等待）⇒ 分派闸 Q23/Q24 **防不住**，必须执行期兜住。

本测试的形态 = **不变量 + 负控**：
  * 正文本体对**真实源码**断言（stdin 必须是 DEVNULL；start_new_session 必须为 True）；
  * 负控段证明**这个检查有牙**（同一提取器喂「缺 stdin 的合成源码」必须判失败）——
    否则「每次都快照」只是仪式。
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "gateway" / "cron_mixin.py"

FAKE_MISSING_STDIN = """import subprocess
def execute_cron_job():
    def _run_cron_script():
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return child
"""

FAKE_WITH_STDIN = """import subprocess
def execute_cron_job():
    def _run_cron_script():
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL)
        return child
"""


def _popen_kwargs(source: str) -> dict:
    """在源码里找 `_run_cron_script` 内的第一个 `subprocess.Popen(...)` 并返回其关键字实参（ast.unparse）。"""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_cron_script":
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "Popen"):
                    return {kw.arg: ast.unparse(kw.value) for kw in sub.keywords}
    raise AssertionError("未找到 _run_cron_script 内的 subprocess.Popen —— 提取器需更新")


def _has_stdin_devnull(source: str) -> bool:
    return _popen_kwargs(source).get("stdin", "").endswith("DEVNULL")


def test_stdin_is_devnull_invariant():
    kwargs = _popen_kwargs(SRC.read_text(encoding="utf-8"))
    assert kwargs.get("stdin", "").endswith("DEVNULL"), (
        "cron 脚本执行器未显式 stdin=DEVNULL（现为 %r）"
        " => 交互式阻塞类挂死会随启动方式改变而复活（RS20.1 C3）" % kwargs.get("stdin")
    )


def test_pipes_and_session_invariants():
    kwargs = _popen_kwargs(SRC.read_text(encoding="utf-8"))
    assert kwargs.get("stdout") == "subprocess.PIPE"
    assert kwargs.get("stderr") == "subprocess.PIPE"
    assert kwargs.get("text") == "True"
    assert kwargs.get("start_new_session") == "True", "Q23：必须独立进程组，否则 killpg 不成立"


def test_negative_control_missing_stdin_is_detected():
    """负控：把 stdin 去掉的合成源码必须被同一提取器判为不合规。"""
    assert _has_stdin_devnull(FAKE_MISSING_STDIN) is False


def test_positive_control_synthetic_source_passes():
    assert _has_stdin_devnull(FAKE_WITH_STDIN) is True


def test_extractor_raises_when_function_renamed():
    """若关键函数改名/删除，测试必须**报错**而不是静默通过。"""
    with pytest.raises(AssertionError):
        _popen_kwargs("def something_else(): pass\n")


def _run(script_body: str, *, devnull_stdin: bool, budget_s: float):
    """跑一个脚本，比较「stdin=DEVNULL」与「继承永不 EOF 的 fd」。

    ⚠️ 关键坑（第一版踩过）：用 `stdin=subprocess.PIPE` 模拟"继承"是**错的** ——
    `communicate()` 会**关闭** stdin ⇒ 子进程拿到 EOF ⇒ 天然不挂。
    真实现场的 fd0 是一条**父进程持有且永不关闭**的管道/终端 ⇒ 必须自己 `os.pipe()`
    并把读端交出去、自己攥着写端不放，才复现「等不到 EOF」。
    """
    bash = shutil.which("bash") or shutil.which("sh")
    if not bash:
        pytest.skip("无 bash/sh 可用")
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "probe.sh"
        script.write_text(script_body, encoding="utf-8")
        r = w = None
        if devnull_stdin:
            stdin_arg = subprocess.DEVNULL
        else:
            r, w = os.pipe()          # 读端给子进程；写端父进程攥着（永不写、永不关）
            stdin_arg = r
        t0 = time.time()
        child = subprocess.Popen(
            [bash, str(script)],
            stdin=stdin_arg,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=True,
        )
        if r is not None:
            os.close(r)               # 父进程不再需要读端（子进程已持有）
        try:
            child.communicate(timeout=budget_s)
            elapsed, rc = time.time() - t0, child.returncode
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate()
            elapsed, rc = time.time() - t0, None
        finally:
            if w is not None:
                os.close(w)           # 收尾：放掉写端，避免 fd 泄漏
        return elapsed, rc


def test_interactive_read_exits_with_devnull_stdin():
    """DEVNULL ⇒ `read` 立刻拿到 EOF ⇒ 秒退。"""
    elapsed, rc = _run("read x\necho done\n", devnull_stdin=True, budget_s=5)
    assert rc is not None and elapsed < 2.0


def test_interactive_read_hangs_with_inherited_pipe():
    """反证（同一脚本、只改 stdin 来源）：继承「父进程攥着不关的管道」⇒ 卡住直到预算用尽。

    这是「P0 修的是真问题」的行为证据；若哪天它开始秒退，说明前提变了（须重新取证）。
    """
    elapsed, rc = _run("read x\necho done\n", devnull_stdin=False, budget_s=1.5)
    assert rc is None, "继承非 EOF stdin 竟然没挂住 —— 前提变化，需重新取证"
    assert elapsed >= 1.4
