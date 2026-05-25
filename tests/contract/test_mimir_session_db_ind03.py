"""IND-03: MIMIR_SESSION_DB with OPENCLAW_SESSION_DB legacy read."""

from pathlib import Path

import mimir_constants


def test_mimir_session_db_primary(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENCLAW_SESSION_DB", raising=False)
    monkeypatch.setenv("MIMIR_SESSION_DB", str(tmp_path / "custom.db"))
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    assert mimir_constants.get_mimir_session_search_db_path() == tmp_path / "custom.db"


def test_openclaw_session_db_legacy_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("MIMIR_SESSION_DB", raising=False)
    monkeypatch.setenv("OPENCLAW_SESSION_DB", str(tmp_path / "legacy.db"))
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    assert mimir_constants.get_mimir_session_search_db_path() == tmp_path / "legacy.db"


def test_mimir_session_db_wins_over_openclaw(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_SESSION_DB", str(tmp_path / "new.db"))
    monkeypatch.setenv("OPENCLAW_SESSION_DB", str(tmp_path / "old.db"))
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    assert mimir_constants.get_mimir_session_search_db_path() == tmp_path / "new.db"
