"""约束第3条 / P0-1: persistent.json 双写（data/ + memory/ 镜像）一致性 + 失败告警。

背景：data/persistent.json 存在但 memory/persistent.json 缺失 8 个月，
双写从未在代码层实现（约束只是行为文本）。本测试固化：
1. 保存后 memory/persistent.json 必须存在；
2. 两侧内容必须逐字节一致；
3. 镜像写失败必须显式告警（save_merged→False / save→raise），不得静默 exit 0。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import persistent_store


def _minimal_persistent() -> dict:
    return {
        "version": "1.0",
        "memory": {
            "key_decisions": [],
            "learned_patterns": [],
            "active_projects": [],
            "user_preferences": {},
            "skills_used": [],
        },
        "progress": {
            "current_objective": None,
            "completed_milestones": [],
            "pending_tasks": [],
        },
        "session_count": 0,
    }


def test_dual_write_creates_memory_mirror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """保存后 memory/persistent.json 必须存在（双写实锤）。"""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIRAETHER_HOME", str(tmp_path))

    persistent_store.save(_minimal_persistent())

    mirror = persistent_store.get_memory_persistent_path()
    assert mirror.exists(), f"dual-write mirror missing: {mirror}"
    assert mirror.read_text(encoding="utf-8").strip()


def test_dual_write_content_identical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """data/ 与 memory/ 两侧内容必须逐字节一致（双写一致性）。"""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIRAETHER_HOME", str(tmp_path))

    persistent_store.save(_minimal_persistent())

    data_raw = persistent_store.get_persistent_path().read_bytes()
    mirror_raw = persistent_store.get_memory_persistent_path().read_bytes()
    assert data_raw == mirror_raw
    # 结构化一致
    assert json.loads(data_raw) == json.loads(mirror_raw)


def test_dual_write_via_save_merged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CrossSessionMemory 主路径 save_merged 也必须触发双写。"""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIRAETHER_HOME", str(tmp_path))

    from agent.cross_session_memory import CrossSessionMemory

    mem = CrossSessionMemory()
    mem.load()
    mem.set_progress(current_objective="dual-write test objective")
    assert mem.save() is True

    mirror = persistent_store.get_memory_persistent_path()
    assert mirror.exists()
    assert persistent_store.get_persistent_path().read_bytes() == mirror.read_bytes()


def test_dual_write_mirror_failure_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """镜像写失败必须显式报错（save→raise），不得静默 exit 0。

    模拟：memory/ 被一个同名目录占位导致 _write_atomic 失败。
    """
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIRAETHER_HOME", str(tmp_path))

    mirror = persistent_store.get_memory_persistent_path()
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.mkdir()  # 目录占位 → tmp.replace 失败（OSError）

    with pytest.raises(RuntimeError, match="dual-write"):
        persistent_store.save(_minimal_persistent())


def test_dual_write_mirror_failure_save_merged_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save_merged 在镜像失败时返回 False（告警信号），不抛异常但绝不假装成功。"""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIRAETHER_HOME", str(tmp_path))

    mirror = persistent_store.get_memory_persistent_path()
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.mkdir()

    ok = persistent_store.save_merged(
        _minimal_persistent(),
        lambda disk, mem: mem,
    )
    assert ok is False
