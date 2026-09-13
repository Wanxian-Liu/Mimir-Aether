"""坑三支持任务（Hermes 开工令 · buzz 收件行 113 · X2-a 同源）——

``session_start`` 行必须自带归因字段，使 HF v2 数据管线可直接消费每个会话文件、
无需与 git-audit 流 join：

``trace_id`` / ``trigger_source`` / ``agent_id`` 三项，取法 = X2-a 同源：
in-process ``agent.run_context.current_run()`` 优先，退化到 X2-a 注入子进程的
env 键（``MIMIR_TRACE_ID`` / ``MIMIR_AGENT_ID`` / ``MIMIR_TRIGGER_SOURCE``）。

验收（Hermes 原话）：「新会话的 trajectory 文件 session_start 行含 trace_id 字段」。
"""

import json
from pathlib import Path

import pytest

import agent.run_context as rc


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """隔离 runtime home + 清空 run 上下文与 X2-a env（防宿主进程残留）。"""
    home = tmp_path / "mimir_home"
    (home / "data").mkdir(parents=True)
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(home))
    for key in ("MIMIR_TRACE_ID", "MIMIR_AGENT_ID", "MIMIR_TRIGGER_SOURCE"):
        monkeypatch.delenv(key, raising=False)
    rc.end_run()
    try:
        from agent.execution_pipeline_sessions import reset_execution_pipeline_state

        reset_execution_pipeline_state()
    except Exception:
        pass
    yield home
    rc.end_run()


def _session_start(rec) -> dict:
    """First line of the trajectory file (session_start), parsed from disk."""
    text = Path(rec.file_path).read_text(encoding="utf-8")
    assert text.strip(), "trajectory file is empty"
    return json.loads(text.splitlines()[0])


# ── ① in-process 通道：gateway 先 begin_run，再建 recorder ──────────────────


def test_session_start_takes_provenance_from_run_context(_isolated):
    from agent.execution_recorder import ExecutionRecorder

    rc.begin_run(trace_id="run_abc123", trigger_source="api", session_key="sk-1")
    rec = ExecutionRecorder(task_name="t-runctx", session_id="s-runctx")
    rec.close()

    head = _session_start(rec)
    assert head["type"] == "session_start"
    assert head["trace_id"] == "run_abc123"
    assert head["trigger_source"] == "api"
    assert head["agent_id"] == "mimir"
    # 既有字段不回归
    assert head["session_id"] == "s-runctx"
    assert head["task_name"] == "t-runctx"
    assert head["start_time"]


def test_trigger_source_resolved_by_run_context_when_not_explicit(_isolated):
    """begin_run 未给 trigger_source 时，run_context 自行解析（X2-a 同源，非 recorder 猜）。"""
    from agent.execution_recorder import ExecutionRecorder

    rc.begin_run(trace_id="run_noexplicit", platform="feishu", text="【讨论室唤醒】x")
    rec = ExecutionRecorder(task_name="t-watchdog", session_id="s-watchdog")

    head = _session_start(rec)
    assert head["trace_id"] == "run_noexplicit"
    assert head["trigger_source"] == "watchdog"  # 由 run_context 的 marker 表解析
    assert head["agent_id"] == "mimir"


def test_recorder_sees_run_context_created_in_another_thread(_isolated):
    """executor 线程里 begin_run（gateway 实际形态）→ 进程级 fallback 仍可见。"""
    import threading

    from agent.execution_recorder import ExecutionRecorder

    box = {}

    def _worker():
        rc.begin_run(trace_id="run_thread", trigger_source="buzz-watcher")
        rec = ExecutionRecorder(task_name="t-thread", session_id="s-thread")
        box["head"] = _session_start(rec)
        rc.end_run()

    t = threading.Thread(target=_worker)
    t.start()
    t.join()

    assert box["head"]["trace_id"] == "run_thread"
    assert box["head"]["trigger_source"] == "buzz-watcher"


# ── ② 子进程通道：X2-a env 键 ───────────────────────────────────────────────


def test_session_start_falls_back_to_x2a_env_keys(_isolated, monkeypatch):
    from agent.execution_recorder import ExecutionRecorder

    monkeypatch.setenv("MIMIR_TRACE_ID", "tr_env_999")
    monkeypatch.setenv("MIMIR_AGENT_ID", "env-agent")
    monkeypatch.setenv("MIMIR_TRIGGER_SOURCE", "self-restart")

    rec = ExecutionRecorder(task_name="t-env", session_id="s-env")
    head = _session_start(rec)

    assert head["trace_id"] == "tr_env_999"
    assert head["agent_id"] == "env-agent"
    assert head["trigger_source"] == "self-restart"


def test_run_context_wins_over_stale_env(_isolated, monkeypatch):
    """同源两通道优先级：in-process run 上下文 > env（不拿陈旧 env 冒充本次 run）。"""
    from agent.execution_recorder import ExecutionRecorder

    monkeypatch.setenv("MIMIR_TRACE_ID", "tr_stale")
    rc.begin_run(trace_id="run_fresh", trigger_source="api")

    head = _session_start(ExecutionRecorder(task_name="t-prio", session_id="s-prio"))
    assert head["trace_id"] == "run_fresh"


# ── ③ 无 run：字段恒在，但**不伪造** join key ─────────────────────────────


def test_keys_present_but_not_fabricated_without_run(_isolated):
    from agent.execution_recorder import ExecutionRecorder

    rec = ExecutionRecorder(task_name="t-norun", session_id="s-norun")
    head = _session_start(rec)

    for key in ("trace_id", "trigger_source", "agent_id"):
        assert key in head, f"{key} 必须存在（HF v2 schema 按字段消费）"
    assert head["trace_id"] == ""      # 无 run ⇒ 不编 trace_id（同 child_env_injection 纪律）
    assert head["trigger_source"] == ""
    assert head["agent_id"] == "mimir"  # 恒有默认值


# ── ④ 真实接线：begin_run → start_execution_pipeline（网关实际顺序） ────────


def test_pipeline_entry_writes_trace_id_to_session_start(_isolated):
    from agent.execution_pipeline_sessions import start_execution_pipeline

    rc.begin_run(trace_id="run_e2e_7", trigger_source="api", session_key="sess-k")
    rec = start_execution_pipeline(task_name="t-e2e", session_id="sid-e2e")
    rec.close()

    head = _session_start(rec)
    assert head["trace_id"] == "run_e2e_7"
    assert head["trigger_source"] == "api"
    assert head["agent_id"] == "mimir"


def test_no_run_no_provenance_keys_injection_unchanged():
    """X2-a 既有契约不回归：未开 run 时 child_env_injection() 仍返回 {}。"""
    rc.end_run()
    assert rc.child_env_injection() == {}
