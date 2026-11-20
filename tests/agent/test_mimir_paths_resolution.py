"""Narrow tests for Mimir home path resolution (MIMIR_AETHER_HOME / MIMIRAETHER_HOME)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

import mimir_constants


@pytest.fixture
def clear_mimir_home_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "HERMES_HOME"):
        monkeypatch.delenv(key, raising=False)


def test_get_mimir_home_uses_mimir_aether_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clear_mimir_home_env: None
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    assert mimir_constants.get_mimir_home() == tmp_path
    assert mimir_constants.get_mimir_data_dir() == tmp_path / "data"
    assert mimir_constants.get_mimir_sessions_dir() == tmp_path / "data" / "sessions"


def test_get_mimir_home_accepts_mimiraether_home_alias(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clear_mimir_home_env: None
) -> None:
    monkeypatch.setenv("MIMIRAETHER_HOME", str(tmp_path))
    assert mimir_constants.get_mimir_home() == tmp_path


def test_get_mimir_home_ignores_hermes_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clear_mimir_home_env: None
) -> None:
    """I-1 定版：HERMES_HOME 是 **Hermes 自家**的键 —— 绝不作为 Mimir 的家。

    旧断言（要求回落到 HERMES_HOME）停在改造前的行为上；实现现为
    「忽略 + stderr 出声」（见 mimir_constants._warn_ignored_hermes_home），
    故本用例随 I-1 定版翻转。新家 = 默认运行数据根 ~/.mimiraether。

    同探针正控（防「忽略」二字其实是探针整体失灵 = 恒负）：
    MIMIR_AETHER_HOME 一设必须被采纳。
    """
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # 负向：Hermes 家的键不得成为 Mimir 的家
    assert mimir_constants.get_mimir_home() != tmp_path
    assert mimir_constants.get_mimir_home() == Path.home() / ".mimiraether"

    # 正控（同一次调用面）：自家键一设即被采纳 —— 证明探针有分辨力
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    assert mimir_constants.get_mimir_home() == tmp_path


def test_mimir_aether_home_precedence_over_hermes_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clear_mimir_home_env: None
) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(a))
    monkeypatch.setenv("HERMES_HOME", str(b))
    assert mimir_constants.get_mimir_home() == a


def test_mimir_aether_home_precedence_over_mimiraether_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clear_mimir_home_env: None
) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(a))
    monkeypatch.setenv("MIMIRAETHER_HOME", str(b))
    assert mimir_constants.get_mimir_home() == a


def test_sticker_cache_path_follows_mimir_aether_home_on_import(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clear_mimir_home_env: None
) -> None:
    """Module-level CACHE_PATH must reflect env at import time; re-import after env set."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    sys.modules.pop("gateway.sticker_cache", None)
    sc = importlib.import_module("gateway.sticker_cache")
    assert sc.CACHE_PATH == tmp_path / "data" / "sticker_cache.json"
