"""RS16 (a2) - gateway hygiene creds reuse agent-layer resolution (card SS23)."""
import hashlib
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from gateway.router.agent_route_mixin import AgentRouteMixin, _cred_fp8  # noqa: E402


class _FakeRunner(AgentRouteMixin):
    def __init__(self, cache=None):
        if cache is not None:
            self._agent_cache = cache
            self._agent_cache_lock = threading.Lock()


class _RealAgent:
    def __init__(self, api_key="", base_url=""):
        self.api_key = api_key
        self.base_url = base_url


class _Wrapper:
    def __init__(self, real):
        self._real_agent = real


GW_EMPTY = {
    "provider": "openrouter",
    "base_url": "https://openrouter.ai/api/v1",
    "api_key": "",
    "cred_source": "gateway",
}
MODEL = "deepseek/deepseek-flash"


def test_I1_gateway_creds_not_overridden():
    out = _FakeRunner()._merge_agent_layer_runtime(
        dict(GW_EMPTY, api_key="gw-usable"), MODEL, session_key="s"
    )
    assert out["api_key"] == "gw-usable"
    assert out["cred_source"] == "gateway"
    assert out["base_url"] == "https://openrouter.ai/api/v1"


def test_I2_agent_layer_fills_empty_gateway_creds(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k" * 35)
    out = _FakeRunner()._merge_agent_layer_runtime(dict(GW_EMPTY), MODEL, session_key="cold-cache")
    assert out["api_key"] == "k" * 35
    assert out["cred_source"] == "agent-layer"
    assert out["base_url"] == "https://api.deepseek.com"
    assert out["provider"] == "deepseek"


def test_I2b_cache_hit_reuses_session_agent_runtime(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    cache = {"s1": (_Wrapper(_RealAgent("cached-key", "https://api.deepseek.com")), ("sig",))}
    out = _FakeRunner(cache=cache)._merge_agent_layer_runtime(dict(GW_EMPTY), MODEL, session_key="s1")
    assert out["api_key"] == "cached-key"
    assert out["cred_source"] == "cache"


def test_I3_both_layers_empty_returns_unchanged(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    src = dict(GW_EMPTY)
    out = _FakeRunner()._merge_agent_layer_runtime(src, MODEL, session_key=None)
    assert out == src
    assert src["api_key"] == ""


def test_I4_fingerprint_never_leaks_value():
    fp = _cred_fp8("secret-value")
    assert fp == hashlib.sha256(b"secret-value").hexdigest()[:8]
    assert len(fp) == 8
    assert _cred_fp8("") == "EMPTY"
    assert _cred_fp8(None) == "EMPTY"


def test_I5_terminal_result_line_outside_cred_gate():
    lines = (REPO / "gateway/router/agent_route_mixin.py").read_text(encoding="utf-8").splitlines()
    gate = next(i for i, l in enumerate(lines) if l.strip() == "if _hyg_cred:")
    term = next(i for i, l in enumerate(lines) if "[COMPRESS] result layer=gateway outcome=" in l)

    def ind(idx):
        return len(lines[idx]) - len(lines[idx].lstrip())

    assert lines[term - 1].strip() == "logger.info("
    assert ind(term - 1) == ind(gate), (ind(term - 1), ind(gate))
    assert any("[COMPRESS] abort layer=gateway reason=no_api_key" in l for l in lines)
    assert any('_hyg_outcome = "aborted_no_cred"' in l for l in lines)
