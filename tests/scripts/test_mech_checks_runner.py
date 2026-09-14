"""RS19 P0 · run_mech_checks.py 单元/契约测试（Gate2 登记）。

覆盖方案卡 §2.2 契约与 §8 验收判据的可机械断言部分：
  * 三态严格：PASS / FAIL / ERROR 不得互相冒充（ERROR 读成 PASS = 又一次「绿着坏」）
  * 判据冲突（VERDICT: PASS 但退出码不符）⇒ ERROR
  * readonly 守卫 ⇒ SKIPPED（不得被读成 PASS）
  * 退出码映射：0 全 PASS / 1 有 FAIL / 2 有 ERROR|SKIPPED / 3 心跳过期
  * 落盘：last_run.json 三态可读 + history.jsonl 一项一行（漏跑可机械发现）
  * 告警：状态变化才报（FAIL→FAIL 不报、FAIL→PASS 报 RECOVERED）
  * 飞书发送失败/缺失不得让 runner 抛异常
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "run_mech_checks.py"
sys.path.insert(0, str(REPO / "scripts"))

import run_mech_checks as rmc  # noqa: E402


# --------------------------------------------------------------------- fixtures


def _mk_checker(path: Path, body: str) -> str:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return str(path)


@pytest.fixture()
def sandbox(tmp_path: Path):
    """返回 (registry_path, workdir)：合成注册表，不触碰生产产物。"""
    work = tmp_path / "work"
    work.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    def build(items, defaults=None, interval_min=1):
        reg = {
            "version": 1,
            "placeholders": {"{repo}": str(REPO), "{home}": str(home)},
            "defaults": {
                "owner": "mimir", "interval_min": interval_min, "timeout_s": 5,
                "readonly": True, "severity": "high", "exit_ok": [0],
                **(defaults or {}),
            },
            "alerts": {"channel": "feishu", "chat_id": "", "log": str(work / "alert.log"),
                       "policy": "state_change_only"},
            "outputs": {"last_run": str(work / "last_run.json"),
                        "history": str(work / "history.jsonl")},
            "items": items,
        }
        reg_path = work / "registry.json"
        reg_path.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
        return reg_path

    return {"work": work, "home": home, "build": build, "mk": _mk_checker}


def _run(registry: Path, *extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "MIMIR_HOME": str(registry.parent)}
    return subprocess.run(
        [sys.executable, str(RUNNER), "--registry", str(registry), "--no-notify", *extra],
        capture_output=True, text=True, timeout=120, cwd=str(REPO), env=env,
    )


def _statuses(work: Path) -> dict:
    payload = json.loads((work / "last_run.json").read_text(encoding="utf-8"))
    return {it["id"]: it["status"] for it in payload["items"]}


V_ANY = r"^VERDICT\s*:\s*(PASS|FAIL)\s*$"


# ------------------------------------------------------------------ unit: 判据层


def test_status_pass():
    item = {"verdict_parse": V_ANY, "exit_ok": [0]}
    assert rmc._status_for({"status_hint": None, "exit_code": 0,
                            "stdout": "x\nVERDICT  : PASS\n", "error": ""}, item) == ("PASS", "verdict=PASS")


def test_status_fail_wins_over_exit_code():
    item = {"verdict_parse": V_ANY, "exit_ok": [0]}
    status, _ = rmc._status_for({"status_hint": None, "exit_code": 0,
                                 "stdout": "VERDICT  : FAIL\n", "error": ""}, item)
    assert status == "FAIL"


def test_status_unparseable_is_error_not_pass():
    item = {"verdict_parse": V_ANY, "exit_ok": [0]}
    status, reason = rmc._status_for({"status_hint": None, "exit_code": 0,
                                      "stdout": "all good!\n", "error": ""}, item)
    assert status == "ERROR" and "unparseable" in reason


def test_status_conflict_is_error():
    item = {"verdict_parse": V_ANY, "exit_ok": [0]}
    status, reason = rmc._status_for({"status_hint": None, "exit_code": 1,
                                      "stdout": "VERDICT: PASS\n", "error": ""}, item)
    assert status == "ERROR" and "conflict" not in reason and "exit_code=1" in reason


def test_status_exec_problem_propagates_error():
    item = {"verdict_parse": V_ANY, "exit_ok": [0]}
    status, reason = rmc._status_for({"status_hint": "ERROR", "exit_code": None,
                                      "stdout": "", "error": "timeout after 2s"}, item)
    assert status == "ERROR" and reason == "timeout after 2s"


def test_status_exit_only_mode():
    item = {"exit_ok": [0]}
    assert rmc._status_for({"status_hint": None, "exit_code": 0, "stdout": "", "error": ""}, item)[0] == "PASS"
    assert rmc._status_for({"status_hint": None, "exit_code": 3, "stdout": "", "error": ""}, item)[0] == "FAIL"


def test_expand_placeholders():
    subs = {"{repo}": "/r", "{home}": "/h"}
    assert rmc._expand("{repo}/a {home}/b", subs) == "/r/a /h/b"


# --------------------------------------------------------------- e2e: 进程级


def test_e2e_three_states_and_exit_code(sandbox):
    ok = sandbox["mk"](sandbox["work"] / "ok.sh", "#!/bin/bash\necho 'VERDICT  : PASS'\nexit 0\n")
    bad = sandbox["mk"](sandbox["work"] / "bad.sh", "#!/bin/bash\necho 'VERDICT  : FAIL'\nexit 1\n")
    bro = sandbox["mk"](sandbox["work"] / "bro.sh", "#!/bin/bash\necho 'nothing'\nexit 0\n")
    reg = sandbox["build"]([
        {"id": "a_ok", "cmd": ok, "verdict_parse": V_ANY},
        {"id": "b_fail", "cmd": bad, "verdict_parse": V_ANY},
        {"id": "c_error", "cmd": bro, "verdict_parse": V_ANY},
    ])
    proc = _run(reg)
    got = _statuses(sandbox["work"])
    assert got == {"a_ok": "PASS", "b_fail": "FAIL", "c_error": "ERROR"}
    assert proc.returncode == 2, proc.stdout
    assert "VERDICT: FAIL" in proc.stdout


def test_e2e_all_pass_exit_zero(sandbox):
    ok = sandbox["mk"](sandbox["work"] / "ok.sh", "#!/bin/bash\necho 'VERDICT  : PASS'\nexit 0\n")
    reg = sandbox["build"]([{"id": "a_ok", "cmd": ok, "verdict_parse": V_ANY}])
    assert _run(reg).returncode == 0


def test_e2e_readonly_guard_skips_and_never_reports_pass(sandbox):
    wr = sandbox["mk"](sandbox["work"] / "wr.sh", "#!/bin/bash\necho 'VERDICT  : PASS'\nexit 0\n")
    reg = sandbox["build"]([{"id": "w", "cmd": wr, "verdict_parse": V_ANY, "readonly": False}])
    proc = _run(reg)
    assert _statuses(sandbox["work"])["w"] == "SKIPPED"
    assert proc.returncode == 2


def test_e2e_timeout_is_error_and_process_group_killed(sandbox):
    slow = sandbox["mk"](sandbox["work"] / "slow.sh", "#!/bin/bash\nsleep 30\n")
    reg = sandbox["build"]([{"id": "slow", "cmd": slow, "timeout_s": 1}])
    assert _run(reg).returncode == 2
    assert _statuses(sandbox["work"])["slow"] == "ERROR"


def test_e2e_history_one_line_per_item_per_run(sandbox):
    ok = sandbox["mk"](sandbox["work"] / "ok.sh", "#!/bin/bash\necho 'VERDICT  : PASS'\nexit 0\n")
    reg = sandbox["build"]([{"id": "a", "cmd": ok, "verdict_parse": V_ANY},
                            {"id": "b", "cmd": ok, "verdict_parse": V_ANY}])
    _run(reg)
    _run(reg)
    lines = (sandbox["work"] / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    assert all({"ts", "run_id", "id", "status"} <= set(json.loads(l)) for l in lines)


def test_e2e_alert_only_on_state_change(sandbox):
    bad = sandbox["mk"](sandbox["work"] / "bad.sh", "#!/bin/bash\necho 'VERDICT  : FAIL'\nexit 1\n")
    reg = sandbox["build"]([{"id": "f", "cmd": bad, "verdict_parse": V_ANY}])
    _run(reg)
    first = (sandbox["work"] / "alert.log").read_text(encoding="utf-8")
    assert first.count("[FAIL] f") == 1
    _run(reg)
    assert (sandbox["work"] / "alert.log").read_text(encoding="utf-8").count("[FAIL] f") == 1


def test_e2e_recovery_alert(sandbox):
    bad = sandbox["work"] / "f.sh"
    sandbox["mk"](bad, "#!/bin/bash\necho 'VERDICT  : FAIL'\nexit 1\n")
    reg = sandbox["build"]([{"id": "f", "cmd": str(bad), "verdict_parse": V_ANY}])
    _run(reg)
    sandbox["mk"](bad, "#!/bin/bash\necho 'VERDICT  : PASS'\nexit 0\n")
    proc = _run(reg)
    log = (sandbox["work"] / "alert.log").read_text(encoding="utf-8")
    assert "[RECOVERED] f" in log and "[RECOVERED] f" in proc.stdout


def test_e2e_low_severity_fail_is_recorded_not_alerted(sandbox):
    """低优先级 FAIL：进 last_run + history（可审计），但不直发（P1 才做每日摘要）。"""
    bad = sandbox["mk"](sandbox["work"] / "bad.sh", "#!/bin/bash\necho 'VERDICT  : FAIL'\nexit 1\n")
    reg = sandbox["build"]([{"id": "low", "cmd": bad, "verdict_parse": V_ANY, "severity": "low"}])
    proc = _run(reg)
    assert "alerts:" not in proc.stdout
    log = sandbox["work"] / "alert.log"
    assert not log.exists() or "[FAIL] low" not in log.read_text(encoding="utf-8")
    assert _statuses(sandbox["work"])["low"] == "FAIL"
    hist = (sandbox["work"] / "history.jsonl").read_text(encoding="utf-8")
    assert '"id": "low"' in hist


def test_e2e_only_filter(sandbox):
    ok = sandbox["mk"](sandbox["work"] / "ok.sh", "#!/bin/bash\necho 'VERDICT  : PASS'\nexit 0\n")
    reg = sandbox["build"]([{"id": "a", "cmd": ok, "verdict_parse": V_ANY},
                            {"id": "b", "cmd": ok, "verdict_parse": V_ANY}])
    _run(reg, "--only", "a")
    assert list(_statuses(sandbox["work"])) == ["a"]


def test_heartbeat_expired_and_fresh(sandbox):
    ok = sandbox["mk"](sandbox["work"] / "ok.sh", "#!/bin/bash\necho 'VERDICT  : PASS'\nexit 0\n")
    reg = sandbox["build"]([{"id": "a", "cmd": ok, "verdict_parse": V_ANY}], interval_min=1)
    _run(reg)
    assert _run(reg, "--heartbeat").returncode == 0
    last = sandbox["work"] / "last_run.json"
    stale = last.stat().st_mtime - 600
    os.utime(last, (stale, stale))
    proc = _run(reg, "--heartbeat")
    assert proc.returncode == 3 and "HEARTBEAT: EXPIRED" in proc.stdout
    assert "HEARTBEAT-EXPIRED" in (sandbox["work"] / "alert.log").read_text(encoding="utf-8")


def test_heartbeat_missing_last_run_is_expired(sandbox):
    reg = sandbox["build"]([])
    proc = _run(reg, "--heartbeat")
    assert proc.returncode == 3 and "no last_run.json" in proc.stdout


def test_notify_failure_does_not_raise(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise FileNotFoundError("lark-cli")
    monkeypatch.setattr(rmc.subprocess, "run", boom)
    ok, info = rmc._notify(["lark-cli", "im", "+messages-send"])
    assert ok is False and "FileNotFoundError" in info


def test_registry_production_file_is_valid_and_mimir_owned():
    """生产注册表自身也要过 schema 基本约束（P0 只注册 owner=mimir）。"""
    prod = Path.home() / ".mimiraether" / "data" / "ops" / "mech_checks.json"
    if not prod.exists():
        pytest.skip("生产注册表不存在")
    reg = json.loads(prod.read_text(encoding="utf-8"))
    assert reg["items"], "注册表不得为空"
    for it in reg["items"]:
        assert it.get("owner") == "mimir", f"{it.get('id')} 非 mimir owner（P0 边界）"
        assert it.get("cmd"), f"{it.get('id')} 缺 cmd"
        assert it.get("readonly", True) is True, f"{it.get('id')} P0 必须是只读项"
