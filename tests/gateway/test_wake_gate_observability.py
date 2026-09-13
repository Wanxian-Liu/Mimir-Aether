"""U16 / RS1-②③：wake_gate 可观测（grant 日志 + /health 快照 + 回溯落盘）。

背景（四方验收卡 Q7 选项 (a) + backlog U16）：grant 侧此前**零日志**，且
``wake_gate_snapshot()`` 全仓零消费者 ⇒ 无法区分「闸跑了并放行」与
「闸根本没跑」，U11 单飞闸的验收永久停在「逻辑验证」。
"""
import json
import logging

from gateway.wake_gate import WakeGate, _metrics_path

ENV_ON = {'MIMIR_WAKE_GATE': 'on'}


def _gate(env=None, clock=None) -> WakeGate:
    return WakeGate(
        env_getter=lambda: dict(env if env is not None else ENV_ON), clock=clock
    )


def _read():
    return json.loads(_metrics_path().read_text(encoding='utf-8'))


# -- ① grant 侧留痕（日志） ------------------------------------------------


def test_grant_logs_info(caplog):
    g = _gate()
    with caplog.at_level(logging.INFO, logger='gateway.wake_gate'):
        d = g.acquire(session_key='s1', run_token='r1', trigger_source='buzz-watcher')
    assert d.granted is True
    msgs = [r.getMessage() for r in caplog.records if 'wake-gate grant' in r.getMessage()]
    assert len(msgs) == 1
    assert 's1' in msgs[0]
    assert 'buzz-watcher' in msgs[0]


def test_deny_is_not_logged_here(caplog):
    """deny 侧已由 agent_mixin 打 WARNING —— 此处重复打 = 噪声翻倍。

    注：caplog 捕获本测试**全量**记录（pytest 把 root 级别置 0），故必须先
    ``caplog.clear()`` 再比较 deny 之后的新增记录（2026-09-13 踩坑：不 clear
    会断言到进入上下文之前的 grant 行）。
    """
    g = _gate()
    assert g.acquire(session_key='s1', run_token='r1').granted
    caplog.clear()
    d = g.acquire(session_key='s1', run_token='r2')
    assert d.reason == 'occupied'
    assert not [r for r in caplog.records if 'wake-gate' in r.getMessage()]


# -- ② 回溯式落盘 ---------------------------------------------------------


def test_grant_persists_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv('MIMIR_AETHER_HOME', str(tmp_path))
    g = _gate()
    g.acquire(session_key='s1', run_token='r1', trigger_source='buzz-watcher')
    p = _metrics_path()
    assert p == tmp_path / 'data' / 'ops' / 'wake_gate_metrics.json'
    data = _read()
    assert data['metrics']['wake_granted_total'] == 1
    assert data['metrics']['run_rejected_by_gate_total'] == 0
    assert data['active_runs'] == 1
    ev = data['events'][-1]
    assert ev['reason'] == 'granted' and ev['granted'] is True
    assert ev['session_key'] == 's1' and ev['trigger_source'] == 'buzz-watcher'
    assert isinstance(ev['ts'], float) and data['pid'] > 0


def test_occupied_polling_does_not_flood_disk(tmp_path, monkeypatch):
    """wait_for_slot 每 50ms 轮询一次 acquire ⇒ occupied 必须排除在落盘之外。"""
    monkeypatch.setenv('MIMIR_AETHER_HOME', str(tmp_path))
    g = _gate()
    g.acquire(session_key='s1', run_token='r1')
    for _ in range(30):
        assert g.acquire(session_key='s1', run_token='r2').reason == 'occupied'
    data = _read()
    assert len(data['events']) == 1
    assert data['events'][0]['run_token'] == 'r1'


def test_duplicate_event_is_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv('MIMIR_AETHER_HOME', str(tmp_path))
    g = _gate()
    g.acquire(session_key='s1', run_token='r1', fingerprint='fp-x')
    g.release('s1', 'r1')
    d = g.acquire(session_key='s1', run_token='r2', fingerprint='fp-x')
    assert d.reason == 'duplicate_event'
    data = _read()
    assert data['events'][-1]['reason'] == 'duplicate_event'
    assert data['metrics']['wake_duplicate_total'] == 1


def test_event_ring_rotates_at_200(tmp_path, monkeypatch):
    monkeypatch.setenv('MIMIR_AETHER_HOME', str(tmp_path))
    g = _gate()
    for i in range(205):
        tok = 'r%d' % i
        assert g.acquire(session_key='s1', run_token=tok).granted
        assert g.release('s1', tok)
    data = _read()
    assert len(data['events']) == 200
    assert data['events'][-1]['run_token'] == 'r204'
    assert data['metrics']['wake_granted_total'] == 205


def test_persist_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv('MIMIR_AETHER_HOME', str(tmp_path))
    g = _gate(env={'MIMIR_WAKE_GATE': 'on', 'MIMIR_WAKE_GATE_PERSIST': '0'})
    assert g.acquire(session_key='s1', run_token='r1').granted
    assert not _metrics_path().exists()


def test_gate_off_is_logged_and_persisted(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv('MIMIR_AETHER_HOME', str(tmp_path))
    g = _gate(env={'MIMIR_WAKE_GATE': 'off'})
    with caplog.at_level(logging.INFO, logger='gateway.wake_gate'):
        d = g.acquire(session_key='s1', run_token='r1', trigger_source='buzz-watcher')
    assert d.granted and d.reason == 'gate_off'
    assert any('wake-gate OFF' in r.getMessage() for r in caplog.records)
    data = _read()
    assert data['events'][-1]['reason'] == 'gate_off'
    assert data['metrics']['gate_off_total'] == 1


def test_observe_failure_never_changes_decision(tmp_path, monkeypatch):
    """观测是可选增强：异常不得影响裁决（否则闸被观测拖死）。"""
    monkeypatch.setenv('MIMIR_AETHER_HOME', str(tmp_path))
    g = _gate()

    def _boom(*_a, **_k):
        raise RuntimeError('boom')

    monkeypatch.setattr(g, '_persist_metrics', _boom)
    assert g.acquire(session_key='s1', run_token='r1').granted is True


# -- ③ /health 挂载 -------------------------------------------------------


def test_snapshot_for_health_exposes_wake_gate(tmp_path, monkeypatch):
    monkeypatch.setenv('MIMIR_AETHER_HOME', str(tmp_path))
    from agent.monitor import snapshot_for_health
    from gateway.wake_gate import reset_wake_gate

    reset_wake_gate()
    snap = snapshot_for_health()
    assert 'wake_gate' in snap
    wg = snap['wake_gate']
    for key in (
        'wake_granted_total',
        'wake_duplicate_total',
        'run_rejected_by_gate_total',
        'active_runs',
        'gate_enabled',
        'lease_s',
    ):
        assert key in wg
    for key in ('agent', 'agent_error_rate', 'agent_tool_p50_ms'):
        assert key in snap
