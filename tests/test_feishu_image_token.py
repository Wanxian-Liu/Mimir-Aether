"""Feishu image download: tenant token refresh before sync GET."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from gateway.config import PlatformConfig
from gateway.platforms.feishu_adapter import (
    FeishuAdapter,
    _feishu_download_image,
    _tenant_token_valid,
)


def _adapter() -> FeishuAdapter:
    cfg = PlatformConfig(
        enabled=True,
        extra={"app_id": "cli_test", "app_secret": "secret_test"},
    )
    return FeishuAdapter(cfg)


def test_tenant_token_valid_requires_token_and_expiry_buffer():
    adapter = _adapter()
    adapter._tenant_token = None
    adapter._token_expires_at = time.time() + 3600
    assert _tenant_token_valid(adapter) is False

    adapter._tenant_token = "tok"
    adapter._token_expires_at = time.time() + 30
    assert _tenant_token_valid(adapter) is False

    adapter._token_expires_at = time.time() + 120
    assert _tenant_token_valid(adapter) is True


def test_ensure_tenant_token_sync_refreshes_when_expired():
    adapter = _adapter()
    adapter._tenant_token = "old"
    adapter._token_expires_at = 0.0

    with patch.object(adapter, "_refresh_token_sync", return_value=True) as refresh:
        assert adapter._ensure_tenant_token_sync() is True
        refresh.assert_called_once()

    adapter._tenant_token = "fresh"
    adapter._token_expires_at = time.time() + 3600
    with patch.object(adapter, "_refresh_token_sync") as refresh:
        assert adapter._ensure_tenant_token_sync() is True
        refresh.assert_not_called()


def test_download_image_refreshes_before_get():
    adapter = _adapter()
    adapter._tenant_token = None
    adapter._token_expires_at = 0.0

    image_bytes = b"\xff\xd8\xff\xe0" + b"x" * 100
    get_resp = MagicMock(status_code=200, content=image_bytes, headers={"Content-Type": "image/jpeg"})

    with patch.object(adapter, "_ensure_tenant_token_sync", return_value=True) as ensure:
        with patch("requests.get", return_value=get_resp) as get:
            with patch(
                "gateway.platforms.base.cache_image_from_bytes",
                return_value="/tmp/fake.jpg",
            ):
                with patch(
                    "gateway.platforms.base._looks_like_image",
                    return_value=True,
                ):
                    adapter._tenant_token = "tok"
                    path = _feishu_download_image(adapter, "img_v3_test_key")

    assert path == "/tmp/fake.jpg"
    ensure.assert_called_once()
    get.assert_called_once()
    headers = get.call_args.kwargs.get("headers") or get.call_args[1].get("headers", {})
    assert headers.get("Authorization") == "Bearer tok"


def test_download_image_aborts_when_refresh_fails():
    adapter = _adapter()
    with patch.object(adapter, "_ensure_tenant_token_sync", return_value=False):
        with patch("requests.get") as get:
            assert _feishu_download_image(adapter, "img_v3_test_key") is None
            get.assert_not_called()


def test_download_image_prefers_message_resource_api():
    adapter = _adapter()
    adapter._tenant_token = "tok"
    adapter._token_expires_at = time.time() + 3600

    image_bytes = b"\xff\xd8\xff\xe0" + b"x" * 100
    get_resp = MagicMock(status_code=200, content=image_bytes, headers={"Content-Type": "image/jpeg"})

    with patch.object(adapter, "_ensure_tenant_token_sync", return_value=True):
        with patch("requests.get", return_value=get_resp) as get:
            with patch(
                "gateway.platforms.base.cache_image_from_bytes",
                return_value="/tmp/fake.jpg",
            ):
                with patch("gateway.platforms.base._looks_like_image", return_value=True):
                    path = _feishu_download_image(
                        adapter, "img_v3_test_key", message_id="om_msg_abc"
                    )

    assert path == "/tmp/fake.jpg"
    url = get.call_args[0][0]
    assert "/messages/om_msg_abc/resources/img_v3_test_key" in url
    assert "type=image" in url
