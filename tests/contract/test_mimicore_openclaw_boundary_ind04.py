"""IND-04: mimicore domain must not reintroduce .openclaw runtime defaults (GH #13 class).

Dual-mode (2026-09-18 · 历史遗留清洗批3.4 · 刘哥批):
- mimicore checkout present  → original assertions (scan the tree)
- mimicore absent (archived) → assert the archived domain stays dead:
  * `mimicore` must NOT be importable (no resurrect via sys.path tricks)
  * the archive tag must resolve (git show mimicore-archived-20260918)
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIMICORE = ROOT / "mimicore"
ARCHIVE_TAG = "mimicore-archived-20260918"

# Only these non-comment lines may reference Path.home() / ".openclaw" (ADR-004 §3)
ALLOWLIST: frozenset[tuple[str, int]] = frozenset(
    {
        ("mimir_paths.py", 87),
        ("mimir_paths.py", 108),
    }
)

BAD_OPENCLAW_DEFAULT = re.compile(
    r'Path\.home\(\)\s*/\s*["\']\.openclaw|["\']~/?\.openclaw/projects'
)
BAD_HERMES_GETENV = re.compile(
    r'getenv\s*\(\s*["\']HERMES_HOME["\']|environ\.get\s*\(\s*["\']HERMES_HOME["\']'
)


@pytest.fixture
def mimicore_checkout() -> Path:
    if not (MIMICORE / "mimir_paths.py").is_file():
        pytest.skip("mimicore checkout absent — archived-domain mode covers this state")
    return MIMICORE


def test_archived_mimicore_domain_stays_dead() -> None:
    """After the archive (mimicore/ removed from the worktree), the old domain
    must not silently come back: not importable, and the archive tag reachable."""
    if (MIMICORE / "mimir_paths.py").is_file():
        pytest.skip("mimicore checkout present — tree-scan mode covers this state")
    assert importlib.util.find_spec("mimicore") is None, (
        "mimicore 已归档（tag mimicore-archived-20260918）但 import 仍可解析 —— "
        "旧域复活：检查 sys.path / 残留目录 / 遮蔽"
    )
    tag_ok = subprocess.run(
        ["git", "show", "--quiet", ARCHIVE_TAG],
        cwd=ROOT, capture_output=True,
    )
    assert tag_ok.returncode == 0, (
        f"mimicore 工作树已移除但归档 tag {ARCHIVE_TAG} 不可达 —— 纪念堂凭证缺失"
    )


def _iter_mimicore_py(mimicore: Path):
    for path in sorted(mimicore.rglob("*.py")):
        if "hermes_cli" in path.parts:
            continue
        rel = path.relative_to(mimicore).as_posix()
        yield rel, path


def test_no_openclaw_runtime_defaults_outside_allowlist(mimicore_checkout: Path) -> None:
    violations: list[str] = []
    for rel, path in _iter_mimicore_py(mimicore_checkout):
        for i, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "legacy" in line.lower() or "ADR-004" in line:
                continue
            if (Path(rel).name, i) in ALLOWLIST:
                continue
            if BAD_OPENCLAW_DEFAULT.search(line):
                violations.append(f"mimicore/{rel}:{i}: {stripped[:120]}")
    assert not violations, (
        "mimicore .openclaw runtime default (use mimir_paths.get_mimir_home):\n"
        + "\n".join(violations[:30])
    )


def test_mimir_paths_hermes_only_inside_get_mimir_home(mimicore_checkout: Path) -> None:
    """HERMES_HOME getenv is allowed only in mimir_paths.get_mimir_home (mirror of ADR-003)."""
    violations: list[str] = []
    for rel, path in _iter_mimicore_py(mimicore_checkout):
        if rel != "mimir_paths.py":
            for i, line in enumerate(
                path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
            ):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if BAD_HERMES_GETENV.search(line):
                    violations.append(f"mimicore/{rel}:{i}: {stripped[:120]}")
    assert not violations, (
        "bare HERMES_HOME getenv outside mimir_paths.py:\n" + "\n".join(violations[:30])
    )


def test_mimicore_get_mimir_home_respects_mimir_aether_home(
    mimicore_checkout: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "HERMES_HOME"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    # 批4：**静态** import 会命中 `.mimir-archived-domains.txt` 归档域闸。本用例是双模
    # 契约锁（mimicore 在场才验、归档后 fixture 已 skip）⇒ 改用 importorskip：
    # 语义不变（在场→动态导入并断言；缺席→skip），且活树对归档域**零静态依赖**。
    _mod = pytest.importorskip(
        "mimicore.mimir_paths",
        reason="mimicore 已归档（tag mimicore-archived-20260918）—— IND-04 仅在场时可验",
    )
    get_mimir_home = _mod.get_mimir_home

    assert get_mimir_home() == tmp_path
