"""Tests for mimircore_tool HTML capsule publish/list (no LLM)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def capsules_home(tmp_path, monkeypatch):
    """Isolate MIMIR_AETHER_HOME and capsule publish dir."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    import mimir_constants
    import tools.mimircore_tool as mt

    monkeypatch.setattr(mimir_constants, "get_mimir_home", lambda: tmp_path)
    mt._MIMICORE_IMPORT_DIR = None
    return tmp_path / "memory" / "capsules"


def test_build_capsule_html_escapes_body():
    import tools.mimircore_tool as mt

    page = mt._build_capsule_html(
        capsule_id="abc123def456",
        title="test_title",
        body_text="<script>alert(1)</script>\nline2",
        gdi_value=88.5,
        capsule_type="optimize",
    )
    assert "<!DOCTYPE html>" in page
    assert 'lang="zh-CN"' in page
    assert 'name="mimir-kind" content="capsule"' in page
    assert 'name="mimir-id" content="abc123def456"' in page
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_publish_filename_slug():
    import tools.mimircore_tool as mt

    name = mt._capsule_publish_filename("abcdefghijklmnop", "我的标题_test")
    assert name.endswith(".html")
    assert name.startswith("abcdefghijkl_")


def test_list_capsules_scans_html_only(capsules_home):
    import tools.mimircore_tool as mt

    capsules_home.mkdir(parents=True, exist_ok=True)
    html_path = capsules_home / "abc123def456_sample.html"
    html_path.write_text(
        mt._build_capsule_html(
            capsule_id="abc123def456",
            title="sample",
            body_text="body",
            gdi_value=70.0,
            capsule_type="auto",
        ),
        encoding="utf-8",
    )
    (capsules_home / "ignored.md").write_text("# not indexed", encoding="utf-8")

    raw = mt._handle_list_capsules(limit=10)
    data = json.loads(raw)
    assert data.get("total") == 1
    assert data["capsules"][0]["name"] == "abc123def456_sample"


def test_get_capsule_by_id_reads_html(capsules_home):
    import tools.mimircore_tool as mt

    capsules_home.mkdir(parents=True, exist_ok=True)
    cid = "deadbeefcafe"
    path = capsules_home / f"{cid[:12]}_item.html"
    path.write_text(
        mt._build_capsule_html(
            capsule_id=cid,
            title="item",
            body_text="preview body",
            gdi_value=75.0,
            capsule_type="repair",
        ),
        encoding="utf-8",
    )

    raw = mt._handle_get_capsule_by_id(cid)
    data = json.loads(raw)
    assert data.get("file") == path.name
    assert "preview body" in data.get("content_preview", "")


def test_resolve_mimicore_import_dir_prefers_repo_submodule(monkeypatch):
    import tools.mimircore_tool as mt

    mt._MIMICORE_IMPORT_DIR = None
    monkeypatch.delenv("MIMIR_CORE_ROOT", raising=False)
    monkeypatch.setenv("MIMIR_REPO_ROOT", str(REPO_ROOT))
    path = mt._resolve_mimicore_import_dir()
    assert path == REPO_ROOT / "mimicore"
    assert (path / "capsule_generator.py").is_file()
