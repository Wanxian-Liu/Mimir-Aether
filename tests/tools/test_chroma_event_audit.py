"""B12 · chroma 写入事件账本的判据两向（RL-20261020-094 · D2/D13）。

为什么用子进程测：**退出码是这个工具对外的 API**（角色卡 L32「Exit codes are an
API — honor them」）。测内部函数只能证明「我记得怎么算」，测不到「脚本对外说的 rc」。

两向纪律（AGENTS §9 档位 ④：闸/判据类必须正控 + 负控，单向 = 不及格）：
  正控 —— 干净账本 / 生产账本形态 ⇒ rc=0，且真重叠能变红（判据有牙）
  负控 —— 缺证据（缺失/空/只有 acquire_failed）⇒ rc=3 弃权，**不是** rc=0
          有证据但坏了（重叠/缺 end/孤儿 end/坏行/未知 phase）⇒ rc=2

B12 之前这五条负控里除「重叠」「缺 end」外全部返回 rc=0 —— 假绿。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / "tools" / "chroma_event_audit.py"


def run(*args):
    return subprocess.run([sys.executable, str(AUDIT), *args],
                          capture_output=True, text=True, timeout=120)


def ledger(tmp_path, lines, name="events.jsonl"):
    p = tmp_path / name
    p.write_text("".join(l + "\n" for l in lines), encoding="utf-8")
    return p


def ev(phase, ts, pid, nonce=None, **kw):
    rec = {"phase": phase, "ts": ts, "pid": pid}
    if nonce is not None:
        rec["nonce"] = nonce
    rec.update(kw)
    return json.dumps(rec, ensure_ascii=False)


CLEAN = [
    ev("begin", 1000.0, 1, "a"), ev("end", 1000.1, 1, "a"),
    ev("begin", 1000.2, 2, "b"), ev("end", 1000.3, 2, "b"),
]


# ---------------------------------------------------------------- 正控（有证据）

def test_selftest_arms_two_way():
    cp = run("--selftest")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "FAIL" not in cp.stdout, cp.stdout
    assert "孤儿 end 计入 orphan_ends" in cp.stdout
    assert "空账本 abstained=True" in cp.stdout


def test_clean_ledger_is_green(tmp_path):
    cp = run("--file", str(ledger(tmp_path, CLEAN)), "--json")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["pairs"] == 2 and d["overlaps"] == 0 and d["abstained"] is False
    assert d["rc"] == 0
    assert cp.stderr == ""


def test_true_overlap_turns_red(tmp_path):
    """判据有牙：真重叠必须 rc=2（负控——该拦的拦住）。"""
    lines = [
        ev("begin", 1000.0, 1, "a"),
        ev("begin", 1000.05, 2, "b"),
        ev("end", 1000.2, 1, "a"),
        ev("end", 1000.3, 2, "b"),
    ]
    cp = run("--file", str(ledger(tmp_path, lines)), "--json")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    assert json.loads(cp.stdout)["overlaps"] == 1


# ------------------------------------------------------- 负控（没有证据 ⇒ 弃权）

def test_missing_ledger_abstains(tmp_path):
    cp = run("--file", str(tmp_path / "nope.jsonl"), "--json")
    assert cp.returncode == 3, cp.stdout + cp.stderr
    assert "弃权" in cp.stderr
    assert json.loads(cp.stdout)["events"] == 0


def test_empty_ledger_abstains(tmp_path):
    cp = run("--file", str(ledger(tmp_path, [])), "--json")
    assert cp.returncode == 3, cp.stdout + cp.stderr
    assert "弃权" in cp.stderr


def test_acquire_failed_only_abstains(tmp_path):
    """只有超时、没有任何成对临界区 ⇒ 证明不了互斥，只能弃权（不是 rc=0）。"""
    lines = [ev("acquire_failed", 1000.0, 7, result="timeout")]
    cp = run("--file", str(ledger(tmp_path, lines)), "--json")
    assert cp.returncode == 3, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["timeouts"] == 1 and d["abstained"] is True


# -------------------------------------------- 负控（有证据但坏了 ⇒ rc=2，不弃权）

def test_unpaired_begin_red(tmp_path):
    cp = run("--file", str(ledger(tmp_path, [ev("begin", 1000.0, 3, "c")])), "--json")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    assert json.loads(cp.stdout)["unpaired"] == 1


def test_orphan_end_red(tmp_path):
    """end 没有 begin 可配（begin 那行丢了/被截断）——B12 之前静默丢弃 ⇒ rc=0。"""
    cp = run("--file", str(ledger(tmp_path, [ev("end", 1000.5, 5, "d", result="ok")])), "--json")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["orphan_ends"] == 1 and d["pairs"] == 0


def test_torn_begin_line_red(tmp_path):
    """SIGKILL 正好落在写 begin 那一行：截断行 + 存活 end。

    这正是设计宣称要抓的崩溃形态（docstring：unpaired 只该在进程被杀时 >0）。
    B12 之前：坏行被 continue 吞掉、孤儿 end 被丢弃 ⇒ pairs=0/unpaired=0/rc=0。
    """
    p = tmp_path / "torn.jsonl"
    p.write_text(
        '{"phase":"begin","ts":1000.0,"pid":11,"nonc\n' + ev("end", 1000.5, 11, "n1", result="ok") + "\n",
        encoding="utf-8",
    )
    cp = run("--file", str(p), "--json")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["parse_errors"] == 1
    assert d["orphan_ends"] == 1


def test_unknown_phase_red(tmp_path):
    cp = run("--file", str(ledger(tmp_path, [ev("heartbeat", 1000.0, 9)])), "--json")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    assert json.loads(cp.stdout)["unknown_phase"] == 1


# ------------------------------------------------------------------ 界面契约

@pytest.mark.parametrize("args", [("--json",), ()])
def test_rc_field_present_in_both_modes(tmp_path, args):
    cp = run("--file", str(ledger(tmp_path, CLEAN)), *args)
    assert cp.returncode == 0
    if "--json" in args:
        assert json.loads(cp.stdout)["rc"] == 0


def test_default_path_missing_does_not_crash(tmp_path, monkeypatch):
    """不带 --file 时走 get_mimir_home()；缺账本必须弃权而不是崩。"""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    cp = subprocess.run([sys.executable, str(AUDIT), "--json"], capture_output=True, text=True,
                        timeout=120, cwd=str(REPO))
    assert cp.returncode == 3, cp.stdout + cp.stderr
    assert "弃权" in cp.stderr
