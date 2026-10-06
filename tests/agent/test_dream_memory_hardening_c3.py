"""C3 梦境蒸馏加固（2026-10-06 · 自检处置表 7 裁决 3a）。

三组验：2 写前备份 · 1 出错出声 · 3 单写窗口；外加 dry_run 零写入回归。

跑法: bash scripts/pytest_isolated.sh tests/agent/test_dream_memory_hardening_c3.py
（重测试必须隔离 —— gateway 自身 cgroup 内跑整仓 pytest 会 OOM）
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from agent import dream_memory, persistent_store


def _home() -> Path:
    """conftest 的 autouse fixture 已把 MIMIR_AETHER_HOME 指到本用例 tmp home。"""
    return Path(os.environ["MIMIR_AETHER_HOME"])


def _seed(home: Path) -> Path:
    """铺一个最小的记忆面（persistent.json + memories/MEMORY.md）。"""
    (home / "data").mkdir(parents=True, exist_ok=True)
    (home / "memories").mkdir(parents=True, exist_ok=True)
    pj = home / "data" / "persistent.json"
    pj.write_text(
        json.dumps(
            {
                "version": "1.4",
                "memory": {"key_decisions": [{"decision": "d1"}], "learned_patterns": []},
                "progress": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (home / "memories" / "MEMORY.md").write_text("# MEMORY\n- a\n", encoding="utf-8")
    return pj


async def _llm_dead(*_a, **_k):
    """替身：模拟蒸馏 LLM 调用失败（_call_dream_llm 返回 None）。"""
    return None




# -- 2 写前备份 -----------------------------------------------------------


def test_backup_creates_rollback_point_with_matching_sha256():
    home = _home()
    _seed(home)
    dest = Path(dream_memory._backup_memory_surface())

    assert dest.is_dir() and dest.parent.name == "backups"
    manifest = json.loads((dest / "MANIFEST.json").read_text(encoding="utf-8"))
    live = [f for f in manifest["files"] if f.get("exists")]
    assert {f["rel"] for f in live} >= {"data/persistent.json", "memories/MEMORY.md"}
    for f in live:
        assert f["sha256"] == f["sha256_backup"], f["rel"]
        assert dream_memory._sha256_file(str(dest / f["rel"])) == f["sha256"]
    assert manifest["restore_cmd"].startswith("cp -a ")


def test_backup_refuses_and_leaves_no_dir_when_surface_absent():
    """记忆面一件都没有 ⇒ 抛（拒绝无回滚点写盘）且不留半成品目录。"""
    with pytest.raises(RuntimeError):
        dream_memory._backup_memory_surface()
    root = _home() / "data" / "backups"
    assert not root.exists() or not list(root.iterdir())


def test_prune_keeps_last_n():
    _seed(_home())
    root = _home() / "data" / "backups"
    for i in range(5):
        (root / f"dream-2026010{i}T000000Z").mkdir(parents=True, exist_ok=True)
    removed = dream_memory._prune_backups(keep=2)
    assert len(removed) == 3
    assert sorted(d.name for d in root.iterdir()) == [
        "dream-20260103T000000Z",
        "dream-20260104T000000Z",
    ]


# -- 1 出错出声 -----------------------------------------------------------


def test_record_failure_writes_readable_record(capsys):
    detail = dream_memory._record_failure("unit", RuntimeError("boom"))
    assert "boom" in detail
    rec = json.loads(Path(dream_memory._failure_record_path()).read_text(encoding="utf-8"))
    assert rec["stage"] == "unit" and "boom" in rec["error"]
    assert dream_memory._FAILURE_MARKER in capsys.readouterr().err


def test_cli_main_rc1_and_marker_when_llm_fails(monkeypatch, capsys):
    """出口落在 rc 上：失败必须 rc=1 且报告带标记（gateway 判的就是 rc）。"""
    _seed(_home())
    monkeypatch.setattr(dream_memory, "_call_dream_llm", _llm_dead)
    assert dream_memory.cli_main([]) == 1
    out = capsys.readouterr()
    assert dream_memory._FAILURE_MARKER in out.out
    assert Path(dream_memory._failure_record_path()).is_file()


def test_failed_cycle_does_not_touch_persistent(monkeypatch):
    """失败 ⇒ 不写盘（不能「失败了还把记忆面重写一遍」）。"""
    pj = _seed(_home())
    before = pj.read_text(encoding="utf-8")
    monkeypatch.setattr(dream_memory, "_call_dream_llm", _llm_dead)
    ok, report = asyncio.run(dream_memory.run_dream_cycle())
    assert ok is False and dream_memory._FAILURE_MARKER in report
    assert pj.read_text(encoding="utf-8") == before


def test_dry_run_is_zero_write(monkeypatch):
    """回归：旧版 dry_run=True 仍一路走到 _save_persistent（docstring 说是不写）。"""
    home = _home()
    pj = _seed(home)
    before = pj.read_text(encoding="utf-8")
    ok, report = asyncio.run(dream_memory.run_dream_cycle(dry_run=True))
    assert ok is True and "dry-run" in report
    assert pj.read_text(encoding="utf-8") == before
    assert not (home / "data" / "backups").exists()
    assert not (home / "data" / ".distilled").exists()


# -- 3 单写窗口 -----------------------------------------------------------


def _spawn_lock_holder(tmp_path: Path, lock: Path, seconds: float) -> subprocess.Popen:
    """起一个**真进程**持 flock（跨进程，不是同进程内自欺）。"""
    holder_py = tmp_path / "hold_window_lock.py"
    holder_py.write_text(
        "import fcntl, sys, time\n"
        "fd = open(sys.argv[1], 'w')\n"
        "fcntl.flock(fd, fcntl.LOCK_EX)\n"
        "print('locked', flush=True)\n"
        "time.sleep(float(sys.argv[2]))\n",
        encoding="utf-8",
    )
    return subprocess.Popen(
        [sys.executable, str(holder_py), str(lock), str(seconds)],
        stdout=subprocess.PIPE,
        text=True,
    )


def test_write_window_excludes_other_process(tmp_path):
    home = _home()
    (home / "data").mkdir(parents=True, exist_ok=True)
    lock = persistent_store.write_lock_path()
    holder = _spawn_lock_holder(tmp_path, lock, 2.0)
    assert holder.stdout.readline().strip() == "locked"
    try:
        t0 = time.monotonic()
        with persistent_store.write_window(timeout_s=0.5, on_timeout="abort") as held:
            assert held is False, "另一进程持锁时不该拿到窗口"
        assert time.monotonic() - t0 >= 0.4
        ledger = home / "data" / "write_window_violations.jsonl"
        assert ledger.is_file() and "abort" in ledger.read_text(encoding="utf-8")
    finally:
        holder.wait(timeout=10)

    # 差额对照：持锁方退出后可拿到 ⇒ 上面那个 False 是锁造成的，不是恒 False
    with persistent_store.write_window(timeout_s=1.0, on_timeout="abort") as held2:
        assert held2 is True


def test_write_window_is_reentrant():
    with persistent_store.write_window(timeout_s=1.0, on_timeout="abort") as outer:
        assert outer is True
        with persistent_store.write_window(timeout_s=0.1, on_timeout="abort") as inner:
            assert inner is True


def test_persistent_save_under_window_no_regression(tmp_path):
    """写入面零回归：save() 仍在窗口内正常落盘 + 双写镜像。"""
    persistent_store.save(
        {"version": "1.0", "memory": {"key_decisions": []}, "progress": {}}
    )
    assert persistent_store.get_persistent_path().is_file()
    assert persistent_store.write_lock_path().is_file()


def test_gateway_save_participates_in_window():
    """接线验证：`persistent_store.save()` 必须真的在窗口内 ——
    主线程持窗口时，另一线程的 save() 拿不到（释放后立刻完成）。"""
    import threading

    persistent_store.save(
        {"version": "1.0", "memory": {"key_decisions": []}, "progress": {}}
    )
    done = threading.Event()
    started = threading.Event()

    def writer():
        started.set()
        persistent_store.save(
            {"version": "1.0", "memory": {"key_decisions": [{"decision": "w"}]}, "progress": {}}
        )
        done.set()

    with persistent_store.write_window(timeout_s=1.0, on_timeout="abort") as held:
        assert held is True
        t = threading.Thread(target=writer)
        t.start()
        assert started.wait(timeout=2)
        assert not done.wait(timeout=0.5), "持窗口期间别的写者不该写进去"
    assert done.wait(timeout=5), "窗口释放后写者应立刻完成"
    t.join(timeout=5)
    final = persistent_store.get_persistent_path().read_text(encoding="utf-8")
    assert "w" in final
