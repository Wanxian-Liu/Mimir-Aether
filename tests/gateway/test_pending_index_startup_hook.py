"""B4b · 启动钩子接 `resume_pending_indexes()` · 回归用例（2026-10-06 · 任务书 行218）。

受控差分（真/假都由受控替身给出，判据为数字或布尔）：
  ① 无 pending ⇒ **早退**：不建 DB 连接、不加载 embedding（零成本路径），返回 skipped
  ② 有 pending ⇒ 以 like_db + limit 调 `resume_pending_indexes`，并回报 pending_after
  ③ 限流口径：`MIMIR_PENDING_INDEX_RESUME_LIMIT` 默认 20 · `<=0` ⇒ 无界(None) · 坏值 ⇒ 20
  ④ fail-open：DB 构造失败 / 续传抛异常 ⇒ 返回 error dict，**不抛**
  ⑤ 钩子入口：`MIMIR_PENDING_INDEX_RESUME=0` ⇒ 不起线程；默认 ⇒ daemon 线程跑一次
  ⑥ 钩子线程内异常不外泄（只记 warning）
"""
from __future__ import annotations

import threading

import pytest

from tools import session_search_indexer as ssi


class _FakeDB:
    def __init__(self, path):
        self.db_path = path
        _FakeDB.calls.append(path)

    calls: list = []


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("MIMIR_PENDING_INDEX_RESUME", "MIMIR_PENDING_INDEX_RESUME_DELAY_S",
                 "MIMIR_PENDING_INDEX_RESUME_LIMIT"):
        monkeypatch.delenv(name, raising=False)
    _FakeDB.calls = []


@pytest.fixture()
def fake_db(monkeypatch):
    import tools.session_search_tool as sst
    import mimir_constants

    monkeypatch.setattr(sst, "SessionSearchDB", _FakeDB)
    monkeypatch.setattr(mimir_constants, "get_mimir_session_search_db_path",
                        lambda: "/tmp/fake-sessions.db", raising=False)
    return _FakeDB


# ───────────────────────── ① 无 pending ⇒ 零成本早退 ─────────────────────────

def test_no_pending_skips_without_constructing_db(fake_db, monkeypatch):
    monkeypatch.setattr(ssi, "pending_index_report", lambda: {})
    out = ssi.startup_resume_pending()
    assert out["skipped"] == "no_pending" and out["pending_seen"] == 0
    assert _FakeDB.calls == []          # 没建 DB ⇒ 没触发 embedding 加载


# ───────────────────────── ② 有 pending ⇒ 续传并回报 ─────────────────────────

def test_pending_present_resumes_with_limit_and_reports_after(fake_db, monkeypatch):
    seq = [{"s1": {"total": 3}}, {}]          # 第一次问有 1 个 pending，续传后再问已清空
    monkeypatch.setattr(ssi, "pending_index_report", lambda: seq.pop(0) if seq else {})
    seen = {}

    def _resume(*, like_db=None, limit=None):
        seen["db_path"] = getattr(like_db, "db_path", None)
        seen["limit"] = limit
        return {"pending_seen": 1, "resumed": {"s1": {"filled": 3}}}

    monkeypatch.setattr(ssi, "resume_pending_indexes", _resume)
    out = ssi.startup_resume_pending()
    assert out["pending_seen"] == 1 and out["pending_after"] == 0
    assert seen == {"db_path": "/tmp/fake-sessions.db", "limit": 20}
    assert out["resumed"]["resumed"]["s1"]["filled"] == 3


# ───────────────────────── ③ 限流口径 ─────────────────────────

