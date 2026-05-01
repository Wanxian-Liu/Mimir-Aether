from agent.delegate_subagent import SubagentManager, TaskStatus


def test_delegate_task_missing_id_returns_false(monkeypatch, tmp_path):
    import agent.delegate_subagent as ds

    monkeypatch.setattr(ds.Path, "home", staticmethod(lambda: tmp_path))
    mgr = SubagentManager()
    assert mgr.delegate_task("no-such-task-id", agent_type="codex") is False


def test_delegate_task_non_pending_returns_false(monkeypatch, tmp_path):
    import agent.delegate_subagent as ds

    monkeypatch.setattr(ds.Path, "home", staticmethod(lambda: tmp_path))

    def _fake_ok(self, agent_type, description, config):
        return {"returncode": 0, "stdout": "fake-ok", "stderr": ""}

    monkeypatch.setattr(ds.SubagentManager, "_execute_agent", _fake_ok)

    mgr = SubagentManager()
    task = mgr.create_task(description="second delegate should fail")
    assert mgr.delegate_task(task.id, agent_type="codex") is True
    t1 = mgr.get_task(task.id)
    assert t1.status == TaskStatus.COMPLETED
    assert mgr.delegate_task(task.id, agent_type="codex") is False
    t2 = mgr.get_task(task.id)
    assert t2.status == TaskStatus.COMPLETED
    assert t2.result == {"returncode": 0, "stdout": "fake-ok", "stderr": ""}


def test_delegate_task_success_sets_completed_and_result(monkeypatch, tmp_path):
    import agent.delegate_subagent as ds

    monkeypatch.setattr(ds.Path, "home", staticmethod(lambda: tmp_path))

    seen: list[tuple[str, str, dict]] = []

    def _fake(self, agent_type, description, config):
        seen.append((agent_type, description, dict(config)))
        return {"returncode": 0, "stdout": "out", "stderr": ""}

    monkeypatch.setattr(ds.SubagentManager, "_execute_agent", _fake)

    mgr = SubagentManager()
    task = mgr.create_task(description="hello delegate")
    cfg = {"timeout": 42, "cwd": str(tmp_path)}
    assert mgr.delegate_task(task.id, agent_type="hermes-agent", agent_config=cfg) is True

    t = mgr.get_task(task.id)
    assert t.status == TaskStatus.COMPLETED
    assert t.error is None
    assert t.result == {"returncode": 0, "stdout": "out", "stderr": ""}
    assert t.assigned_agent == "hermes-agent"
    assert t.completed_at is not None
    assert len(seen) == 1
    assert seen[0][0] == "hermes-agent"
    assert seen[0][1] == "hello delegate"
    assert seen[0][2]["timeout"] == 42
    assert seen[0][2]["cwd"] == str(tmp_path)


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

