"""B1-F13 案 b′ · M3 收敛的**单源判据**（T95 会后收尾 · 组件 B）。

两向（AGENTS §9 档位 ④）：
- 正控：运行时件有该段 ⇒ 读数来自运行时件，仓根件被无视；
- 负控：把仓根件的值改掉 ⇒ 读数**不变**（证明仓根件已不是真源）；
- 兜底：运行时件缺该段 ⇒ 回落仓根件且 **stderr 出声**（禁静默降级）；
- 归一：两处读者（delegate_tool / config_mixin / gateway session_mixin）
  对同一键取到同一份配置（A4 双读者分歧已消）。

判据（本文件自足，不需要真实家目录）：
    <venv>/python3 -m pytest tests/test_config_single_source.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _write_cfg(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


RUNTIME_CFG = """
delegation:
  provider: RUNTIME-PROVIDER
  model: RUNTIME/model
  max_iterations: 9
smart_model_routing:
  enabled: false
  max_simple_chars: 11
  max_simple_words: 3
  cheap_model:
    provider: RUNTIME-PROVIDER
    model: RUNTIME/cheap
"""

LEGACY_CFG = """
delegation:
  provider: LEGACY-PROVIDER
  model: LEGACY/model
  max_iterations: 44
smart_model_routing:
  enabled: true
  max_simple_chars: 222
  max_simple_words: 22
  cheap_model:
    provider: LEGACY-PROVIDER
    model: LEGACY/cheap
"""


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """临时 MIMIR_AETHER_HOME + 可控的仓根候选路径。"""
    import mimir_constants

    home = tmp_path / "home"
    legacy = _write_cfg(tmp_path / "legacy" / "config.yaml", LEGACY_CFG)
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(home))
    monkeypatch.setattr(mimir_constants, "get_legacy_repo_config_paths", lambda: [legacy])
    monkeypatch.setattr(mimir_constants, "_LEGACY_CONFIG_WARNED", set())
    return {"home": home, "legacy": legacy, "mc": mimir_constants}


def test_runtime_section_wins(sandbox):
    """正控：运行时件有该段 ⇒ 读数来自运行时件（来源路径逐字）。"""
    mc = sandbox["mc"]
    runtime = _write_cfg(sandbox["home"] / "config.yaml", RUNTIME_CFG)

    delegation, src_d = mc.load_config_section("delegation", caller="test")
    smr, src_s = mc.load_config_section("smart_model_routing", caller="test")

    assert delegation["provider"] == "RUNTIME-PROVIDER"
    assert delegation["max_iterations"] == 9
    assert smr["enabled"] is False
    assert smr["cheap_model"]["model"] == "RUNTIME/cheap"
    assert src_d == str(runtime) and src_s == str(runtime)


def test_repo_root_edit_is_not_read(sandbox):
    """负控：改仓根件的值 ⇒ 读数不变（仓根件已非真源）。"""
    mc = sandbox["mc"]
    _write_cfg(sandbox["home"] / "config.yaml", RUNTIME_CFG)

    before, _ = mc.load_config_section("delegation", caller="test")
    # 改仓根件（真源之外的那份）
    _write_cfg(sandbox["legacy"], LEGACY_CFG.replace("LEGACY/model", "MUTATED/model"))
    after, _ = mc.load_config_section("delegation", caller="test")

    assert before == after, "仓根件被改了读数却变了 ⇒ 单源未成立"
    assert after["model"] == "RUNTIME/model"


def test_loud_fallback_when_runtime_section_missing(sandbox, capsys):
    """兜底：运行时件缺段 ⇒ 回落到仓根件，且 stderr 出声（禁静默）。"""
    mc = sandbox["mc"]
    _write_cfg(sandbox["home"] / "config.yaml", "context:\n  max_recent_messages: 5\n")

    smr, src = mc.load_config_section("smart_model_routing", caller="test.fallback")
    err = capsys.readouterr().err

    assert smr["enabled"] is True                     # 值来自仓根件
    assert src == str(sandbox["legacy"])
    assert "[config-single-source]" in err            # 出声
    assert "test.fallback" in err                     # 出声带 caller


def test_both_readers_share_one_source(sandbox):
    """归一：delegate_tool 与 config_mixin 两处读者取到同一份运行时配置。"""
    mc = sandbox["mc"]
    runtime = _write_cfg(sandbox["home"] / "config.yaml", RUNTIME_CFG)

    from tools import delegate_tool

    dt_cfg = delegate_tool._load_config()
    dt_src = mc.load_config_section("delegation", caller="test")[1]

    import agent.config_mixin as cm

    cls = next(
        obj for name, obj in vars(cm).items()
        if isinstance(obj, type) and hasattr(obj, "_load_smart_routing_config")
    )
    cm_cfg = cls._load_smart_routing_config(cls.__new__(cls))
    cm_src = mc.load_config_section("smart_model_routing", caller="test")[1]

    assert dt_cfg["provider"] == "RUNTIME-PROVIDER"
    assert cm_cfg["cheap_model"]["model"] == "RUNTIME/cheap"
    assert dt_src == str(runtime) == cm_src


def test_gateway_reader_agrees_with_agent_reader(sandbox):
    """A4 双读者分歧已消：gateway 侧与 agent 侧对同一键取到同一份配置。"""
    _write_cfg(sandbox["home"] / "config.yaml", RUNTIME_CFG)

    import agent.config_mixin as cm
    import gateway.session_mixin as gsm

    agent_cls = next(
        obj for name, obj in vars(cm).items()
        if isinstance(obj, type) and hasattr(obj, "_load_smart_routing_config")
    )
    gw_cls = next(
        obj for name, obj in vars(gsm).items()
        if isinstance(obj, type) and hasattr(obj, "_load_smart_model_routing")
    )

    agent_cfg = agent_cls._load_smart_routing_config(agent_cls.__new__(agent_cls))
    gw_cfg = gw_cls._load_smart_model_routing()

    assert agent_cfg == gw_cfg
    assert gw_cfg["max_simple_chars"] == 11
