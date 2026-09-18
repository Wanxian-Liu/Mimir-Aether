"""A8 · scripts/ 整树语法闸的受控双胞验收（负控必须被拒 + 孪生对照不误拦）。

背景：run_ralph_tier0.sh Gate1 新增 `scripts/check_scripts_syntax.py` 调用。
本文件五臂，缺一不可：

  臂 A（负控）  故意坏语法的样本 → 必须被拒（rc≠0 且输出点名该文件）
  臂 B（孪生）  同目录只留合法文件 → 必须全 PASS（证明臂 A 不是假阳性）
  臂 B2        同一文件：坏→拒 / 修好→过（判据来自文件内容，不是目录名或缓存）
  臂 C（真实树）真 scripts/ 整树 → 必须 rc=0 且确实扫到文件（证明闸非空转）
  臂 D（接线）  门禁脚本内确有该闸调用（**脚本存在 ≠ 已接线**）
  臂 E（回归钉）A8 病灶文件 scripts/signal-deliver.py 必须可 ast.parse
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / "scripts" / "check_scripts_syntax.py"
GATE = REPO / "run_ralph_tier0.sh"

BROKEN = "def f(:\n    return 1\n"
VALID = "def g(x):\n    return x + 1\n"


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=180,
    )


def test_arm_a_negative_control_broken_sample_rejected(tmp_path):
    """臂 A：故意坏语法样本必须被拒（A8 DoD ② 的负控例）。"""
    (tmp_path / "bad_sample.py").write_text(BROKEN, encoding="utf-8")
    r = _run(tmp_path)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "SYNTAX-FAIL" in r.stdout
    assert "bad_sample.py" in r.stdout
    assert "fail=1" in r.stdout


def test_arm_b_twin_valid_sample_passes(tmp_path):
    """臂 B（孪生对照）：只有合法文件时必须全 PASS —— 证明臂 A 不是假阳性。"""
    (tmp_path / "good_sample.py").write_text(VALID, encoding="utf-8")
    r = _run(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SYNTAX-FAIL" not in r.stdout
    assert "scanned=1 ok=1 fail=0" in r.stdout


def test_arm_b2_same_file_broken_then_fixed(tmp_path):
    """臂 B2：同一路径同一文件，坏→拒、修好→过，判据来自内容而非目录/缓存。"""
    p = tmp_path / "sample.py"
    p.write_text(BROKEN, encoding="utf-8")
    assert _run(tmp_path).returncode != 0
    p.write_text(VALID, encoding="utf-8")
    r = _run(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_arm_c_real_scripts_tree_clean_and_nonvacuous():
    """臂 C：真 scripts/ 整树 rc=0（A8 DoD ③），且确实扫到整树（非空转）。"""
    r = subprocess.run(
        [sys.executable, str(CHECKER)],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=300,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SYNTAX-FAIL" not in r.stdout
    verdict = [ln for ln in r.stdout.splitlines() if ln.startswith("SYNTAX-GATE")][-1]
    scanned = int(verdict.split("scanned=")[1].split()[0])
    assert scanned >= 50, verdict
    assert "fail=0" in verdict


def test_arm_d_gate_wired_in_gate1_not_just_present():
    """臂 D：闸必须真接进 Gate1（脚本存在 ≠ 已接线）。"""
    text = GATE.read_text(encoding="utf-8")
    assert "scripts/check_scripts_syntax.py" in text
    assert text.index("scripts/check_scripts_syntax.py") < text.index("Gate2 Parity Tests")


def test_arm_e_a8_lesion_file_parses():
    """臂 E：A8 病灶文件回归钉 —— 该文件必须永久可解析。"""
    src = (REPO / "scripts" / "signal-deliver.py").read_text(encoding="utf-8")
    ast.parse(src)
    assert "BUZZ_INBOX_HERMES" in src
