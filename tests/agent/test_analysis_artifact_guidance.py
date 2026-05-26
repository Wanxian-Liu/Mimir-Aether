"""IQ-EVO-35: analysis artifact read-only prompt injection."""

from __future__ import annotations

import json

from agent.prompt_builder import build_analysis_artifact_guidance, build_system_prompt


def test_guidance_off_when_env_off(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("MIMIR_AUTO_ANALYSIS", raising=False)
    assert build_analysis_artifact_guidance() == ""


def test_guidance_includes_latest_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_ANALYSIS", "1")
    art_dir = tmp_path / "data" / "analysis_artifacts"
    art_dir.mkdir(parents=True)
    (art_dir / "t.json").write_text(
        json.dumps({"task_name": "iq35", "prompt": "Summary: fix session_search path."}),
        encoding="utf-8",
    )
    text = build_analysis_artifact_guidance()
    assert "IQ-EVO-35" in text
    assert "session_search" in text


def test_build_system_prompt_includes_guidance(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_ANALYSIS", "1")
    art_dir = tmp_path / "data" / "analysis_artifacts"
    art_dir.mkdir(parents=True)
    (art_dir / "t.json").write_text(
        json.dumps({"prompt": "hint text"}),
        encoding="utf-8",
    )
    prompt = build_system_prompt(
        model="deepseek-chat",
        include_skills=False,
        include_context=False,
    )
    assert "Recent execution analysis" in prompt
