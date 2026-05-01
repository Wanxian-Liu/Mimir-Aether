import sys

import pytest


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


def test_cli_models_set_missing_model_id_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    rc = _run_cli_main(cli_mod, monkeypatch, ["cli.py", "models", "--set"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "--set 需要模型 ID" in out or "模型 ID" in out


def test_cli_models_set_followed_by_flag_treated_as_missing_value(monkeypatch, capsys):
    import cli as cli_mod

    # Next token starts with "-" → do not consume as model id; same boundary as bare --set
    rc = _run_cli_main(cli_mod, monkeypatch, ["cli.py", "models", "--set", "--refresh"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "--set 需要模型 ID" in out or "模型 ID" in out


def test_cli_query_and_explicit_subcommand_rejected(monkeypatch, capsys):
    import cli as cli_mod

    # -q 与显式子命令同时出现 → 报错退出，避免静默忽略其中一种意图。
    rc = _run_cli_main(
        cli_mod,
        monkeypatch,
        ["cli.py", "-q", "parity-query-must-not-run-as-task", "version"],
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert "不能同时使用" in out or "单次任务" in out
    assert "parity-query-must-not-run-as-task" not in out


def test_cli_version_with_query_tokens_in_remainder_is_safe(monkeypatch, capsys):
    import cli as cli_mod

    # -q after positional command stays in REMAINDER; optional --query is unset.
    rc = _run_cli_main(cli_mod, monkeypatch, ["cli.py", "version", "-q", "remainder-orphan"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "MimirAether 版本信息" in out


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="argparse.ArgumentParser(exit_on_error=False) requires Python 3.9+",
)
def test_cli_max_iterations_non_int_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    rc = _run_cli_main(
        cli_mod,
        monkeypatch,
        ["cli.py", "--max-iterations", "not-an-int", "version"],
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert "须为整数" in out or "max-iterations" in out.lower()


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="argparse.ArgumentParser(exit_on_error=False) requires Python 3.9+",
)
def test_cli_max_iterations_below_one_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    rc = _run_cli_main(
        cli_mod,
        monkeypatch,
        ["cli.py", "--max-iterations", "0", "version"],
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert ">=" in out or "须" in out


def test_cli_config_unknown_subcommand_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    rc = _run_cli_main(cli_mod, monkeypatch, ["cli.py", "config", "not-a-real-subcmd"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "未知 config 子命令" in out


def test_cli_models_set_and_list_mutex_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    rc = _run_cli_main(
        cli_mod,
        monkeypatch,
        ["cli.py", "models", "--set", "deepseek/deepseek-chat", "--list"],
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert "不能同时使用" in out or "--set" in out


def test_cli_profiles_create_clone_mutex_returns_one(monkeypatch, capsys):
    import cli as cli_mod

    rc = _run_cli_main(
        cli_mod,
        monkeypatch,
        ["cli.py", "profiles", "create", "parity-name", "--clone", "--clone-all"],
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert "不能同时使用" in out

