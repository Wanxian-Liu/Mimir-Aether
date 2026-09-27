"""记忆卫生闸回归（2026-09-27 · Mimir）

被测缺陷族：MEMORY.md 逼近上限（曾 98%）+ 单条过长 ⇒ 一旦触发
_maybe_compact() 的 Phase 2.5 就发生**结构性丢失**（300 字符时代 45 处不可恢复）。

闸门 scripts/check_memory_hygiene.py 三条判据各配一条负控；本文件用合成 home
（pytest tmp_path）跑闸门，正控 = 健康 home，负控 = 分别触发 R1/R2/R3。
臂型：B = 行为级（真跑闸门进程）。
"""
import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
GATE = REPO / "scripts" / "check_memory_hygiene.py"
SEP = "\n\u00a7\n"
MARK = "[" + "..." + "] (truncated)"


def _home(tmp_path, mem, user=("短条目",)):
    d = tmp_path / "home"
    (d / "memories").mkdir(parents=True, exist_ok=True)
    (d / "memories" / "MEMORY.md").write_text(SEP.join(mem), encoding="utf-8")
    (d / "memories" / "USER.md").write_text(SEP.join(user), encoding="utf-8")
    return d


def _run(home):
    p = subprocess.run(
        [sys.executable, str(GATE), "--home", str(home)],
        capture_output=True, text=True, timeout=120, cwd=str(REPO),
    )
    return p.returncode, p.stdout + p.stderr


def test_b_healthy_home_passes(tmp_path):
    """正控：健康 home ⇒ rc=0 / VERDICT PASS。"""
    rc, out = _run(_home(tmp_path, ["正常条目一", "正常条目二"]))
    assert rc == 0, out
    assert "VERDICT: PASS" in out


def test_b_r1_long_entry_fails(tmp_path):
    """负控 R1：单条 >1200 字符 ⇒ FAIL。"""
    rc, out = _run(_home(tmp_path, ["正常条目", "X" * 1500]))
    assert rc == 1, out
    assert "最长条目" in out


def test_b_r2_usage_over_limit_fails(tmp_path):
    """负控 R2：用量 >85% ⇒ FAIL（条目须互不相同，否则被去重折叠）。"""
    rc, out = _run(_home(tmp_path, [f"条目{i} " + "Y" * 870 for i in range(8)]))
    assert rc == 1, out
    assert "用量" in out


def test_b_r3_truncation_marker_fails(tmp_path):
    """负控 R3：注入态出现截断标记 ⇒ FAIL。"""
    rc, out = _run(_home(tmp_path, ["含标记 " + MARK + " 尾部"]))
    assert rc == 1, out
    assert "截断标记" in out


def test_s_gate_registered_in_mech_registry():
    """S：闸门必须登记在机械检查注册表（否则等于没接线）。"""
    reg = json.loads(
        (pathlib.Path.home() / ".mimiraether" / "data" / "ops" / "mech_checks.json")
        .read_text(encoding="utf-8")
    )
    ids = [it["id"] for it in reg["items"]]
    assert "memory_hygiene" in ids
    item = [it for it in reg["items"] if it["id"] == "memory_hygiene"][0]
    assert "check_memory_hygiene.py" in item["cmd"]
