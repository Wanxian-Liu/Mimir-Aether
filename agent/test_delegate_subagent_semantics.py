from pathlib import Path

from agent.delegate_subagent import SubagentManager, TaskStatus


def test_delegate_task_unknown_agent_marks_failed(monkeypatch, tmp_path):
    import agent.delegate_subagent as ds

    # Isolate persisted task state under tmp_path.
    monkeypatch.setattr(ds.Path, "home", staticmethod(lambda: tmp_path))

    mgr = SubagentManager()
    task = mgr.create_task(description="unknown agent test")

    ok = mgr.delegate_task(
        task_id=task.id,
        agent_type="definitely-not-a-real-agent-cmd-xyz",
        agent_config={"timeout": 0.2},
    )

    assert ok is True  # delegate_task returns True even if the task fails.
    t2 = mgr.get_task(task.id)
    assert t2 is not None
    assert t2.status == TaskStatus.FAILED
    assert t2.error is not None
    assert "not found in PATH" in t2.error

