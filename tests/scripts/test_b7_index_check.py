"""决定5 闸：`scripts/b7_index_check.py` 的**假绿**与**假红**双向验收（2026-09-17）。

背景（盘上实证）
----------------
旧版（65 行 · sha8 `25c941dc`）有两处结构性假绿：
  ① L25 `ND.iterdir()` **非递归** + 键 = **basename**
     ⇒ 子目录文件**根本不在 files 集合里** ⇒ 永不报 UNLISTED ⇒ 报 PASS 的假绿。
     盘上量：工具报 `disk=164`，真文件数（除 INDEX.md）应 = **165**，漏的正是
     `evidence/e3_os_level_snapshot.txt`。
  ② `stale = listed - set(files)` ⇒ **恒为空集**（死度量）。

本闸的设计原则：**假绿与假红来自同一个错误 —— 判据作用域没对着「承诺」**。
故双向验收：既证「该报的报得出」（正控 + 修前反证），也证「不该报的不报」（假红防护）。

受控探针：全部跑 `tmp_path` fixture 树（`--notes-dir` / `--index` 参数化），
不碰真实 notes 目录。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/b7_index_check.py"
PY = sys.executable


def _load():
    spec = importlib.util.spec_from_file_location("b7_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fixture(tmp_path: Path) -> Path:
    """造一棵 notes 树：顶层 2 件 + 子目录 1 件 + INDEX.md。"""
    nd = tmp_path / "notes"
    (nd / "evidence").mkdir(parents=True)
    (nd / "a.md").write_text("a", encoding="utf-8")
    (nd / "b.md").write_text("b", encoding="utf-8")
    (nd / "evidence" / "c.txt").write_text("c", encoding="utf-8")
    return nd


def _index(nd: Path, body: str) -> Path:
    idx = nd / "INDEX.md"
    idx.write_text(
        "## 活\n\n" + body + "\n## 冻\n\n## 归档\n\n",
        encoding="utf-8",
    )
    return idx


def _run(nd: Path) -> tuple[int, str]:
    r = subprocess.run(
        [PY, str(SCRIPT), "--notes-dir", str(nd)],
        capture_output=True, text=True,
    )
    return r.returncode, r.stdout + r.stderr


# ── 正控：探针有鉴别力（顶层未登记必须报出）────────────────────────────────


def test_positive_control_top_level_unlisted_is_reported(tmp_path):
    nd = _fixture(tmp_path)
    _index(nd, "| `a.md` | x |\n")  # b.md 未登记
    rc, out = _run(nd)
    assert rc == 1
    assert "UNLISTED b.md" in out


# ── 目标（本闸核心）：子目录未登记也必须报出 ────────────────────────────────


def test_nested_unlisted_is_reported(tmp_path):
    """修前这里是假绿：`iterdir()` 看不到 evidence/ ⇒ 永不报 UNLISTED。"""
    nd = _fixture(tmp_path)
    _index(nd, "| `a.md` | x |\n| `b.md` | y |\n")  # evidence/c.txt 未登记
    rc, out = _run(nd)
    assert rc == 1, f"应 FAIL（子目录件未登记）；实得 rc={rc}\n{out}"
    assert "UNLISTED evidence/c.txt" in out


def test_nested_file_counts_toward_disk_total(tmp_path):
    nd = _fixture(tmp_path)
    _index(nd, "| `a.md` | x |\n| `b.md` | y |\n| `evidence/c.txt` | z |\n")
    rc, out = _run(nd)
    assert rc == 0, out
    assert "disk=3" in out          # a.md + b.md + evidence/c.txt
    assert "nested   : 1" in out


# ── 鉴别力自证：修前逻辑在同一用例上必须漏报 ───────────────────────────────


def test_old_iterdir_logic_misses_nested(tmp_path):
    """把旧逻辑内联跑同一棵树 ⇒ 证明本闸能区分修前/修后（否则用例无鉴别力）。"""
    nd = _fixture(tmp_path)
    old = {p.name for p in nd.iterdir() if p.is_file()}   # 旧 L25
    old.discard("INDEX.md")
    assert old == {"a.md", "b.md"}
    assert "evidence/c.txt" not in old      # 旧逻辑结构上就看不见
    # 新逻辑必须看得见
    mod = _load()
    assert "evidence/c.txt" in mod.collect(nd)


def test_source_no_longer_uses_iterdir():
    """结构闸：源码里不得再出现非递归 iterdir（防退化）。"""
    src = SCRIPT.read_text(encoding="utf-8")
    body = src.split('"""', 2)[2]          # 去掉模块 docstring（其中提到"旧版 iterdir"）
    assert ".iterdir()" not in body
    assert ".rglob(" in body


# ── 假红防护：非登记位不得被判 stale / unlisted ────────────────────────────


def test_inline_mentions_are_not_registrations(tmp_path):
    """行文内引用（描述格里的其它文件 / wiki 卡路径）不得报 stale。"""
    nd = _fixture(tmp_path)
    _index(
        nd,
        "| `a.md` | 归属卡 `2026-09-16-六项终裁执行记录.md` #5 |\n"
        "| `b.md` | 见 `docs/AGENT_REPO_OWNERSHIP.md` 与 `…F2审计…众议.md` |\n"
        "| `evidence/c.txt` | e |\n",
    )
    rc, out = _run(nd)
    assert rc == 0, f"行文内引用被误判 ⇒ 假红\n{out}"
    assert "staleness: index *.md tokens with no file on disk = 0" in out


def test_command_output_cell_is_not_registration(tmp_path):
    """命令输出格（含 `=` 与空格）不得被当成登记位。"""
    nd = _fixture(tmp_path)
    _index(
        nd,
        "| `a.md` | x |\n| `b.md` | y |\n| `evidence/c.txt` | z |\n"
        "| 覆盖率 | `disk=3 listed=3 unlisted=0` |\n",
    )
    rc, out = _run(nd)
    assert rc == 0, out


def test_ambiguous_basename_requires_relative_path(tmp_path):
    """同名文件 >1 处 ⇒ 只用 basename 登记必须报 AMBIGUOUS（不得静默算过）。"""
    nd = tmp_path / "notes"
    (nd / "x").mkdir(parents=True)
    (nd / "y").mkdir(parents=True)
    (nd / "same.md").write_text("1", encoding="utf-8")
    (nd / "x" / "same.md").write_text("2", encoding="utf-8")
    (nd / "y" / "same.md").write_text("3", encoding="utf-8")
    _index(nd, "| `same.md` | 只写 basename |\n")
    rc, out = _run(nd)
    assert rc == 1
    assert "AMBIGUOUS same.md" in out


# ── 真实盘：本仓契约（notes 覆盖必须真覆盖）────────────────────────────────


def test_real_notes_tree_declares_nested_coverage():
    """真实运行输出必须**显式声明**子目录件数量 —— 让假绿无处藏。"""
    r = subprocess.run([PY, str(SCRIPT)], capture_output=True, text=True)
    assert "nested   :" in (r.stdout + r.stderr)
