"""RL-20261020-094 收尾面：判据弃权语义 + 演练脚本可跑（2026-10-22 B10）。

判据本体在仓外（~/.mimiraether/gates/），所以这里用子进程调它——
测的是「它对外说的 rc」而不是内部函数，正好覆盖 F7 假绿那类问题。
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GATE = Path.home() / ".mimiraether" / "gates" / "verify_chroma_write_coverage.py"
DRILLS = REPO / "scripts" / "rl094_drills.py"

pytestmark = pytest.mark.skipif(not GATE.exists(), reason="判据不在本机")


def _run(*args, timeout=60):
    return subprocess.run([sys.executable, str(GATE), *args],
                          capture_output=True, text=True, timeout=timeout)


def test_empty_root_abstains(tmp_path):
    """F7：一个站点都没扫到 ⇒ rc=3，不是 rc=0。"""
    cp = _run("--root", str(tmp_path))
    assert cp.returncode == 3, cp.stdout + cp.stderr
    assert "弃权" in cp.stderr


def test_real_repo_reports_nullable():
    """真仓读数必须仍是有牙的：guards=10 / nullable=1 / rc=2。"""
    cp = _run("--root", str(REPO))
    assert cp.returncode == 2, cp.stdout + cp.stderr
    assert "guards=10 unguarded=0 nullable=1" in cp.stdout


def test_selftest_arms():
    cp = _run("--selftest", timeout=180)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "9/9" in cp.stdout


def test_drill_d3_dual_source(tmp_path):
    """D3：受控超时下两个源各记 1 次，且不污染 unpaired。"""
    env = dict(os.environ)
    env.pop("MIMIR_AETHER_HOME", None)
    env["MIMIR_AETHER_HOME"] = str(tmp_path)
    cp = subprocess.run([sys.executable, str(DRILLS), "d3"], env=env,
                        capture_output=True, text=True, timeout=120)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert '"d3": "PASS"' in cp.stdout
