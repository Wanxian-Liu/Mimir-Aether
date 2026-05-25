"""IND-04: mimicore submodule must not reintroduce .openclaw runtime defaults (GH #13 class)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIMICORE = ROOT / "mimicore"

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
        pytest.skip("mimicore submodule not initialized (git submodule update --init mimicore)")
    return MIMICORE


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
    from mimicore.mimir_paths import get_mimir_home

    assert get_mimir_home() == tmp_path
