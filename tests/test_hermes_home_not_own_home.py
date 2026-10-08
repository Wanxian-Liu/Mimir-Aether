"""回归用例（第 20 单 · 跨环境假红族）：
`HERMES_HOME` 存在时**不得**改变 Mimir 自家解析。

判据（可跑）：
  python3 -m pytest tests/test_hermes_home_not_own_home.py -q
  -> 期望 6 passed, 0 skipped（无 skip/xfail）
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mimir_constants  # noqa: E402


def _resolve(monkeypatch, **env):
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "HERMES_HOME"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return mimir_constants.get_mimir_home()


def test_hermes_home_alone_does_not_change_own_home(monkeypatch):
    """HERMES_HOME 单独存在 ⇒ 自家仍是默认 ~/.mimiraether（不是 ~/.hermes）。"""
    got = _resolve(monkeypatch, HERMES_HOME="/home/rayliu/.hermes")
    assert got == mimir_constants._DEFAULT_MIMIR_HOME, got
    assert got.name == ".mimiraether", got


def test_own_key_wins_over_hermes_home(monkeypatch):
    """两个键同时存在 ⇒ 自家键赢（MIMIR_AETHER_HOME 优先）。"""
    got = _resolve(
        monkeypatch,
        MIMIR_AETHER_HOME="/tmp/own_home",
        HERMES_HOME="/home/rayliu/.hermes",
    )
    assert got == Path("/tmp/own_home"), got


def test_legacy_own_key_wins_over_hermes_home(monkeypatch):
    """旧自家键 MIMIRAETHER_HOME 也赢过 HERMES_HOME。"""
    got = _resolve(
        monkeypatch,
        MIMIRAETHER_HOME="/tmp/legacy_own",
        HERMES_HOME="/home/rayliu/.hermes",
    )
    assert got == Path("/tmp/legacy_own"), got


def test_hermes_home_is_ignored_loudly(monkeypatch, capsys):
    """忽略必须出声（stderr 一行），且**只警告不改行为**。"""
    monkeypatch.setattr(mimir_constants, "_HERMES_HOME_WARNED", False)
    got = _resolve(monkeypatch, HERMES_HOME="/home/rayliu/.hermes")
    err = capsys.readouterr().err
    assert "[mimir-home]" in err, err
    assert "HERMES_HOME=/home/rayliu/.hermes" in err, err
    assert got == mimir_constants._DEFAULT_MIMIR_HOME, got


def test_hermes_home_pointing_at_own_home_is_silent(monkeypatch, capsys):
    """HERMES_HOME 恰指向自家 ⇒ 无歧义，不吵（防噪音）。"""
    monkeypatch.setattr(mimir_constants, "_HERMES_HOME_WARNED", False)
    got = _resolve(monkeypatch, HERMES_HOME=str(mimir_constants._DEFAULT_MIMIR_HOME))
    assert "[mimir-home]" not in capsys.readouterr().err
    assert got == mimir_constants._DEFAULT_MIMIR_HOME, got


def test_read_gates_agree_with_hermes_home_set():
    """端到端：HERMES_HOME 指到别处时，两个读口仍读自家（子进程，真环境）。"""
    fake = "/tmp/fake_hermes_home_regression"
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        # 2026-10-08 修（CI Only-Red 根因）：此前写死开发机家目录，
        # 与本进程真实 HOME 不一致 ⇒ 子进程解析到别的家目录、断言必败。
        "HOME": str(Path.home()),
        "HERMES_HOME": fake,
        "PYTHONPATH": str(ROOT),
    }
    own = str(mimir_constants._DEFAULT_MIMIR_HOME)

    r2 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_run_health_alerts.py")],
        capture_output=True, text=True, env=env, cwd=str(ROOT),
    )
    assert fake not in r2.stdout, r2.stdout
    assert own in r2.stdout, r2.stdout

    r4 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_memory_hygiene.py")],
        capture_output=True, text=True, env=env, cwd=str(ROOT),
    )
    assert "entries=" in r4.stdout, r4.stdout
    assert fake not in r4.stdout, r4.stdout
    assert "VERDICT:" in r4.stdout, r4.stdout
