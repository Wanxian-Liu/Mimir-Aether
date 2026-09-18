"""A8/批4 · 全仓语法闸 + 归档域闸的受控双胞验收（负控必须被拒 + 孪生对照不误拦）。

背景：
  A8（一代）：run_ralph_tier0.sh Gate1 接入 scripts/check_scripts_syntax.py（仅 scripts/ 整树）。
  批4（二代）：同一闸扩为 ① 默认根 = **本仓根**（全仓扫，补「空转绿盲区」）
              ② 归档域 import 检测（清单单一真源 .mimir-archived-domains.txt）。

臂（缺一不可）：
  臂 A（负控）    坏语法样本 → 必须被拒（rc≠0 且输出点名该文件）
  臂 B（孪生）    同目录只留合法文件 → 必须全 PASS（证明臂 A 不是假阳性）
  臂 B2           同一文件：坏→拒 / 修好→过（判据来自文件内容，不是目录名或缓存）
  臂 C（真实树）  真仓全仓（无 --root）→ rc=0、规模 ≥500、SYNTAX-GATE 的 root= 就是仓根
                  —— **钉住「空转绿盲区」修复**（旧默认只扫 scripts/ 的 93 个文件）
  臂 D（接线）    门禁脚本内确有该闸调用（**脚本存在 ≠ 已接线**）
  臂 E（回归钉）  A8 病灶文件 scripts/signal-deliver.py 必须可 ast.parse
  臂 F（归档负控）`from mimicore.x import y` → 必须 ARCHIVED-IMPORT-FAIL 且 rc≠0
  臂 G（归档孪生）同目录换成合法 import → 必须全绿（证明臂 F 不是假阳性）
  臂 H（组件边界）mimicorex / mimicore_extra **不得**命中；mimicore.sub **必须**命中
  臂 I（真实清单）真仓清单存在、首行 = mimicore、真仓全仓扫 hits=0
  臂 J（病灶钉）  批4 当场发现的语法死 agent/auto_retrospective.py 必须永久可 ast.parse
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / "scripts" / "check_scripts_syntax.py"
GATE = REPO / "run_ralph_tier0.sh"
ARCHIVED_LIST = REPO / ".mimir-archived-domains.txt"

BROKEN = "def f(:\n    return 1\n"
VALID = "def g(x):\n    return x + 1\n"
ARCHIVED_SAMPLE = "from mimicore.mimir_paths import get_mimir_home\n"
LIVE_SAMPLE = "from mimir_cli.model_config import get_model\n"


def _run(root: Path, archived_list: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(CHECKER), "--root", str(root)]
    if archived_list is not None:
        cmd += ["--archived-domains", str(archived_list)]
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(REPO), timeout=300
    )


def _synthetic_list(tmp_path: Path, *prefixes: str) -> Path:
    p = tmp_path / "archived-domains.txt"
    p.write_text("\n".join(prefixes) + "\n", encoding="utf-8")
    return p


# --- 臂 A/B/B2：语法闸本体（A8 原有，语义不变）--------------------------------------


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


# --- 臂 C/D/E：真实树 + 接线 + A8 病灶回归钉 -----------------------------------------


def test_arm_c_real_tree_clean_and_scans_whole_repo():
    """臂 C：真仓全仓（默认根）rc=0，且**确实扫全仓**（非空转绿）。

    批4 关键断言：默认 root 必须是**仓根**、规模 ≥500（旧行为 = scripts/ 的 93 个）。
    """
    r = subprocess.run(
        [sys.executable, str(CHECKER)],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=300,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SYNTAX-FAIL" not in r.stdout
    assert "ARCHIVED-IMPORT-FAIL" not in r.stdout
    verdict = [ln for ln in r.stdout.splitlines() if ln.startswith("SYNTAX-GATE")][-1]
    scanned = int(verdict.split("scanned=")[1].split()[0])
    assert scanned >= 500, f"默认根未覆盖全仓（空转绿盲区回归）: {verdict}"
    assert "fail=0" in verdict
    assert f"root={REPO}" in verdict, verdict
    archived = [ln for ln in r.stdout.splitlines() if ln.startswith("ARCHIVED-GATE")][-1]
    assert "hits=0" in archived, archived
    assert "prefixes=0" not in archived, archived


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


# --- 臂 F/G/H：归档域闸（批4 新增）---------------------------------------------------


def test_arm_f_negative_control_archived_import_rejected(tmp_path):
    """臂 F：归档域 import 样本必须被拒（rc≠0 + 点名 + hits=1）。"""
    (tmp_path / "leak_sample.py").write_text(ARCHIVED_SAMPLE, encoding="utf-8")
    lst = _synthetic_list(tmp_path, "mimicore")
    r = _run(tmp_path, lst)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "ARCHIVED-IMPORT-FAIL" in r.stdout
    assert "leak_sample.py:1" in r.stdout
    assert "matches archived domain 'mimicore'" in r.stdout
    assert "hits=1" in r.stdout


def test_arm_g_twin_live_import_passes(tmp_path):
    """臂 G（孪生对照）：同一位置换成**活**域 import → 必须全绿（非假阳性）。"""
    (tmp_path / "ok_sample.py").write_text(LIVE_SAMPLE, encoding="utf-8")
    lst = _synthetic_list(tmp_path, "mimicore")
    r = _run(tmp_path, lst)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ARCHIVED-IMPORT-FAIL" not in r.stdout
    assert "hits=0" in r.stdout


def test_arm_h_component_boundary_not_bare_prefix(tmp_path):
    """臂 H：匹配按**组件边界** —— mimicorex / mimicore_extra 不算归档域。"""
    (tmp_path / "lookalike.py").write_text(
        "import mimicorex\nimport mimicore_extra\n", encoding="utf-8"
    )
    lst = _synthetic_list(tmp_path, "mimicore")
    r = _run(tmp_path, lst)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "hits=0" in r.stdout, r.stdout

    (tmp_path / "real_sub.py").write_text("from mimicore import sub\n", encoding="utf-8")
    r2 = _run(tmp_path, lst)
    assert r2.returncode != 0, r2.stdout + r2.stderr
    assert r2.stdout.count("ARCHIVED-IMPORT-FAIL") == 1, r2.stdout
    assert "real_sub.py:1" in r2.stdout


# --- 臂 I/J：单一真源清单 + 批4 当场病灶 ---------------------------------------------


def test_arm_i_single_source_list_exists_and_covers_repo():
    """臂 I：清单单一真源存在、首行 = mimicore、且真仓全仓扫 hits=0（无复活式 import）。"""
    assert ARCHIVED_LIST.is_file(), f"归档域清单缺失（单一真源）: {ARCHIVED_LIST}"
    first = ARCHIVED_LIST.read_text(encoding="utf-8").splitlines()[0].strip()
    assert first == "mimicore", f"清单首行应为 mimicore，实际 {first!r}"
    r = subprocess.run(
        [sys.executable, str(CHECKER)], capture_output=True, text=True,
        cwd=str(REPO), timeout=300,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    archived = [ln for ln in r.stdout.splitlines() if ln.startswith("ARCHIVED-GATE")][-1]
    assert "hits=0" in archived, archived
    assert "prefixes=0" not in archived, archived


def test_arm_j_batch4_lesion_file_parses_and_no_orphan_docstring():
    """臂 J：批4 当场发现的语法死（agent/auto_retrospective.py）永久钉住。

    病根 = OC-01 归档 commit a07c73a 插入 banner 时留下**孤儿三引号** ⇒ tokenize
    "EOF in multi-line string"。它在 scripts/ 之外，故一代闸看不见。
    """
    src = (REPO / "agent" / "auto_retrospective.py").read_text(encoding="utf-8")
    ast.parse(src)
    assert '不再导入。"""\n"""' not in src, "孤儿三引号回归"
    assert "OC-01 ARCHIVED" in src
