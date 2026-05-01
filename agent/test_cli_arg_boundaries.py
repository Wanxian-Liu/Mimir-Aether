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


def test_cli_profiles_export_missing_output_path_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    rc = _run_cli_main(cli_mod, monkeypatch, ["cli.py", "profiles", "export", "some_profile"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "导出路径" in out or "用法: profiles export" in out


def test_cli_profiles_create_missing_name_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    rc = _run_cli_main(cli_mod, monkeypatch, ["cli.py", "profiles", "create"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "请指定profile名称" in out or "用法: profiles create" in out


def test_cli_profiles_delete_missing_name_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    rc = _run_cli_main(cli_mod, monkeypatch, ["cli.py", "profiles", "delete"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "删除" in out and ("名称" in out or "用法" in out)


def test_cli_profiles_import_missing_archive_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    rc = _run_cli_main(cli_mod, monkeypatch, ["cli.py", "profiles", "import"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "归档" in out or "用法: profiles import" in out


def test_cli_config_set_missing_value_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    rc = _run_cli_main(cli_mod, monkeypatch, ["cli.py", "config", "set", "SOME_KEY"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Usage: config set" in out or "config set" in out.lower()


def test_cli_config_get_missing_key_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    rc = _run_cli_main(cli_mod, monkeypatch, ["cli.py", "config", "get"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Usage: config get" in out or "config get" in out.lower()

