"""活体 cron 入口的日志面：``cli_main()`` 必须让 ``logger.info()`` 落盘。

治的毛病（2026-11-22 实测）：活体入口 ``scripts/dream_memory_cron.sh`` 用
「裸解释器 + -c 单行」形态 ⇒ 本模块**被 import** ⇒ ``__name__ != "__main__"``
⇒ 文件末尾 ``__main__`` 块的 ``basicConfig`` **从不执行** ⇒ 全部 ``logger.info()``
被 ``logging.lastResort`` 丢弃。读数：61 个日志文件 ``grep -F '[DreamMemory]'``
= 0 命中。后果：``取数面=`` 这个「无人知道它在空转」的唯一观测面一行都没落过盘。

变异点（负控）：把 ``_ensure_cli_logging`` 换成 no-op（等价修复前行为），
同一个 INFO 必须**落不进**文件。做不到 ⇒ 本用例没有鉴别力。
"""
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import dream_memory as dm  # noqa: E402

MARK = "[DreamMemory] 取数面=PROBE-END-TO-END"


def _our_handlers():
    return [
        h
        for h in dm.logger.handlers
        if isinstance(h, logging.FileHandler)
        and str(getattr(h, "baseFilename", "")).endswith("dream_memory.log")
    ]


@pytest.fixture(autouse=True)
def clean_logger_state():
    """每个用例前后清掉本模块加的 FileHandler / 就绪标记（logger 是模块全局）。"""
    def _reset():
        for h in _our_handlers():
            dm.logger.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass
        if hasattr(dm.logger, "_mimir_cli_log_ready"):
            delattr(dm.logger, "_mimir_cli_log_ready")

    _reset()
    yield
    _reset()


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """把数据根指到 tmp，别污染真实 logs/。"""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    return tmp_path


def _emit_and_collect(tmp_path):
    """走真 cli_main，让桩替身发一条 INFO，再读盘。"""
    def _fake_sync(dry_run=False):
        dm.logger.info(MARK)
        return "STUB-REPORT"

    dm.sync_run_dream_cycle = _fake_sync
    rc = dm.cli_main([])
    for h in _our_handlers():
        h.flush()
    logf = tmp_path / "logs" / "dream_memory.log"
    body = logf.read_text(encoding="utf-8") if logf.exists() else ""
    return rc, body


# ── 正控 ────────────────────────────────────────────────────────────────

def test_ensure_cli_logging_attaches_file_handler(isolated_home):
    dm._ensure_cli_logging()
    hs = _our_handlers()
    assert len(hs) == 1, hs
    assert dm.logger.level == logging.INFO
    assert str(isolated_home / "logs") in hs[0].baseFilename


def test_ensure_cli_logging_is_idempotent(isolated_home):
    dm._ensure_cli_logging()
    dm._ensure_cli_logging()
    dm._ensure_cli_logging()
    assert len(_our_handlers()) == 1, _our_handlers()


def test_cli_main_emits_source_face_to_log(isolated_home):
    """活体路径：INFO 必须落进 logs/dream_memory.log。"""
    rc, body = _emit_and_collect(isolated_home)
    assert rc == 0, rc
    assert "PROBE-END-TO-END" in body, body[-400:]


# ── 负控 / 变异点 ────────────────────────────────────────────────────────

def test_mutation_control_without_ensure_cli_logging_nothing_lands(
    isolated_home, monkeypatch
):
    """等价修复前行为（no-op）⇒ 同一条 INFO 必须落不进文件。

    若本用例变红（即 no-op 下也落盘），说明 test_cli_main_emits_source_face_to_log
    的绿不是本修复带来的 —— 该正控没有鉴别力。
    """
    monkeypatch.setattr(dm, "_ensure_cli_logging", lambda: None)
    dm.logger.setLevel(logging.WARNING)  # 等价 __main__ 块未执行时的有效级别
    rc, body = _emit_and_collect(isolated_home)
    assert rc == 0, rc
    assert "PROBE-END-TO-END" not in body, body[-400:]


def test_cli_main_body_calls_ensure_logging():
    """结构闸：``cli_main`` 体内必须调用 ``_ensure_cli_logging()``。

    防回归 —— 有人把它挪回 ``__main__`` 块，本文件其余用例仍会绿
    （因为它们直接调 ``cli_main`` 而不经过 __main__），只有这条会红。
    """
    import inspect

    src = inspect.getsource(dm.cli_main)
    assert "_ensure_cli_logging()" in src, src[:300]
