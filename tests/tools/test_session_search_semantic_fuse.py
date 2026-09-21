"""R4 fuse: semantic warmup + per-query timeout degradation + bounded abandonment (twin-arm).

臂 A / A' = 慢语义必须降级到关键词兜底 **并带显式标记**；
臂 B = 孪生对照（快语义 ⇒ 无标记、计数器不动）；
臂 C = 差分对照（关断保险丝 ⇒ 同一快路径不再走降级分支）；
臂 D = 单飞闸（已有 worker 在飞 ⇒ 立即降级、不得叠加第二个 worker、不得等满超时）。

桩件纪律：慢桩用 `threading.Event` 释放，测试收尾必须把 worker 放走（`_settle`）——
否则被遗弃的桩线程会污染后续用例（本轮实测 3 failed 的顺序依赖污染）。
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tools.session_search_tool import (  # noqa: E402
    SessionSearchDB,
    semantic_degradation_stats,
    semantic_degradation_total,
    semantic_inflight_stats,
    semantic_query_timeout_s,
    session_search,
    warmup_semantic_search,
)

CHROMA_HITS = [
    {
        "id": "s1:1",
        "content": "semantic fast hit",
        "metadata": {
            "session_id": "s1",
            "message_id": 1,
            "role": "user",
            "source": "cli",
            "timestamp": 1.0,
        },
        "distance": 0.1,
    }
]


@pytest.fixture(autouse=True)
def _clean_fuse_state():
    """每个用例起止都把单飞闸复位（布尔 ⇒ 复位幂等，不会把在飞 worker 变成负值）。"""
    from tools.session_search_tool import _SEMANTIC_INFLIGHT

    _SEMANTIC_INFLIGHT["running"] = False
    yield
    _SEMANTIC_INFLIGHT["running"] = False


def _seed_like_db(tmp_path):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="cli", title="t")
    db.add_message("s1", "user", "fuse-fallback-token")
    return db_path


def _stall(release: threading.Event):
    def _fn(*_args, **_kwargs):
        release.wait(timeout=5)
        return []

    return _fn


def _settle(release: threading.Event, timeout: float = 2.0) -> bool:
    """放走被遗弃的桩 worker，并等到单飞闸真正空出来。"""
    release.set()
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if semantic_inflight_stats()["running"] is False:
            return True
        time.sleep(0.01)
    return False


def test_semantic_query_timeout_s_default_override_and_invalid(monkeypatch):
    monkeypatch.delenv("MIMIR_SEMANTIC_QUERY_TIMEOUT_S", raising=False)
    assert semantic_query_timeout_s() == 5.0
    monkeypatch.setenv("MIMIR_SEMANTIC_QUERY_TIMEOUT_S", "1.5")
    assert semantic_query_timeout_s() == 1.5
    monkeypatch.setenv("MIMIR_SEMANTIC_QUERY_TIMEOUT_S", "not-a-number")
    assert semantic_query_timeout_s() == 5.0
    monkeypatch.setenv("MIMIR_SEMANTIC_QUERY_TIMEOUT_S", "0")
    assert semantic_query_timeout_s() == 0.0


def test_arm_a_slow_semantic_degrades_to_fts5_with_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_FTS5_DB", str(tmp_path / "fts5_search.db"))
    (tmp_path / "fts5_search.db").write_bytes(b"")
    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic")
    monkeypatch.setenv("MIMIR_SEMANTIC_QUERY_TIMEOUT_S", "0.05")
    before = semantic_degradation_total()
    release = threading.Event()
    canned = [
        {
            "session_id": "fts1",
            "source": "cli",
            "started_at": "",
            "title": "fts",
            "summary": "fts fallback hit",
            "message_count": 1,
        }
    ]

    with patch(
        "tools.session_search_tool._semantic_index_ready", return_value=True
    ), patch(
        "tools.chroma_session_indexer.query_session_messages", side_effect=_stall(release)
    ), patch(
        "tools.session_search_tool._session_search_via_fts5", return_value=canned
    ) as fts_mock:
        results = session_search("fuse-fallback-token", db_path=str(tmp_path / "nope.db"))

    assert fts_mock.called
    assert len(results) == 1
    assert results[0]["session_id"] == "fts1"
    assert results[0]["degraded"] is True
    assert results[0]["degraded_reason"].startswith("semantic_timeout>")
    assert results[0]["degraded_fallback"] == "fts5"
    assert semantic_degradation_total() == before + 1
    assert _settle(release)


def test_arm_a_prime_slow_semantic_degrades_to_like_without_fts_db(tmp_path, monkeypatch):
    db_path = _seed_like_db(tmp_path)
    monkeypatch.setenv("OPENCLAW_FTS5_DB", str(tmp_path / "missing.db"))
    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic")
    monkeypatch.setenv("MIMIR_SEMANTIC_QUERY_TIMEOUT_S", "0.05")
    release = threading.Event()

    with patch(
        "tools.session_search_tool._semantic_index_ready", return_value=True
    ), patch(
        "tools.chroma_session_indexer.query_session_messages", side_effect=_stall(release)
    ):
        results = session_search("fuse-fallback-token", db_path=str(db_path))

    assert len(results) == 1
    assert results[0]["session_id"] == "s1"
    assert results[0]["degraded"] is True
    assert results[0]["degraded_fallback"] == "like"
    assert _settle(release)


def test_arm_b_twin_fast_semantic_is_not_degraded(tmp_path, monkeypatch):
    db_path = _seed_like_db(tmp_path)
    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic")
    monkeypatch.setenv("MIMIR_SEMANTIC_QUERY_TIMEOUT_S", "5")
    before = semantic_degradation_total()

    with patch(
        "tools.session_search_tool._semantic_index_ready", return_value=True
    ), patch(
        "tools.chroma_session_indexer.query_session_messages", return_value=CHROMA_HITS
    ):
        results = session_search("semantic fast hit", db_path=str(db_path))

    assert len(results) == 1
    assert "semantic fast hit" in results[0]["summary"]
    assert "degraded" not in results[0]
    assert semantic_degradation_total() == before


def test_arm_c_fuse_disabled_keeps_semantic_path(tmp_path, monkeypatch):
    """差分对照：关断保险丝后不再走降级分支。"""
    db_path = _seed_like_db(tmp_path)
    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic")
    monkeypatch.setenv("MIMIR_SEMANTIC_QUERY_TIMEOUT_S", "0")
    before = semantic_degradation_total()

    with patch(
        "tools.session_search_tool._semantic_index_ready", return_value=True
    ), patch(
        "tools.chroma_session_indexer.query_session_messages", return_value=CHROMA_HITS
    ):
        results = session_search("semantic fast hit", db_path=str(db_path))

    assert len(results) == 1
    assert "degraded" not in results[0]
    assert semantic_degradation_total() == before


def test_arm_d_inflight_busy_degrades_fast_without_second_worker(tmp_path, monkeypatch):
    """臂 D：单飞闸 —— 已有 worker 在飞 ⇒ 立即降级，不叠加第二个 worker、不等满超时。

    背景：v1（无界遗弃）实测把同一 benchmark 从 141s 拖到 498s 仍未跑完（CPU 密集
    查询堆成 worker 舰队）。本臂锁住修法，且断言「不得等满超时」（fail-fast）。
    """
    db_path = _seed_like_db(tmp_path)
    monkeypatch.setenv("OPENCLAW_FTS5_DB", str(tmp_path / "missing.db"))
    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic")
    monkeypatch.setenv("MIMIR_SEMANTIC_QUERY_TIMEOUT_S", "5")

    from tools.session_search_tool import _SEMANTIC_INFLIGHT

    _SEMANTIC_INFLIGHT["running"] = True
    try:
        with patch(
            "tools.session_search_tool._semantic_index_ready", return_value=True
        ), patch("tools.chroma_session_indexer.query_session_messages") as qmock:
            t0 = time.perf_counter()
            results = session_search("fuse-fallback-token", db_path=str(db_path))
            elapsed = time.perf_counter() - t0
    finally:
        _SEMANTIC_INFLIGHT["running"] = False

    assert not qmock.called, "busy 分支不得启动第二个语义 worker"
    assert elapsed < 1.0, "fail-fast：不得等满超时"
    assert results and results[0]["degraded"] is True
    assert results[0]["degraded_reason"] == "semantic_inflight_busy"


def test_inflight_stats_surface_shape():
    assert set(semantic_inflight_stats()) == {"running", "skipped"}


def test_warmup_semantic_search_never_raises(monkeypatch):
    with patch("tools.chroma_session_indexer.query_session_messages", return_value=[]):
        assert warmup_semantic_search() is True
    with patch(
        "tools.chroma_session_indexer.query_session_messages",
        side_effect=RuntimeError("warmup boom"),
    ):
        assert warmup_semantic_search() is False


def test_degradation_stats_snapshot_shape():
    assert set(semantic_degradation_stats()) == {"count", "last_reason", "last_ts"}


def test_benchmark_reports_semantic_degraded_count(tmp_path):
    """降级标记必须有消费端 —— 否则保险丝会把超时伪装成「延迟变好」。"""
    import run_memory_retrieval_benchmark as bench

    like_db = tmp_path / "sessions_search.db"
    like_db.write_bytes(b"")

    def _fake_semantic(_query, _db_path):
        from tools.session_search_tool import _DEGRADED_STATE

        _DEGRADED_STATE["count"] = int(_DEGRADED_STATE["count"]) + 1
        return 0, 1.0

    with patch.object(bench, "_semantic_search", side_effect=_fake_semantic), patch.object(
        bench, "_like_search", return_value=(0, 0.0)
    ), patch(
        "tools.session_search_tool._semantic_index_ready", return_value=True
    ), patch.object(
        bench, "BENCHMARK_QUERIES", bench.BENCHMARK_QUERIES[:2]
    ):
        report = bench.run_benchmark(
            like_db_path=str(like_db), fts_db_path=str(tmp_path / "missing.db")
        )

    assert report["semantic_degraded_count"] == 2
    assert report["semantic_timeout_s"] == 5.0
    assert report["semantic_latency_mode"] == "fuse_bounded"
    assert report["rows"][0]["semantic_degraded"] is True
