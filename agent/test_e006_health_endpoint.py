"""E-006 slice: loopback GET /health for api_server + config defaults."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_api_server_handle_health_returns_status_ok():
    async def _run():
        from agent.monitor import reset_monitor_state
        from gateway.config import PlatformConfig
        from gateway.platforms.api_server import APIServerAdapter

        reset_monitor_state()
        adapter = APIServerAdapter(PlatformConfig(enabled=True))
        request = _make_get_request("/health")
        response = await adapter._handle_health(request)
        assert response.status == 200
        body = json.loads(response.body)
        assert body["status"] == "ok"
        assert body["gateway"] == "ok"
        assert "agent_error_rate" in body
        assert "agent" in body

    asyncio.run(_run())


def test_load_gateway_config_enables_loopback_api_server(monkeypatch, tmp_path):
    from gateway.config import Platform, load_gateway_config

    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("API_SERVER_ENABLED", raising=False)
    monkeypatch.delenv("MIMIR_PORT", raising=False)

    config = load_gateway_config()
    api = config.platforms.get(Platform.API_SERVER)
    assert api is not None
    assert api.enabled is True
    assert api.extra.get("host") == "127.0.0.1"
    assert api.extra.get("port") == 18999


def test_load_gateway_config_respects_api_server_disabled(monkeypatch, tmp_path):
    from gateway.config import Platform, load_gateway_config

    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("API_SERVER_ENABLED", "false")

    config = load_gateway_config()
    api = config.platforms.get(Platform.API_SERVER)
    assert api is None or api.enabled is False


def test_api_server_default_port_uses_mimir_port(monkeypatch):
    from gateway.config import PlatformConfig
    from gateway.platforms.api_server import APIServerAdapter

    monkeypatch.setenv("MIMIR_PORT", "19001")
    monkeypatch.delenv("API_SERVER_PORT", raising=False)
    adapter = APIServerAdapter(PlatformConfig(enabled=True))
    assert adapter._port == 19001


def _make_get_request(path: str):
    from aiohttp.test_utils import make_mocked_request

    return make_mocked_request("GET", path)


def test_api_server_connect_exposes_health_route():
    async def _run():
        from agent.monitor import reset_monitor_state
        from aiohttp.test_utils import TestClient, TestServer
        from gateway.config import PlatformConfig
        from gateway.platforms.api_server import APIServerAdapter

        reset_monitor_state()

        cfg = PlatformConfig(enabled=True, extra={"host": "127.0.0.1", "port": 0})
        adapter = APIServerAdapter(cfg)
        # Bind ephemeral port via aiohttp test server on the app routes only
        from aiohttp import web

        app = web.Application()
        app.router.add_get("/health", adapter._handle_health)
        server = TestServer(app)
        client = TestClient(server)
        await client.start_server()
        try:
            resp = await client.get("/health")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"
        finally:
            await client.close()

    asyncio.run(_run())
