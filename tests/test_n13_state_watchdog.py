"""N13 段1 · 看门狗两向 mock（卡 L772 正控 / L773 负控）+ 幂等 + 零改卡。

重跑（cwd = 仓根）:
    bash scripts/pytest_isolated.sh tests/test_n13_state_watchdog.py -q
"""
import hashlib
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import state_event_log as sel        # noqa: E402
import state_watchdog as sw          # noqa: E402


def _n(lines, prefix):
    return sum(1 for ln in lines if ln.startswith(prefix))


def test_l772_positive_2x_deadline_reports_one_stalled_one_alert(tmp_path):
    """L772 正控：last_event_at = now − 2×deadline ⇒ 1 行 stalled + 1 行报警。"""
    r = sw._arm(str(tmp_path), primary_state="in_progress",
                primary_age_s=2 * 3600.0, extra_card="N902")   # 卡内 deadline: 1h
    assert _n(r["lines"], "stalled:") == 1
    assert _n(r["lines"], "alert:") == 1
    assert r["heartbeat"]["stalled"] == 1
    assert sel.line_count(r["alerts_path"]) == 1
    assert "N901" in r["lines"][0]
    assert "silent_s=7200 deadline_s=3600" in r["lines"][0]


def test_l773_negative_now_reports_zero(tmp_path):
    """L773 负控：last_event_at = now ⇒ 0 行 stalled / 0 行报警。"""
    r = sw._arm(str(tmp_path), primary_state="in_progress", primary_age_s=0.0)
    assert _n(r["lines"], "stalled:") == 0
    assert _n(r["lines"], "alert:") == 0
    assert r["heartbeat"]["stalled"] == 0
    assert sel.line_count(r["alerts_path"]) == 0


def test_negative_waiting_human_never_alerts(tmp_path):
    """等人态无 deadline ⇒ 沉默 365 天也不报（等人不是停摆）。"""
    r = sw._arm(str(tmp_path), primary_state="awaiting_decision",
                primary_age_s=365 * 86400.0, primary_deadline="")
    assert _n(r["lines"], "stalled:") == 0


def test_event_append_is_idempotent(tmp_path):
    """幂等：同一事件重放（换 ts）⇒ 行数不涨。"""
    p = str(tmp_path / "e.jsonl")
    rec = {"card_id": "NX", "from": "pending", "to": "in_progress",
           "event": "deps_all_closed", "actor": "hermes", "trace_id": "t"}
    assert sel.append_event(dict(rec), path=p, ts=1.0) == "appended"
    assert sel.append_event(dict(rec), path=p, ts=2.0) == "duplicate"
    assert sel.line_count(p) == 1
    assert sel.last_event_at("NX", p) == 1.0


def test_watchdog_never_modifies_ledger(tmp_path):
    """零改卡：跑一 tick 前后，卡文件 sha256 不变。"""
    sw._arm(str(tmp_path), primary_state="in_progress", primary_age_s=2 * 3600.0)
    ledger = str(tmp_path / "ledger.md")
    before = hashlib.sha256(open(ledger, "rb").read()).hexdigest()
    sw.tick(ledger=ledger, events=str(tmp_path / "state-events.jsonl"),
            alerts=str(tmp_path / "a.jsonl"), heartbeat=str(tmp_path / "hb.json"),
            now=sw.MOCK_NOW)
    after = hashlib.sha256(open(ledger, "rb").read()).hexdigest()
    assert before == after


def test_preflight_guard_is_loud_on_bad_paths(tmp_path):
    """前置闸两向：ledger 缺失 rc=2 / 扫到 0 张卡 rc=3 / 正常 rc=0。"""
    missing = str(tmp_path / "nope.md")
    assert sw.preflight_guard(missing, [])[0] == 2          # 台账缺失 ⇒ 出声
    assert sw.preflight_guard(missing, [{"card_id": "N1"}])[0] == 2   # 缺件优先于有卡
    empty = str(tmp_path / "empty.md")
    open(empty, "w").write("no yaml here\n")
    assert sw.preflight_guard(empty, [])[0] == 3            # 扫到 0 张卡 ⇒ 出声
    assert sw.preflight_guard(empty, [{"card_id": "N1"}])[0] == 0     # 有卡 ⇒ 过闸


def test_heartbeat_rc_semantics(tmp_path):
    """心跳两向：缺失 rc=1 / 新鲜 rc=0 / 过期 rc=1。"""
    p = str(tmp_path / "hb.json")
    assert sw.check_heartbeat(p, 900)[0] == 1
    open(p, "w").write('{"ts": 1000.0, "tick": 1}')
    assert sw.check_heartbeat(p, 900, now=1010.0)[0] == 0
    assert sw.check_heartbeat(p, 900, now=5000.0)[0] == 1