def test_startup_resume_limit_default_and_overrides(monkeypatch):
    assert ssi._startup_resume_limit() == 20
    monkeypatch.setenv("MIMIR_PENDING_INDEX_RESUME_LIMIT", "5")
    assert ssi._startup_resume_limit() == 5
    monkeypatch.setenv("MIMIR_PENDING_INDEX_RESUME_LIMIT", "0")
    assert ssi._startup_resume_limit() is None      # <=0 ⇒ 无界
    monkeypatch.setenv("MIMIR_PENDING_INDEX_RESUME_LIMIT", "abc")
    assert ssi._startup_resume_limit() == 20        # 坏值 ⇒ 回默认


# ───────────────────────── ④ fail-open ─────────────────────────

def test_fail_open_when_db_construction_raises(monkeypatch):
    import tools.session_search_tool as sst

    class _Boom:
        def __init__(self, path):
            raise RuntimeError("db down")

    monkeypatch.setattr(sst, "SessionSearchDB", _Boom)
    monkeypatch.setattr(ssi, "pending_index_report", lambda: {"s1": {"total": 1}})
    out = ssi.startup_resume_pending()               # 不抛
    assert "RuntimeError: db down" in out["error"]


def test_fail_open_when_resume_raises(fake_db, monkeypatch):
    monkeypatch.setattr(ssi, "pending_index_report", lambda: {"s1": {"total": 1}})

    def _boom(*, like_db=None, limit=None):
        raise ValueError("resume exploded")

    monkeypatch.setattr(ssi, "resume_pending_indexes", _boom)
    out = ssi.startup_resume_pending()
    assert "ValueError: resume exploded" in out["error"]


# ───────────────────────── ⑤⑥ 钩子入口 ─────────────────────────

def test_hook_disabled_by_env_starts_no_thread(monkeypatch):
    monkeypatch.setenv("MIMIR_PENDING_INDEX_RESUME", "0")
    before = {t.name for t in threading.enumerate()}
    assert ssi.start_pending_index_resume_thread() is None
    assert {t.name for t in threading.enumerate()} == before


def test_hook_starts_daemon_thread_and_calls_once(monkeypatch):
    monkeypatch.setenv("MIMIR_PENDING_INDEX_RESUME_DELAY_S", "0")
    monkeypatch.setenv("MIMIR_PENDING_INDEX_RESUME_LIMIT", "7")
    calls = []
    monkeypatch.setattr(ssi.time, "sleep", lambda _s: None)
    monkeypatch.setattr(ssi, "startup_resume_pending",
                        lambda **kw: calls.append(kw) or {"skipped": "no_pending"})
    th = ssi.start_pending_index_resume_thread()
    assert th is not None and th.daemon is True and th.name == "pending-index-resume"
    th.join(timeout=5)
    assert not th.is_alive()
    assert calls == [{}]                    # 线程内跑了一次（limit 由 startup_resume_pending 自解析）


def test_hook_thread_swallows_exceptions(monkeypatch, caplog):
    monkeypatch.setenv("MIMIR_PENDING_INDEX_RESUME_DELAY_S", "0")
    monkeypatch.setattr(ssi.time, "sleep", lambda _s: None)

    def _boom(**kw):
        raise RuntimeError("hook exploded")

    monkeypatch.setattr(ssi, "startup_resume_pending", _boom)
    with caplog.at_level("WARNING"):
        th = ssi.start_pending_index_resume_thread()
        th.join(timeout=5)
    assert any("钩子异常" in r.getMessage() or "hook exploded" in r.getMessage()
               for r in caplog.records)


# ───────────────────────── ⑦ 接线守卫（防「钩子写了没人调」） ─────────────────────────

def test_gateway_run_wires_pending_index_hook():
    """接线守卫：gateway 启动路径必须有**一处**真实调用（非行为证明）。

    防「实现已落、调用点没接」= 钩子恒假（2026-09-26/27 恒假族同源）。行为由 ①–⑥ 覆盖。
    """
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "gateway" / "run.py").read_text(encoding="utf-8")
    assert "from tools.session_search_indexer import start_pending_index_resume_thread" in text
    assert "start_pending_index_resume_thread(logger=logger)" in text
