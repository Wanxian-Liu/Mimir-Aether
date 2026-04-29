import sys


def _run_cli_main(cli_mod, monkeypatch, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", argv)
    return cli_mod.main()


def test_cli_version_returns_zero(monkeypatch):
    import cli as cli_mod

    rc = _run_cli_main(cli_mod, monkeypatch, ["cli.py", "version"])
    assert rc == 0


def test_cli_profiles_rename_missing_new_arg_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    # profiles rename <old> <new> -> missing <new> should return 1
    rc = _run_cli_main(cli_mod, monkeypatch, ["cli.py", "profiles", "rename", "old_only"])
    assert rc == 1

    captured = capsys.readouterr()
    # We assert on a stable substring to ensure the failure is due to arg boundary,
    # not a deeper runtime error.
    assert "请指定原名称和新名称" in captured.out or "用法: profiles rename" in captured.out

