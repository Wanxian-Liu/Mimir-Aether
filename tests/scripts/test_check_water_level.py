"""F3 · 水位阈值出声 —— 判据回归（第 9 单 · A 档 #4 · 2026-10-07）。

四条判据各一对（坏病例 + 孪生对照，禁恒真）：
  1 越阈 => 出声：stdout 首行明示 OVER + rc=2
  2 未越阈 => 不误报：rc=0（孪生对照）
  3 台账 append-only：两次越阈 => 行数 +1（不是覆盖改写）
  4 复用现成：取数来自 tools.memory_tool / agent.context_usage_snapshot /
    scripts.check_memory_hygiene（不新造第二套水位）；未越阈不写台账。

`--home` 覆盖：测试全部用合成 home，不碰真记忆、不碰真台账。
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_water_level.py"
LEDGER = "water_level_events.jsonl"


def _run(args, cwd=None):
    env = dict(os.environ)
    # 显式 HOME（防沙箱 HOME 语义漂移）；--home 已覆盖读数面，故 HOME 不影响读数。
    env.setdefault("HOME", str(pathlib.Path.home()))
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True, text=True, cwd=str(cwd or REPO), env=env,
    )


def _home(tmp_path, *, mem_chars, total, threshold=300000, user_chars=0):
    (tmp_path / "memories").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "ops").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memories" / "MEMORY.md").write_text("x" * mem_chars, encoding="utf-8")
    if user_chars:
        (tmp_path / "memories" / "USER.md").write_text("y" * user_chars, encoding="utf-8")
    (tmp_path / "data" / "ops" / "last_context_usage.json").write_text(
        json.dumps({"total_tokens": total, "threshold_tokens": threshold,
                    "caliber": "synth@1M/thr=%d" % threshold, "writer_kind": "main"}),
        encoding="utf-8",
    )
    return tmp_path


def _ledger_lines(home):
    p = home / "data" / "ops" / LEDGER
    if not p.exists():
        return 0
    return len([ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()])



def test_selftest_all_pass():
    r = _run(["--selftest"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ALL PASS" in r.stdout
    # 注意：判据名含 "LEDGER_FAIL" 字样 —— 只能按行首标记判，不能裸查 "FAIL"。
    assert "[selftest] FAIL" not in r.stdout
    assert "HAS FAILURE" not in r.stdout


def test_over_threshold_alerts_with_nonzero_rc(tmp_path):
    h = _home(tmp_path, mem_chars=7100, total=1000)  # 88.8% > 85%
    r = _run(["--home", str(h)])
    assert r.returncode == 2, r.stdout + r.stderr
    assert r.stdout.splitlines()[0].startswith("WATER_LEVEL: OVER"), r.stdout
    assert "<== OVER" in r.stdout
    assert _ledger_lines(h) == 1


def test_under_threshold_no_false_alarm(tmp_path):
    h = _home(tmp_path, mem_chars=100, total=1000)
    r = _run(["--home", str(h)])
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines()[0].startswith("WATER_LEVEL: OK"), r.stdout
    assert _ledger_lines(h) == 0, "未越阈不得写台账（防噪音）"


def test_ledger_append_only(tmp_path):
    h = _home(tmp_path, mem_chars=7100, total=1000)
    assert _run(["--home", str(h)]).returncode == 2
    first = (h / "data" / "ops" / LEDGER).read_text(encoding="utf-8")
    assert _ledger_lines(h) == 1
    assert _run(["--home", str(h)]).returncode == 2
    after = (h / "data" / "ops" / LEDGER).read_text(encoding="utf-8")
    assert _ledger_lines(h) == 2, "append-only：两次越阈 => 行数 +1"
    assert after.startswith(first), "旧行必须保留（append 不是覆盖改写）"


def test_session_over_threshold_alerts(tmp_path):
    h = _home(tmp_path, mem_chars=100, total=300000, threshold=300000)
    r = _run(["--home", str(h)])
    assert r.returncode == 2, r.stdout + r.stderr
    sess = [ln for ln in r.stdout.splitlines() if ln.strip().startswith("session:")]
    assert sess and "<== OVER" in sess[0], r.stdout


def test_no_ledger_flag_reports_without_writing(tmp_path):
    h = _home(tmp_path, mem_chars=7100, total=1000)
    r = _run(["--home", str(h), "--no-ledger"])
    assert r.returncode == 2, r.stdout + r.stderr
    assert _ledger_lines(h) == 0


def test_rc_semantics_documented():
    """rc 语义不可裁剪：0/2/3/4 四态在源码中明示。"""
    src = SCRIPT.read_text(encoding="utf-8")
    for frag in ("RC_OK, RC_OVER, RC_UNREADABLE, RC_LEDGER_FAIL = 0, 2, 3, 4",
                 "UNREADABLE(3) > LEDGER_FAIL(4) > OVER(2) > OK(0)"):
        assert frag in src, frag


def test_reuses_existing_meters_no_second_water_level_system():
    """判据 4：取数复用现成读数器（禁新造第二套水位系统）。"""
    src = SCRIPT.read_text(encoding="utf-8")
    for frag in ("from tools.memory_tool import MAX_ENTRY_CHARS, get_memory_store",
                 "from agent.context_usage_snapshot import read_context_usage_snapshot",
                 "from check_memory_hygiene import USAGE_LIMIT_PCT"):
        assert frag in src, frag
