"""#12 空跑闸门 · 预算计数语义 + 硬限（P0-2 · 2026-10-07）。

受控差分口径由 scripts/probes/empty_run_gate_budget_differential.py 提供
（旧版 vs 新版同轨迹回放）；本文件钉住**新版**的性质，并反钉旧版的病灶。
"""
import json

import pytest

from agent import empty_run_gate as erg


def _call(name, args):
    return {"id": "c", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def _msg(*tcs):
    return {"role": "assistant", "content": "", "tool_calls": list(tcs)}


READ = [("read_file", {"path": "/repo/agent/agent_loop.py"})]
CARD = "/repo/wiki/discussions/2026-10-07-x.md"
STAGING = [("execute_code", {"code": "open('/repo/.mimiraether/tmp/d.md','w').write('x')"})]
DELIV = [("write_file", {"path": CARD, "content": "x"})]
DELIV_VAR = [("execute_code",
              {"code": "p = pathlib.Path('/repo/wiki/discussions/y.md')\np.write_text('x')"})]


def turns(*groups):
    out = []
    for g in groups:
        out.append(_msg(*[_call(n, a) for n, a in g]))
    return out


def _replay(n, msgs, limit=4):
    g = erg.EmptyRunGate(task_id="t", limit=limit, force_writes=0)
    fires = []
    for i in range(len(msgs) + 1):
        fires.append(bool(g.tick(msgs[:i], i)))
    return fires, g


# ── 负控：预算内不触发 ────────────────────────────────────────────────
def test_negative_below_limit_no_fire():
    msgs = turns(READ, READ, READ)
    assert erg.readonly_streak(msgs) == 3
    assert erg.EmptyRunGate(task_id="t", limit=4, force_writes=0).tick(msgs, 3) is None


# ── 正控：达阈即触发 ─────────────────────────────────────────────────
def test_positive_at_limit_fires():
    msgs = turns(READ, READ, READ, READ)
    assert erg.readonly_streak(msgs) == 4
    d = erg.EmptyRunGate(task_id="t", limit=4, force_writes=0).tick(msgs, 4)
    assert d and "空跑闸门" in d


# ── 核心回归（旧版病灶）：staging 写**不得**退还预算 ──────────────────
def test_staging_write_does_not_refund_budget():
    msgs = turns(READ, READ, READ, READ, STAGING, READ)
    # 新版：staging 写同样计为「未交付」⇒ streak 连续累加为 6
    assert erg.readonly_streak(msgs) == 6
    assert erg.deliverable_written(msgs) is False
    fires, _ = _replay(erg, turns(READ, READ, READ, READ, STAGING), limit=4)
    assert fires == [False, False, False, False, True, True], fires


def test_old_semantics_would_refund():
    """反钉：把 staging 写当成 write 清零 ⇒ 触发点被推后（旧版行为）。"""
    msgs = turns(READ, READ, READ, READ, STAGING)
    kinds = [erg.classify_tool(n, json.dumps(a)) for n, a in STAGING]
    assert kinds == ["write"]          # 仍被判 write（用于「写过没」的其它口径）
    assert erg.is_deliverable_path("/repo/.mimiraether/tmp/d.md") is False  # 但不是交付物
    assert erg.readonly_streak(msgs) == 5   # 新版不再 break ⇒ 预算未退还


# ── 交付物写 ⇒ 清零 + 不触发 ─────────────────────────────────────────
def test_deliverable_write_resets():
    msgs = turns(READ, READ, READ, READ, DELIV)
    assert erg.turn_deliverable_written(msgs[-1]["tool_calls"]) is True
    assert erg.readonly_streak(msgs) == 0
    assert erg.EmptyRunGate(task_id="t", limit=4, force_writes=0).tick(msgs, 5) is None


# ── 别名路径（变量化写）识别 ─────────────────────────────────────────
def test_alias_variable_path_is_deliverable():
    msgs = turns(READ, READ, READ, READ, DELIV_VAR)
    assert erg.deliverable_written(msgs) is True
    assert erg.readonly_streak(msgs) == 0


def test_alias_read_only_open_is_not_write():
    raw = json.dumps({"code": "p = pathlib.Path('/repo/x.md')\np.open('r').read()"})
    assert erg.write_targets("execute_code", raw) == []


# ── 硬限（机制）────────────────────────────────────────────────────
def test_hard_limit_blocks_readonly_not_write(monkeypatch):
    monkeypatch.delenv("MIMIR_READONLY_HARD_LIMIT", raising=False)
    assert erg.readonly_hard_limit() == erg.readonly_turn_limit() * 3
    g = erg.EmptyRunGate(task_id="t", limit=4, force_writes=0)
    g.streak = erg.readonly_hard_limit()
    assert g.should_block_readonly("read_file", '{"path": "x"}') is True
    assert g.should_block_readonly("search_files", '{"pattern": "x"}') is True
    assert g.should_block_readonly("write_file", '{"path": "x"}') is False
    g.streak = erg.readonly_hard_limit() - 1
    assert g.should_block_readonly("read_file", "{}") is False


def test_hard_limit_off(monkeypatch):
    monkeypatch.setenv("MIMIR_READONLY_HARD_LIMIT", "0")
    g = erg.EmptyRunGate(task_id="t", limit=4, force_writes=0)
    g.streak = 999
    assert g.should_block_readonly("read_file", "{}") is False


def test_hard_limit_garbage_falls_back(monkeypatch):
    monkeypatch.setenv("MIMIR_READONLY_HARD_LIMIT", "abc")
    assert erg.readonly_hard_limit() == erg.readonly_turn_limit() * 3


def test_build_blocked_result_names_tool():
    txt = erg.build_blocked_result("read_file", 13, 12)
    assert "read_file" in txt and "硬限" in txt


# ── ignored 计数（升级信号）─────────────────────────────────────────
def test_ignored_counter_and_reset():
    g = erg.EmptyRunGate(task_id="t", limit=4, force_writes=0)
    msgs = turns(READ, READ, READ, READ)
    assert g.tick(msgs, 4) and g.ignored == 1
    msgs = turns(READ, READ, READ, READ, READ)
    g.tick(msgs, 5)
    assert g.ignored == 2
    g.tick(turns(READ), 1)              # 回落到预算内 ⇒ 复位
    assert g.ignored == 0
