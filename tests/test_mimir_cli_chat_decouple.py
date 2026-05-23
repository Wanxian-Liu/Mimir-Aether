"""E-005: mimir chat decoupled from cli.main."""

import inspect

import pytest

from mimir_cli.chat_runner import apply_chat_env, cmd_chat_does_not_import_cli_main, run_chat


def test_cmd_chat_does_not_import_cli_main():
    assert cmd_chat_does_not_import_cli_main()


def test_run_chat_query_mode(monkeypatch):
    calls = {}

    async def fake_run_task(task, model, max_iterations, verbose):
        calls["task"] = task
        calls["model"] = model
        calls["max_iterations"] = max_iterations
        calls["verbose"] = verbose
        return 0

    monkeypatch.setattr("cli.run_task", fake_run_task)

    class Args:
        query = "hello"
        model = "deepseek/deepseek-chat"
        verbose = True
        max_turns = 12
        source = None
        resume = None
        checkpoints = False
        worktree = False
        pass_session_id = False

    with pytest.raises(SystemExit) as exc:
        run_chat(Args())
    assert exc.value.code == 0
    assert calls["task"] == "hello"
    assert calls["max_iterations"] == 12


def test_apply_chat_env_sets_session_id(monkeypatch):
    monkeypatch.delenv("HERMES_SESSION_ID", raising=False)

    class Args:
        source = "tool"
        resume = "sess-abc"
        max_turns = 5
        checkpoints = True
        worktree = False
        pass_session_id = True

    apply_chat_env(Args())
    import os

    assert os.environ["HERMES_SESSION_ID"] == "sess-abc"
    assert os.environ["HERMES_SESSION_SOURCE"] == "tool"
    assert os.environ["HERMES_MAX_ITERATIONS"] == "5"
    assert os.environ["HERMES_CHECKPOINTS"] == "1"
    assert os.environ["HERMES_PASS_SESSION_ID"] == "1"


def test_main_cmd_chat_source_has_no_cli_main_import():
    from mimir_cli import main as mimir_main

    src = inspect.getsource(mimir_main.cmd_chat)
    assert "from cli import main" not in src
    assert "chat_runner" in src
