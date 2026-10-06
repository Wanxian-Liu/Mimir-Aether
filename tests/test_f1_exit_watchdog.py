"""F-1 退出看门狗回归用例（禁 skip / xfail）。

判据对象 = 「停机尾链有硬上限」：默认上限必须 < systemd TimeoutStopSec(30)，
drain 必须被夹进该上限内，且到点必须真的强制退出（带退出码 + 出声证据）。
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from gateway import exit_watchdog as ew  # noqa: E402


def test_default_budget_is_below_systemd_timeout(monkeypatch):
    """默认上限必须严格小于 systemd 的 30s —— 否则等于没装。"""
    monkeypatch.delenv("MIMIR_EXIT_WATCHDOG_SECS", raising=False)
    value = ew.exit_watchdog_seconds()
    assert value == ew.DEFAULT_EXIT_WATCHDOG_S
    assert 0 < value < 30
    assert ew.DEFAULT_EXIT_WATCHDOG_S < 30


def test_env_override_clamped_to_ceiling(monkeypatch):
    """env 可调，但封顶在 29s（永不 ≥ systemd 的 30s）。"""
    monkeypatch.setenv("MIMIR_EXIT_WATCHDOG_SECS", "5")
    assert ew.exit_watchdog_seconds() == 5.0
    monkeypatch.setenv("MIMIR_EXIT_WATCHDOG_SECS", "999")
    assert ew.exit_watchdog_seconds() == ew.MAX_EXIT_WATCHDOG_S
    assert ew.exit_watchdog_seconds() < 30
    monkeypatch.setenv("MIMIR_EXIT_WATCHDOG_SECS", "0")
    assert ew.exit_watchdog_seconds() == ew.MIN_EXIT_WATCHDOG_S


def test_invalid_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("MIMIR_EXIT_WATCHDOG_SECS", "not-a-number")
    assert ew.exit_watchdog_seconds() == ew.DEFAULT_EXIT_WATCHDOG_S
    assert ew.exit_watchdog_seconds("") == ew.DEFAULT_EXIT_WATCHDOG_S
    assert ew.exit_watchdog_seconds(None) == ew.DEFAULT_EXIT_WATCHDOG_S


def test_drain_budget_clamped_under_watchdog(monkeypatch):
    """drain 默认 60s 必须被夹到 watchdog - margin，且永不为负。"""
    monkeypatch.delenv("MIMIR_EXIT_WATCHDOG_SECS", raising=False)
    wd = ew.exit_watchdog_seconds()
    budget = ew.drain_budget_seconds(60.0)
    assert budget == wd - ew.DEFAULT_DRAIN_MARGIN_S
    assert budget < wd < 30
    # 本来就短的 drain 不被放大
    assert ew.drain_budget_seconds(3.0) == 3.0
    # 极端配置下不为负
    assert ew.drain_budget_seconds(60.0, watchdog=1.0) == 0.0
    assert ew.drain_budget_seconds("garbage") >= 0.0


def _run_armed_subprocess(seconds: float, exit_code: int, timeout: float = 20.0):
    code = (
        "import logging, sys;"
        f"sys.path.insert(0, {str(REPO)!r});"
        "logging.basicConfig(level=logging.ERROR);"
        "lg = logging.getLogger('f1-test');"
        "from gateway.exit_watchdog import arm_exit_watchdog;"
        f"arm_exit_watchdog('unit-test', seconds={seconds}, logger=lg, "
        f"exit_code_provider=lambda: {exit_code});"
        "import time; time.sleep(300)"
    )
    started = time.monotonic()
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, timeout=timeout)
    return proc, time.monotonic() - started


def test_watchdog_forces_exit_with_intended_code_and_evidence():
    """到点必须真退出：耗时 ≈ 上限、退出码取 provider、出声带 F1_EXIT_WATCHDOG_FIRED。"""
    proc, elapsed = _run_armed_subprocess(seconds=1.0, exit_code=7)
    assert proc.returncode == 7, (proc.returncode, proc.stderr[-2000:])
    assert elapsed < 8.0, elapsed
    assert elapsed >= 1.0, elapsed
    assert "F1_EXIT_WATCHDOG_FIRED" in proc.stderr, proc.stderr[-2000:]
    assert "f1-exit-watchdog" not in proc.stderr  # 证据里不掺杂质


def test_watchdog_status_reports_armed_budget(monkeypatch):
    monkeypatch.setenv("MIMIR_EXIT_WATCHDOG_SECS", "12")
    ew._reset_for_tests()
    st = ew.status()
    assert st["armed"] is False
    assert st["default_seconds"] == ew.DEFAULT_EXIT_WATCHDOG_S
    assert ew.exit_watchdog_seconds() == 12.0
