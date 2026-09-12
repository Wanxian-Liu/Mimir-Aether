"""skip_db contract: JSONL-only must ALSO skip the derived search index.

Audit 2026-09-12: ``gateway/session.py::append_to_transcript`` wrote to the search
index even when ``skip_db=True``, so callers asking for "only JSONL, skip the SQLite
write" still appended rows to ``data/sessions_search.db``. Bare-python3 Gate2 runs
deposited 800 fixture rows (sid-1 / sid / sid-rw, payload hello / x) into the
PRODUCTION index over 3.5 months.

Regression guards:
- skip_db=True  -> no session-DB write AND no search-index write;
- skip_db=False -> both happen (control, so the guard cannot be satisfied by
  disabling indexing altogether);
- rewrite_transcript -> search index rewritten once by default; skip_db=True suppresses
  BOTH the SQLite rewrite and the derived search-index rewrite (R1, 2026-09-12);
- derived sessions-search DB落点可注入 (``sessions_search_db_path=``) -> 调用方/测试无需
  改进程全局 env 即可沙箱化派生写入。
"""

from __future__ import annotations

from pathlib import Path

from unittest.mock import MagicMock, patch

from gateway.config import load_gateway_config
from gateway.session import SessionStore


def _store(tmp_path, db):
    return SessionStore(
        tmp_path / "sessions",
        load_gateway_config(),
        transcript_session_db=db,
    )


def test_skip_db_skips_session_db(tmp_path):
    db = MagicMock()
    store = _store(tmp_path, db)
    store.append_to_transcript("sid-1", {"role": "user", "content": "x"}, skip_db=True)
    db.append_message.assert_not_called()


def test_skip_db_also_skips_search_index(tmp_path):
    db = MagicMock()
    store = _store(tmp_path, db)
    with patch.object(store, "_append_to_sessions_search_index") as mock_index:
        store.append_to_transcript("sid-1", {"role": "user", "content": "x"}, skip_db=True)
    mock_index.assert_not_called()


def test_without_skip_db_indexes_search_index(tmp_path):
    db = MagicMock()
    store = _store(tmp_path, db)
    with patch.object(store, "_append_to_sessions_search_index") as mock_index:
        store.append_to_transcript("sid-2", {"role": "user", "content": "hello"})
    mock_index.assert_called_once()
    db.append_message.assert_called_once()


def test_rewrite_transcript_rewrites_search_index_once(tmp_path):
    db = MagicMock()
    store = _store(tmp_path, db)
    with patch.object(store, "_rewrite_sessions_search_index") as mock_rewrite:
        store.rewrite_transcript("sid-rw", [{"role": "user", "content": "one"}])
    mock_rewrite.assert_called_once()


# --- R1 (2026-09-12): rewrite 路径闸门 + 派生索引落点注入 -------------------------


def test_rewrite_transcript_skip_db_skips_search_index(tmp_path):
    """skip_db=True 时 rewrite 不得触碰派生搜索索引（与 append 同契约）。"""
    db = MagicMock()
    store = _store(tmp_path, db)
    with patch.object(store, "_rewrite_sessions_search_index") as mock_rewrite:
        store.rewrite_transcript(
            "sid-rw", [{"role": "user", "content": "one"}], skip_db=True
        )
    mock_rewrite.assert_not_called()


def test_rewrite_transcript_skip_db_skips_sqlite(tmp_path):
    """skip_db=True 时 rewrite 不得 clear/replay SQLite。"""
    db = MagicMock()
    store = _store(tmp_path, db)
    store.rewrite_transcript(
        "sid-rw", [{"role": "user", "content": "one"}], skip_db=True
    )
    db.clear_messages.assert_not_called()
    db.append_message.assert_not_called()


def test_rewrite_transcript_skip_db_still_writes_jsonl(tmp_path):
    """闸门只关派生写入，JSONL 必须照写（否则 skip_db 语义被读成「什么都不写」）。"""
    db = MagicMock()
    store = _store(tmp_path, db)
    store.rewrite_transcript(
        "sid-jsonl", [{"role": "user", "content": "one"}], skip_db=True
    )
    jsonl = store.get_transcript_path("sid-jsonl")
    assert jsonl.exists()
    assert "one" in jsonl.read_text(encoding="utf-8")


def test_rewrite_skip_db_leaves_injected_index_untouched(tmp_path):
    """端到端：注入落点 + skip_db=True → 派生索引 DB 根本不被初始化/创建。"""
    injected = tmp_path / "idx.db"
    store = SessionStore(
        tmp_path / "sessions",
        load_gateway_config(),
        sessions_search_db_path=injected,
    )
    store.rewrite_transcript("sid-e2e", [{"role": "user", "content": "one"}], skip_db=True)
    assert store._sessions_search_db is None
    assert not injected.exists()


def test_injected_index_path_is_used(tmp_path):
    """注入的落点必须真正生效（构造器本就支持 db_path，此前未被使用）。"""
    injected = tmp_path / "injected.db"
    store = SessionStore(
        tmp_path / "sessions",
        load_gateway_config(),
        sessions_search_db_path=injected,
    )
    db = store._get_sessions_search_db()
    assert db is not None
    assert Path(db.db_path) == injected
    assert injected.exists()


def test_injected_index_path_beats_env(tmp_path, monkeypatch):
    """注入优先于 env（MIMIR_SESSION_DB）——保证调用方可以压过全局配置。"""
    monkeypatch.setenv("MIMIR_SESSION_DB", str(tmp_path / "env.db"))
    injected = tmp_path / "injected.db"
    store = SessionStore(
        tmp_path / "sessions",
        load_gateway_config(),
        sessions_search_db_path=injected,
    )
    db = store._get_sessions_search_db()
    assert db is not None
    assert Path(db.db_path) == injected


def test_env_index_path_used_without_injection(tmp_path, monkeypatch):
    """无注入时仍走既有 env 通道（不回归既有注入点）。"""
    env_db = tmp_path / "env.db"
    monkeypatch.setenv("MIMIR_SESSION_DB", str(env_db))
    store = SessionStore(tmp_path / "sessions", load_gateway_config())
    db = store._get_sessions_search_db()
    assert db is not None
    assert Path(db.db_path) == env_db


def test_wrapper_passes_skip_db_through(tmp_path):
    """兼容包装类必须透传 skip_db（否则调用方设了也无效）。"""
    from gateway.session import SessionManager  # noqa: F401  (存在性即可)
    import inspect

    sig = inspect.signature(SessionManager.rewrite_transcript)
    assert "skip_db" in sig.parameters
