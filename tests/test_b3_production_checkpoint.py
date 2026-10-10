"""B3 防截断 · 回归用例（2026-10-06 · 刘哥派单）

三条规则的受控差分：
  ① 轮次用满 ~80% 仍未落盘 ⇒ 强制先写「半段」（幂等，每阈值一次）
  ② >60 轮大活 ⇒ 落盘交棒（max_turns<=60 不触发）
  ③ 「产出后即刻补账」= 可跑检查（rc 0/2/3），不是承诺
外加收尾兜底：轮次类退出仍零落盘 ⇒ 框架代写半段（复用空跑闸 flush，草稿优先）。

用受控差分：同一 policy 只换 (turn, has_written) 两个自变量。
"""
import os
import subprocess
import sys

import pytest

from agent import iteration_budget as ib


READ_ONLY_TURN = {
    "role": "assistant", "content": "",
    "tool_calls": [{"id": "c1", "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path": "/tmp/x.py"}'}}],
}
WRITE_TURN = {
    "role": "assistant", "content": "",
    "tool_calls": [{"id": "c2", "type": "function",
                    "function": {"name": "write_file", "arguments": '{"path": "~/wiki/discussions/card.md", "content": "x"}'}}],
}


def _policy(max_turns, written=False, **kw):
    return ib.ProductionCheckpointPolicy(
        max_turns=max_turns, task_id="t-test", has_written=lambda _m: written, **kw)


def _msgs(with_write=False):
    m = [{"role": "user", "content": "任务书"}, READ_ONLY_TURN]
    if with_write:
        m.append(WRITE_TURN)
    return m


# ───────────────────────── 阈值（纯函数） ─────────────────────────

def test_half_segment_threshold_ceil():
    assert ib.half_segment_threshold(90, 0.8) == 72
    assert ib.half_segment_threshold(120, 0.8) == 96
    assert ib.half_segment_threshold(10, 0.8) == 8
    assert ib.half_segment_threshold(1, 0.8) == 1
    assert ib.half_segment_threshold(0, 0.8) == 1


# ───────────────────────── 规则① 半段 ─────────────────────────

def test_rule1_fires_at_threshold_only_when_unwritten():
    p = _policy(90, written=False, handoff=0)   # 隔离规则②（否则 turn>=60 先被交棒截走）
    assert p.tick(_msgs(), 71) is None          # 差一轮 ⇒ 不触发
    d = p.tick(_msgs(), 72)                     # 阈值 ⇒ 触发
    assert d and "半段" in d and "未闭项" in d
    assert p.half_fired is True


def test_rule1_silent_when_already_written():
    p = _policy(90, written=True, handoff=0)
    for t in (72, 80, 89, 90):
        assert p.tick(_msgs(with_write=True), t) is None
    assert p.half_fired is False


def test_rule1_idempotent():
    p = _policy(90, written=False, handoff=0)
    assert p.tick(_msgs(), 72) is not None
    assert p.tick(_msgs(), 73) is None
    assert p.tick(_msgs(), 90) is None
    kinds = [d["kind"] for d in p.decisions]
    assert kinds.count("half_segment") == 1


# ───────────────────────── 规则② 交棒 ─────────────────────────

def test_rule2_handoff_fires_once_for_large_task():
    p = _policy(120, written=True)
    d = p.tick(_msgs(with_write=True), 60)
    assert d and "交棒" in d
    assert p.tick(_msgs(with_write=True), 61) is None
    assert [x["kind"] for x in p.decisions] == ["handoff"]


def test_rule2_not_fired_when_max_turns_le_60():
    p = _policy(60, written=True)
    for t in (59, 60):
        assert p.tick(_msgs(with_write=True), t) is None


# ───────────────────────── env 回滚 ─────────────────────────

def test_disabled_by_env(monkeypatch):
    monkeypatch.setenv("MIMIR_B3_GUARD", "0")
    p = _policy(90, written=False, handoff=0)
    assert p.tick(_msgs(), 90) is None
    assert p.decisions == []


# ───────────────────────── 收尾兜底：框架代写半段 ─────────────────────────

def test_framework_half_segment_written_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    msgs = _msgs() + [{"role": "assistant", "content": "半句：我正准备写卡…"}]
    r = ib.write_framework_half_segment(
        task_id="run-abc", turn=90, max_turns=90, reason="max_turns",
        messages=msgs, last_assistant="半句：我正准备写卡…")
    assert r["written"] is True
    body = open(r["path"], encoding="utf-8").read()
    assert "框架代写" in body and "未闭项清单" in body and "半句：我正准备写卡" in body
    assert "read_file" in body                      # 已确证读数（实际工具调用）
    r2 = ib.write_framework_half_segment(
        task_id="run-abc", turn=90, max_turns=90, reason="max_turns", messages=msgs)
    assert r2["written"] is False and r2["reason"] == "already_written"


def test_core_loop_flush_skips_when_deliverable_written(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    from agent.core_loop import _b3_flush_half_segment
    class _R:
        turns_used = 42
    out = _b3_flush_half_segment(_R(), _msgs(with_write=True), "run-x", "max_turns", 90)
    assert out is None


def test_core_loop_flush_writes_framework_half_segment(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    from agent.core_loop import _b3_flush_half_segment
    class _R:
        turns_used = 90
    out = _b3_flush_half_segment(_R(), _msgs(), "run-y", "max_turns", 90)
    assert out and out["mode"] == "framework" and len(out["targets"]) == 1
    assert os.path.exists(out["targets"][0])


def test_core_loop_flush_disabled_by_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_B3_GUARD", "0")
    from agent.core_loop import _b3_flush_half_segment
    class _R:
        turns_used = 90
    assert _b3_flush_half_segment(_R(), _msgs(), "run-z", "max_turns", 90) is None


# ───────────────────────── 规则③ 补账可跑检查（rc 语义） ─────────────────────────

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "check_inbox_ledger_lag.py")


def _run_check(tmp_path, inbox_lines, watermark):
    inbox = tmp_path / "inbox.jsonl"
    inbox.write_text("".join('{"i": %d}\n' % i for i in range(inbox_lines)), encoding="utf-8")
    ledger = tmp_path / "inbox-processed.log"
    ledger.write_text("2026-10-06 19:00:00 processed 1 lines (up to %d)\n" % watermark,
                      encoding="utf-8")
    return subprocess.run([sys.executable, SCRIPT, "--inbox", str(inbox), "--ledger", str(ledger)],
                          capture_output=True, text=True)


def test_rule3_rc0_when_caught_up(tmp_path):
    r = _run_check(tmp_path, 221, 221)
    assert r.returncode == 0 and "lag=0" in r.stdout


def test_rule3_rc2_when_lag(tmp_path):
    r = _run_check(tmp_path, 222, 221)
    assert r.returncode == 2 and "欠账 1 行" in r.stdout and "222" in r.stdout


def test_rule3_rc3_when_instrument_missing(tmp_path):
    r = subprocess.run([sys.executable, SCRIPT, "--inbox", str(tmp_path / "nope.jsonl"),
                        "--ledger", str(tmp_path / "nope.log")], capture_output=True, text=True)
    assert r.returncode == 3 and "量具不可用" in r.stdout


def test_real_sequence_handoff_then_half_segment():
    """90 轮大活且零落盘：turn 60 交棒 ⇒ turn 72 半段；中间轮次静默。"""
    p = _policy(90, written=False)
    assert p.tick(_msgs(), 59) is None
    assert "交棒" in (p.tick(_msgs(), 60) or "")
    assert p.tick(_msgs(), 71) is None
    assert "半段" in (p.tick(_msgs(), 72) or "")
    assert [d["kind"] for d in p.decisions] == ["handoff", "half_segment"]


def test_rule3_ledger_resolves_via_mimir_aether_home(tmp_path):
    """回归：台账默认路径须 HOME 无关（曾因裸 expanduser 在非真实家目录 HOME 下误报 rc=3）。"""
    home = tmp_path / "mh"
    (home / "logs").mkdir(parents=True)
    (home / "logs" / "inbox-processed.log").write_text(
        "2026-10-06 20:00:00 processed 1 lines (up to 5)\n", encoding="utf-8")
    inbox = tmp_path / "inbox.jsonl"
    inbox.write_text("".join('{"i": %d}\n' % i for i in range(5)), encoding="utf-8")
    env = dict(os.environ, MIMIR_AETHER_HOME=str(home), HOME=str(tmp_path / "fakehome"))
    env.pop("MIMIR_LEDGER", None)
    r = subprocess.run([sys.executable, SCRIPT, "--inbox", str(inbox)],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "lag=0" in r.stdout, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# 规则③ 治本件：补账必须同步 .hwm（否则 patrol L213 报「⚠陈旧水位」= 幻影告警）
# 2026-10-06 行 229 实测：手工 append 只动台账不动 hwm ⇒ led=158 vs hwm=156 漂移。
# ---------------------------------------------------------------------------
APPENDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "scripts", "append_inbox_processed.py")


def _seed(tmp_path, seed_lines=1, hwm="1"):
    led = tmp_path / "inbox-processed.log"
    led.write_text("2026-10-06 20:00:00 processed 1 lines (up to 5)\n", encoding="utf-8")
    (tmp_path / "inbox-processed.log.hwm").write_text(hwm + "\n", encoding="utf-8")
    return led


def test_appender_appends_and_syncs_hwm(tmp_path):
    """补账一行 ⇒ 台账 +1 行 ∧ `.hwm` 同步到新行数（不变量 wc-l == hwm 成立）。"""
    led = _seed(tmp_path)
    r = subprocess.run([sys.executable, APPENDER, "--ledger", str(led),
                        "-m", "[pytest] smoke", "--up-to", "6"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = led.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and "up to 6" in lines[-1] and "[pytest] smoke" in lines[-1]
    assert (tmp_path / "inbox-processed.log.hwm").read_text().strip() == "2"


def test_appender_dry_run_writes_nothing(tmp_path):
    """--dry-run ⇒ rc 0 但台账与 hwm 均不变（控制组：防「预演顺手写盘」）。"""
    led = _seed(tmp_path)
    r = subprocess.run([sys.executable, APPENDER, "--ledger", str(led),
                        "-m", "x", "--up-to", "6", "--dry-run"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(led.read_text(encoding="utf-8").splitlines()) == 1
    assert (tmp_path / "inbox-processed.log.hwm").read_text().strip() == "1"


def test_appender_sync_hwm_subcommand(tmp_path):
    """--sync-hwm 只对齐 hwm 到当前行数（治漂移的兜底入口）。"""
    led = _seed(tmp_path, hwm="1")
    with open(led, "a", encoding="utf-8") as fh:
        fh.write("2026-10-06 21:00:00 processed 1 lines (up to 9) [x]\n")
    r = subprocess.run([sys.executable, APPENDER, "--ledger", str(led), "--sync-hwm"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "inbox-processed.log.hwm").read_text().strip() == "2"


def test_appender_bad_args_rc3(tmp_path):
    """缺 --up-to / 非整数 / message 含换行 ⇒ rc=3（不得静默按 0 行记账）。"""
    led = _seed(tmp_path)
    for args in (["-m", "x"], ["-m", "x", "--up-to", "abc"], ["-m", "a\nb", "--up-to", "7"]):
        r = subprocess.run([sys.executable, APPENDER, "--ledger", str(led), *args],
                           capture_output=True, text=True)
        assert r.returncode == 3, (args, r.stdout + r.stderr)
    assert len(led.read_text(encoding="utf-8").splitlines()) == 1


def test_appender_missing_ledger_rc3(tmp_path):
    """台账缺失 ⇒ rc=3（量具不可用，不得读成「已补账」）。"""
    r = subprocess.run([sys.executable, APPENDER, "--ledger", str(tmp_path / "nope.log"),
                        "-m", "x", "--up-to", "7"], capture_output=True, text=True)
    assert r.returncode == 3, r.stdout + r.stderr
