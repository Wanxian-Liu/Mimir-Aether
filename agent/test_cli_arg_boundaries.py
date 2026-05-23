"""mimir_cli argparse boundary tests (E-008 · replaces legacy cli.py parser tests)."""

import sys

import pytest


def _run_main(monkeypatch, argv: list[str]) -> int:
    from mimir_cli import main as cli_mod

    monkeypatch.setattr(sys, "argv", argv)
    return cli_mod.main()


def test_mimir_version_returns_zero(monkeypatch, capsys):
    rc = _run_main(monkeypatch, ["mimir", "version"])
    assert rc is None or rc == 0
    out = capsys.readouterr().out
    assert "MimirAether v" in out


def test_mimir_profile_rename_missing_new_name_exits(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, ["mimir", "profile", "rename", "old_only"])
    assert exc.value.code != 0


def test_mimir_profile_create_missing_name_exits(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, ["mimir", "profile", "create"])
    assert exc.value.code != 0


def test_mimir_config_set_missing_value_returns_one(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, ["mimir", "config", "set", "SOME_KEY"])
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "config set" in out.lower()


def test_mimir_config_unknown_subcommand_exits(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, ["mimir", "config", "not-a-real-subcmd"])
    assert exc.value.code != 0


def test_mimir_chat_query_with_extra_positional_rejected(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, ["mimir", "chat", "-q", "parity-query", "version"])
    assert exc.value.code != 0


def test_cli_shim_version_via_python_cli_py(monkeypatch, capsys):
    """``python cli.py version`` still works through the compatibility shim."""
    import cli as cli_mod

    monkeypatch.setattr(sys, "argv", ["cli.py", "version"])
    rc = cli_mod.main()
    assert rc is None or rc == 0
    out = capsys.readouterr().out
    assert "MimirAether v" in out
