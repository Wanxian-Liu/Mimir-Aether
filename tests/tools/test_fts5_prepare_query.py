"""FTS5 MATCH query preparation (hyphen / dotted tokens)."""

from tools.fts5_search.engine import (
    FTS5SearchEngine,
    prepare_fts5_match_query,
    fts_token_needs_quoting,
)


def test_fts_token_needs_quoting_hyphen_and_dot():
    assert fts_token_needs_quoting("IR-20260520")
    assert fts_token_needs_quoting("E-008")
    assert fts_token_needs_quoting("persistent.json")
    assert not fts_token_needs_quoting("JEPA")
    assert not fts_token_needs_quoting("AND")


def test_prepare_query_quotes_hyphenated_id():
    assert prepare_fts5_match_query("IR-20260520") == '"IR-20260520"'


def test_prepare_query_multi_term_hyphen():
    assert prepare_fts5_match_query("E-008 cli shim") == (
        '"E-008" AND cli AND shim'
    )


def test_fts_match_hyphen_query_no_operational_error(tmp_path):
    db_path = tmp_path / "fts.db"
    engine = FTS5SearchEngine(str(db_path))
    try:
        engine._ensure_session("s1", source="test", title="t")
        engine.index_message(
            "s1",
            "user",
            "See IR-20260520 incident checklist",
        )
        prepared = prepare_fts5_match_query("IR-20260520")
        cursor = engine._conn.execute(
            "SELECT COUNT(*) FROM messages_fts WHERE messages_fts MATCH ?",
            (prepared,),
        )
        assert cursor.fetchone()[0] >= 1
    finally:
        engine.close()


def test_session_search_backend_env(monkeypatch):
    from tools.session_search_tool import get_session_search_backend

    monkeypatch.delenv("SESSION_SEARCH_BACKEND", raising=False)
    assert get_session_search_backend() == "like"
    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "hybrid")
    assert get_session_search_backend() == "hybrid"
    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "FTS5")
    assert get_session_search_backend() == "fts5"
    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic")
    assert get_session_search_backend() == "semantic"
    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "semantic_hybrid")
    assert get_session_search_backend() == "semantic_hybrid"
    monkeypatch.setenv("SESSION_SEARCH_BACKEND", "bogus")
    assert get_session_search_backend() == "like"
