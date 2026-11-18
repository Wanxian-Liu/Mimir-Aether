"""B1-F4 · FEISHU_HOME_CHANNEL 双消费点同源（config.yaml = 唯一真源）。

C1 = ``scripts/state_engine._read_home_channel``   —— 停止令验签面（fail-closed：读不到拒一切）
C2 = ``gateway.config._apply_env_overrides`` 的 Feishu 装配 —— 投递/会话面
     （→ ``GatewayConfig.get_home_channel()`` → ``DeliveryRouter`` → session context）

改前分叉（实证）：C1 读 config.yaml，C2 只读 ``os.getenv``。生产 config.yaml 有值、
进程环境变量无值 ⇒ C2 静默为 None（``if feishu_home:`` 直接跳过），于是
``get_home_channel()`` / ``home_channels`` 全空，而 C1 拿得到真值。

本用例对拍两消费方读数，并给出**负控**：env 副本与真源背离时，投递面必须仍取真源。
"""
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CHANNEL = "oc_truth_channel"
ENV_COPY = "oc_env_copy"


def _home(tmp_path, channel=CHANNEL):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    body = "" if channel is None else "FEISHU_HOME_CHANNEL: %s\n" % channel
    (home / "config.yaml").write_text(body + "context:\n  max_recent_messages: 200\n",
                                      encoding="utf-8")
    return home


def _state_engine_read(config_file):
    """C1：直接加载脚本模块（scripts/ 不是包），只调其只读函数。"""
    path = REPO / "scripts" / "state_engine.py"
    spec = importlib.util.spec_from_file_location("_state_engine_probe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._read_home_channel(str(config_file))


def _gateway_read(home, monkeypatch, env_value):
    """C2：走真实装配路径 ``_apply_env_overrides``，不 patch 被测实现本身。"""
    from gateway import config as gw_config

    monkeypatch.setattr(gw_config, "_get_gateway_home", lambda: home)
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test_app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test_secret")
    if env_value is None:
        monkeypatch.delenv("FEISHU_HOME_CHANNEL", raising=False)
    else:
        monkeypatch.setenv("FEISHU_HOME_CHANNEL", env_value)
    cfg = gw_config.GatewayConfig()
    gw_config._apply_env_overrides(cfg)
    hc = cfg.get_home_channel(gw_config.Platform.FEISHU)
    return getattr(hc, "chat_id", None)


# ---------------------------------------------------------------- 正控
def test_yaml_truth_reaches_delivery_face(tmp_path, monkeypatch):
    """改前会红：C2 只读 env（未设）⇒ chat_id=None，yaml 真值到不了投递面。"""
    home = _home(tmp_path)
    assert _gateway_read(home, monkeypatch, env_value=None) == CHANNEL


# ---------------------------------------------------------------- 对拍
def test_two_consumers_agree_on_same_yaml(tmp_path, monkeypatch):
    """两消费点对同一 config.yaml 必须解析出同一个 chat_id。"""
    home = _home(tmp_path)
    c1 = _state_engine_read(home / "config.yaml")
    c2 = _gateway_read(home, monkeypatch, env_value=None)
    assert c1 == c2 == CHANNEL, (c1, c2)


# ---------------------------------------------------------------- 负控
def test_env_copy_cannot_override_truth(tmp_path, monkeypatch):
    """负控：env 副本与真源背离 ⇒ 投递面仍取真源（副本不得翻盘）。"""
    home = _home(tmp_path)
    assert _gateway_read(home, monkeypatch, env_value=ENV_COPY) == CHANNEL


def test_env_fallback_only_when_truth_missing(tmp_path, monkeypatch):
    """兼容层：真源缺失时才允许 env 副本兜底（且有 WARNING 出声）。"""
    home = _home(tmp_path, channel=None)
    assert _gateway_read(home, monkeypatch, env_value=ENV_COPY) == ENV_COPY


def test_no_source_leaves_home_channel_unset(tmp_path, monkeypatch):
    """两源皆空 ⇒ 不设 home_channel（不臆造目标；调用方须自行 loudly fail）。"""
    home = _home(tmp_path, channel=None)
    assert _gateway_read(home, monkeypatch, env_value=None) is None
