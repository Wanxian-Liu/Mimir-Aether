"""F2 alerts 读口 · 正负控（scripts/check_run_health_alerts.py）。

纪律：**只证明「坏样本被拒」不算数** —— 必须同时证明「好样本不被误拦」。
故本文件两侧都测：负控（缺失 / 坏行 / 已 fire 但台账缺）必须出声；
孪生（空台账 / 从未越线 / 非主机）必须 rc 0 **且明示**（禁空白静默）。

本文件**不使用 skip/xfail**（禁刷绿）—— 所有断言在任意主机上都真跑。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_run_health_alerts as gate  # noqa: E402

SCRIPT = ROOT / "scripts" / "check_run_health_alerts.py"
TS = "2026-10-07T02:48:32"


def _alert(ts=TS, kind="max_turns"):
    return json.dumps({"ts": ts, "date": "2026-10-07", "kind": kind,
                       "reason": "%s=1>=1" % kind, "counts": {"runs": 14}})


def _ledger(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _cli(*args, home=None):
    env = dict(os.environ)
    env["HOME"] = "/home/rayliu"
    if home:
        env["MIMIR_AETHER_HOME"] = str(home)
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, env=env, cwd=str(ROOT))


# --- 负控（坏样本必须出声）----------------------------------------------

def test_missing_ledger_is_missing_rc3(tmp_path):
    s, rc, _out = gate._probe(tmp_path / "nope.jsonl")
    assert (s["state"], rc) == ("MISSING", gate.RC_UNREADABLE)


def test_corrupt_line_is_parse_error_rc4(tmp_path):
    p = _ledger(tmp_path, "c.jsonl", _alert() + "\n{oops\n")
    s, rc, _out = gate._probe(p)
    assert s["state"] == "PARSE_ERROR" and rc == gate.RC_PARSE_ERROR
    assert s["bad_lines"] == [2]
    assert s["n"] == 1  # 已解析部分仍上报 —— 禁「一坏全隐」


def test_diagnosis_fired_but_ledger_gone_is_missing(tmp_path):
    home = tmp_path / "h"
    (home / "data" / "ops").mkdir(parents=True)
    (home / "data" / "ops" / "run_health_state.json").write_text(
        json.dumps({"alerted": {"2026-10-07": {"max_turns": True}}}), encoding="utf-8")
    s, rc, _out = gate._probe(tmp_path / "nope.jsonl", home=home)
    assert (s["state"], rc) == ("MISSING", gate.RC_UNREADABLE)


# --- 孪生（好样本不得误拦，且必须明示）-----------------------------------

def test_empty_ledger_is_none_rc0_and_explicit(tmp_path):
    s, rc, out = gate._probe(_ledger(tmp_path, "e.jsonl", ""))
    assert (s["state"], rc) == ("NONE", gate.RC_NONE)
    assert "NONE" in out and out.strip()  # 明示「无告警」，禁空白静默


def test_healthy_ledger_is_alert_rc2(tmp_path):
    s, rc, out = gate._probe(_ledger(tmp_path, "g.jsonl", _alert() + "\n"))
    assert (s["state"], rc) == ("ALERT", gate.RC_ALERTS)
    assert "max_turns" in out and TS in out


def test_window_filter_excludes_old_alert(tmp_path):
    p = _ledger(tmp_path, "g.jsonl", _alert(ts="2020-01-01T00:00:00") + "\n")
    kept, undated = gate.select(gate.read_alerts(p)[0], gate.parse_window("1m"))
    assert kept == [] and undated == 0


def test_diagnosis_skip_when_not_a_mimir_host(tmp_path):
    s, rc, out = gate._probe(tmp_path / "nope.jsonl", home=tmp_path / "nohome")
    assert (s["state"], rc) == ("SKIP", gate.RC_NONE)
    assert "SKIP" in out


def test_diagnosis_no_alerts_yet_when_never_fired(tmp_path):
    home = tmp_path / "h"
    (home / "data" / "ops").mkdir(parents=True)
    (home / "data" / "ops" / "run_health_state.json").write_text(
        json.dumps({"alerted": {}}), encoding="utf-8")
    s, rc, _out = gate._probe(tmp_path / "nope.jsonl", home=home)
    assert (s["state"], rc) == ("NO_ALERTS_YET", gate.RC_NONE)


# --- CLI 端到端（rc 语义 + 出声面不依赖人工开文件）------------------------

def test_cli_selftest_all_pass():
    r = _cli("--selftest")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[selftest] ALL PASS" in r.stdout
    assert "HAS FAILURE" not in r.stdout


def test_cli_selftest_covers_both_arms():
    out = _cli("--selftest").stdout
    assert out.count("[selftest] PASS") >= 8
    assert "\u574f1" in out and "\u5b6a1" in out


def test_cli_missing_is_not_blank(tmp_path):
    r = _cli("--path", str(tmp_path / "nope.jsonl"))
    assert r.returncode == gate.RC_UNREADABLE
    assert r.stdout.strip(), "\u7981\u7a7a\u767d\u9759\u9ed8"


def test_cli_never_silently_blank_any_host():
    r = _cli()
    assert "RUN_HEALTH_ALERTS:" in r.stdout


def test_cli_json_mode_keeps_rc_semantics(tmp_path):
    p = _ledger(tmp_path, "g.jsonl", _alert() + "\n")
    r = _cli("--path", str(p), "--json")
    assert r.returncode == gate.RC_ALERTS
    payload = json.loads(r.stdout)
    assert payload["state"] == "ALERT" and payload["n"] == 1


def test_cli_gate_mode_alert_prints_but_rc0(tmp_path):
    p = _ledger(tmp_path, "g.jsonl", _alert() + "\n")
    r = _cli("--path", str(p), "--gate")
    assert r.returncode == 0
    assert "ALERT" in r.stdout  # gate 只放宽判死，不吞宣告


def test_cli_gate_mode_still_fails_on_corruption(tmp_path):
    p = _ledger(tmp_path, "c.jsonl", _alert() + "\n{oops\n")
    r = _cli("--path", str(p), "--gate")
    assert r.returncode == gate.RC_PARSE_ERROR


def test_cli_gate_mode_still_fails_on_missing_ledger(tmp_path):
    r = _cli("--path", str(tmp_path / "nope.jsonl"), "--gate")
    assert r.returncode == gate.RC_UNREADABLE
