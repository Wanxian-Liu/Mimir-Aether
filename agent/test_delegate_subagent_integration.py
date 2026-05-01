"""Real subprocess integration tests for SubagentManager (POSIX)."""

import sys

import pytest

from agent.delegate_subagent import SubagentManager, TaskStatus

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="delegate integration uses /bin/sh stubs",
)


def _write_executable(path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_delegate_real_subprocess_success(monkeypatch, tmp_path):
    import agent.delegate_subagent as ds

    monkeypatch.setattr(ds.Path, "home", staticmethod(lambda: tmp_path))

    stub = tmp_path / "ok_agent"
    _write_executable(
        stub,
        "#!/bin/sh\n"
        "printf '%s' \"$1\"\n"
        "echo DELEGATE_OK\n"
        "exit 0\n",
    )

    mgr = SubagentManager()
    task = mgr.create_task(description="arg-for-stub")

    assert (
        mgr.delegate_task(
            task.id,
            agent_type=str(stub),
            agent_config={"timeout": 30, "cwd": str(tmp_path)},
        )
        is True
    )

    t = mgr.get_task(task.id)
    assert t.status == TaskStatus.COMPLETED
    assert t.error is None
    assert t.result is not None
    assert t.result["returncode"] == 0
    assert "DELEGATE_OK" in (t.result.get("stdout") or "")
    assert "arg-for-stub" in (t.result.get("stdout") or "")


def test_delegate_real_subprocess_timeout_marks_failed(monkeypatch, tmp_path):
    import agent.delegate_subagent as ds

    monkeypatch.setattr(ds.Path, "home", staticmethod(lambda: tmp_path))

    slow = tmp_path / "slow_agent"
    _write_executable(
        slow,
        "#!/bin/sh\nsleep 30\nexit 0\n",
    )

    mgr = SubagentManager()
    task = mgr.create_task(description="will-timeout")

    assert (
        mgr.delegate_task(
            task.id,
            agent_type=str(slow),
            agent_config={"timeout": 1, "cwd": str(tmp_path)},
        )
        is True
    )

    t = mgr.get_task(task.id)
    assert t.status == TaskStatus.FAILED
    assert t.error is not None
    assert "timed out" in t.error.lower()
