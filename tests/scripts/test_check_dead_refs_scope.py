"""Scope guard for scripts/check_dead_refs.py (2026-09-26).

Pre-fix failure: section 3 claimed to scan "Python imports in code blocks" but
ran the regex over the whole document, so prose that *illustrates* an import
was reported as a dead reference -> the RS19 dead_refs item was red every run
(a checklist people learn to ignore; same family as the fake-green defects).

Discrimination is measured both ways: a real dead import inside a fenced block
must still be flagged, and the same text in prose must not be.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DEAD = "from mimicore.nonexistent_module import thing"


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "check_dead_refs", REPO / "scripts" / "check_dead_refs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "skills" / "demo-skill" / "SKILL.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_dead_import_inside_fenced_block_is_flagged(tmp_path):
    mod = _load_checker()
    md = _write(tmp_path, "# demo\n\n```python\n" + DEAD + "\n```\n")
    issues = mod.check_skill(md, {})
    assert any("Dead mimicore import" in i for i in issues), issues


def test_dead_import_in_prose_is_not_flagged(tmp_path):
    """The negative arm: this is exactly what produced the daily false FAIL."""
    mod = _load_checker()
    md = _write(tmp_path, "# demo\n\n- probe note: dropped the filter -> reads `"
                + DEAD + "` -> 22\n")
    issues = mod.check_skill(md, {})
    assert not any("mimicore" in i for i in issues), issues


def test_corpus_scan_is_clean_and_does_not_crash():
    """Integration arm over the real skill corpus (133 skills at fix time)."""
    r = subprocess.run([sys.executable, "scripts/check_dead_refs.py"],
                       cwd=REPO, capture_output=True, text=True, timeout=600)
    out = r.stdout + r.stderr
    assert "Scanned:" in out, out[-400:]
    assert r.returncode == 0, out[-800:]
    assert "Issues: 0 in 0 skills" in out, out[-400:]
