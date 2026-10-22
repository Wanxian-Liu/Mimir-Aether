"""B12/B12b · chroma 写入事件账本的判据两向（RL-20261020-094 · D2/D13）。

为什么用子进程测：**退出码是这个工具对外的 API**（角色卡 L32「Exit codes are an
API — honor them」）。测内部函数只能证明「我记得怎么算」，测不到「脚本对外说的 rc」。

两向纪律（AGENTS §9 档位 ④：闸/判据类必须正控 + 负控，单向 = 不及格）：
  正控 —— 干净账本 / 新鲜证据 ⇒ rc=0，且真重叠能变红（判据有牙）
  负控 —— 没有可用证据（缺失/空/只有 acquire_failed/读不出/单 pid/陈旧）⇒ rc=3 弃权
          有证据但坏了（重叠/缺 end/孤儿 end/坏行/未知 phase/锁本体报错）⇒ rc=2

B12b 补的六条，都是独立审计（L2 异源）复现过的主张：
  ① 陈旧账本 rc=0（MIMIR_CHROMA_EVENTS=0 只让账本停止增长，不会清空历史）
  ② lock_errors（acquire_failed/result=error）不进退出码
  ③ abstained 与 rc=3 不等价（孤儿 end 时 abstained=true 而 rc=2）
  ④ 单 pid 账本 pairs>0 即 rc=0 —— overlaps 恒 0 是空真
  ⑤ 账本读不出来时抛 traceback + 未声明的 rc=1
  ⑥ selftest 全在 audit() 层，把 unknown_phase 从 violations 删掉仍然全绿
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / "tools" / "chroma_event_audit.py"

# 新鲜证据：默认 --max-age-s 是 86400，夹具必须用「现在」附近的时间戳，
# 否则会（正确地）被判成陈旧弃权。留 5s 余量避免测试跑慢时踩线。
NOW = time.time()
T = NOW - 5.0


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
    ev("begin", T, 1, "a"), ev("end", T + 0.1, 1, "a"),
    ev("begin", T + 0.2, 2, "b"), ev("end", T + 0.3, 2, "b"),
]

OVERLAP = [
    ev("begin", T, 1, "a"),
    ev("begin", T + 0.05, 2, "b"),
    ev("end", T + 0.2, 1, "a"),
    ev("end", T + 0.3, 2, "b"),
]


# ---------------------------------------------------------------- 正控（有证据）

def test_selftest_arms_two_way():
    cp = run("--selftest")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "FAIL" not in cp.stdout, cp.stdout
    assert "孤儿 end 计入 orphan_ends" in cp.stdout
    assert "空账本 no_pairs=True" in cp.stdout
    # B12b：rc 阶梯本身也要被测——否则把 violations 删一项 selftest 照样全绿。
    assert "rc 阶梯 单 pid⇒3" in cp.stdout
    assert "rc 阶梯 lock_errors⇒2" in cp.stdout


def test_clean_ledger_is_green(tmp_path):
    cp = run("--file", str(ledger(tmp_path, CLEAN)), "--json")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["pairs"] == 2 and d["overlaps"] == 0 and d["abstained"] is False
    assert d["distinct_pids"] == 2 and d["rc"] == 0
    assert cp.stderr == ""


def test_true_overlap_turns_red(tmp_path):
    """判据有牙：真重叠必须 rc=2（负控——该拦的拦住）。"""
    cp = run("--file", str(ledger(tmp_path, OVERLAP)), "--json")
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
    lines = [ev("acquire_failed", T, 7, result="timeout")]
    cp = run("--file", str(ledger(tmp_path, lines)), "--json")
    assert cp.returncode == 3, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["timeouts"] == 1 and d["abstained"] is True


def test_stale_ledger_abstains(tmp_path):
    """B12b ①：陈旧证据不是「现在干净」。

    MIMIR_CHROMA_EVENTS=0 只是让账本停止增长、不会清空历史，
    所以「关掉了」≠「查过了」——必须靠时间面抓。
    """
    stale = [ev("begin", 1_600_000_000.0, 1, "a"), ev("end", 1_600_000_000.1, 1, "a"),
             ev("begin", 1_600_000_000.2, 2, "b"), ev("end", 1_600_000_000.3, 2, "b")]
    cp = run("--file", str(ledger(tmp_path, stale)), "--json")
    assert cp.returncode == 3, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["abstained"] is True and d["last_event_age_s"] > 86_400
    assert "陈旧" in cp.stderr


def test_max_age_zero_disables_freshness(tmp_path):
    """逃生口：--max-age-s 0 = 只看账本内容新鲜度，不判新旧。"""
    stale = [ev("begin", 1_600_000_000.0, 1, "a"), ev("end", 1_600_000_000.1, 1, "a"),
             ev("begin", 1_600_000_000.2, 2, "b"), ev("end", 1_600_000_000.3, 2, "b")]
    cp = run("--file", str(ledger(tmp_path, stale)), "--json", "--max-age-s", "0")
    assert cp.returncode == 0, cp.stdout + cp.stderr


def test_single_pid_abstains(tmp_path):
    """B12b ④：overlaps 的定义是「不同 pid 相交」；单 pid 时它恒 0，是空真。"""
    lines = [ev("begin", T, 1, "a"), ev("end", T + 0.1, 1, "a"),
             ev("begin", T + 0.2, 1, "a"), ev("end", T + 0.3, 1, "a")]
    cp = run("--file", str(ledger(tmp_path, lines)), "--json")
    assert cp.returncode == 3, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["pairs"] == 2 and d["distinct_pids"] == 1
    assert "一个 pid" in cp.stderr


def test_unreadable_ledger_abstains(tmp_path):
    """B12b ⑤：读不出来 ≠ 崩溃。rc=1 + traceback 是未声明的 API。"""
    if os.geteuid() == 0:
        pytest.skip("root 无视文件权限")
    p = ledger(tmp_path, CLEAN, name="locked.jsonl")
    p.chmod(0o000)
    try:
        cp = run("--file", str(p), "--json")
    finally:
        p.chmod(0o644)
    assert cp.returncode == 3, cp.stdout + cp.stderr
    assert "Traceback" not in cp.stderr
    assert "读不出来" in cp.stderr


def test_directory_as_ledger_abstains(tmp_path):
    cp = run("--file", str(tmp_path), "--json")
    assert cp.returncode == 3, cp.stdout + cp.stderr
    assert "Traceback" not in cp.stderr
    assert "弃权" in cp.stderr


# -------------------------------------------- 负控（有证据但坏了 ⇒ rc=2，不弃权）

def test_unpaired_begin_red(tmp_path):
    cp = run("--file", str(ledger(tmp_path, [ev("begin", T, 3, "c")])), "--json")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    assert json.loads(cp.stdout)["unpaired"] == 1


def test_orphan_end_red(tmp_path):
    """end 没有 begin 可配（begin 那行丢了/被截断）——B12 之前静默丢弃 ⇒ rc=0。"""
    cp = run("--file", str(ledger(tmp_path, [ev("end", T + 0.5, 5, "d", result="ok")])), "--json")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["orphan_ends"] == 1 and d["pairs"] == 0
    # B12b ③：abstained 只描述 rc==3；这里 rc=2，字段不得说「弃权」。
    assert d["abstained"] is False


def test_torn_begin_line_red(tmp_path):
    """SIGKILL 正好落在写 begin 那一行：截断行 + 存活 end。

    这正是设计宣称要抓的崩溃形态（docstring：unpaired 只该在进程被杀时 >0）。
    B12 之前：坏行被 continue 吞掉、孤儿 end 被丢弃 ⇒ pairs=0/unpaired=0/rc=0。
    """
    p = tmp_path / "torn.jsonl"
    p.write_text(
        '{"phase":"begin","ts":1000.0,"pid":11,"nonc\n'
        + ev("end", T + 0.5, 11, "n1", result="ok") + "\n",
        encoding="utf-8",
    )
    cp = run("--file", str(p), "--json")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["parse_errors"] == 1
    assert d["orphan_ends"] == 1


def test_unknown_phase_red(tmp_path):
    cp = run("--file", str(ledger(tmp_path, [ev("heartbeat", T, 9)])), "--json")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    assert json.loads(cp.stdout)["unknown_phase"] == 1


def test_lock_error_is_violation(tmp_path):
    """B12b ②：acquire_failed/result=error = 锁本体没能取到（OSError），必须红。

    B12 时这一例是 rc=0：errors=1 写在 JSON 里、rc 却是绿的，读者只看得见 rc。
    """
    lines = CLEAN + [ev("acquire_failed", T + 0.4, 3, result="error",
                        scope="process", error="OSError: flock")]
    cp = run("--file", str(ledger(tmp_path, lines)), "--json")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["lock_errors"] == 1 and d["pairs"] == 2
    assert "lock_errors=1" in cp.stderr


def test_index_error_is_loud_but_not_violation(tmp_path):
    """临界区内写失败：锁履职了，不是互斥违规——但不能静默。"""
    lines = [json.loads(x) for x in CLEAN]
    lines[1]["result"] = "error"
    cp = run("--file", str(ledger(tmp_path, [json.dumps(r, ensure_ascii=False) for r in lines])), "--json")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["index_errors"] == 1 and d["lock_errors"] == 0
    assert "index_errors=1" in cp.stderr


def test_seq_gap_red(tmp_path):
    """第 2 批：账本丢行只能靠 seq 空洞发现。

    B12b 之前配对全对也判绿 —— 丢一条 begin 只会变成 unpaired，但丢掉一对
    begin+end（或整段）则什么都不剩，读数与「真的没发生」逐位相同。
    """
    recs = [json.loads(x) for x in CLEAN]
    for i, r in enumerate(recs):
        r["seq"] = i + 1
    recs[1]["seq"] = 7  # 2..6 那几条丢了
    p = ledger(tmp_path, [json.dumps(r, ensure_ascii=False) for r in recs], name="seqgap.jsonl")
    cp = run("--file", str(p), "--json")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    d = json.loads(cp.stdout)
    assert d["seq_gaps"] == 5, d["seq_gaps"]
    assert "seq_gaps=5" in cp.stderr


def test_ledger_without_seq_is_not_red(tmp_path):
    """老账本（B12b 之前）没有 seq 字段——不能因为「旧证据缺这个字段」判红。"""
    cp = run("--file", str(ledger(tmp_path, CLEAN)), "--json")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert json.loads(cp.stdout)["seq_gaps"] == 0


# ------------------------------------------------------------------ 界面契约

@pytest.mark.parametrize("args", [("--json",), ()])
def test_rc_field_present_in_both_modes(tmp_path, args):
    cp = run("--file", str(ledger(tmp_path, CLEAN)), *args)
    assert cp.returncode == 0
    if "--json" in args:
        assert json.loads(cp.stdout)["rc"] == 0
    else:
        # B12b：人类模式也要把 rc 和 evidence_gaps 打出来，否则管道外的人看不到。
        assert "rc=0" in cp.stdout
        assert "evidence_gaps" in cp.stdout


def test_default_path_missing_does_not_crash(tmp_path, monkeypatch):
    """不带 --file 时走 get_mimir_home()；缺账本必须弃权而不是崩。"""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    cp = subprocess.run([sys.executable, str(AUDIT), "--json"], capture_output=True, text=True,
                        timeout=120, cwd=str(REPO))
    assert cp.returncode == 3, cp.stdout + cp.stderr
    assert "弃权" in cp.stderr
