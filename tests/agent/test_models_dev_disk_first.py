"""models.dev 磁盘缓存优先 —— 2026-09-16 停滞真因修复的闸。

背景：入站消息关键路径上（agent_route_mixin -> get_model_context_length -> fetch_models_dev）
旧序会在内存 TTL 过期时做一次 ~4.6MB 网络拉取，而 `requests.timeout` 只约束单个 socket 操作
=> 慢速滴流可拖过 30s 停滞看门狗（15:37:43 实测开火）。本闸锁住「磁盘新鲜 => 不上网」。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from agent import models_dev


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture
def env(monkeypatch, tmp_path):
    """隔离：内存缓存归零 + 磁盘缓存指向 tmp + 清 env 覆盖；返回 (cache_file, calls)。"""
    cache_file = tmp_path / "models_dev_cache.json"
    monkeypatch.setattr(models_dev, "_get_cache_path", lambda: cache_file)
    monkeypatch.setattr(models_dev, "_models_dev_cache", {}, raising=False)
    monkeypatch.setattr(models_dev, "_models_dev_cache_time", 0.0, raising=False)
    monkeypatch.delenv("MIMIR_MODELS_DEV_DISK_TTL", raising=False)
    calls: list = []

    def _spy(url, *a, **kw):
        calls.append(url)
        return _Resp({"net": {}})

    monkeypatch.setattr(models_dev.requests, "get", _spy)
    return cache_file, calls


def _write(cache_file: Path, data: dict, age_s: float = 0.0) -> None:
    cache_file.write_text(json.dumps(data), encoding="utf-8")
    if age_s:
        old = time.time() - age_s
        os.utime(cache_file, (old, old))


def test_fresh_disk_cache_skips_network(env):
    cache_file, calls = env
    _write(cache_file, {"deepseek": {"models": {"deepseek-flash": {"limit": {"context": 1000000}}}}})
    out = models_dev.fetch_models_dev()
    assert calls == [], "disk cache fresh -> network must NOT be hit"
    assert "deepseek" in out


def test_stale_disk_cache_goes_to_network(env):
    cache_file, calls = env
    _write(cache_file, {"stale": {}}, age_s=2 * 86400)
    out = models_dev.fetch_models_dev()
    assert len(calls) == 1, "stale disk cache -> exactly one network fetch"
    assert "net" in out


def test_ttl_zero_restores_network_first(env, monkeypatch):
    """回滚闸：MIMIR_MODELS_DEV_DISK_TTL=0 恢复旧的「网络优先」。"""
    cache_file, calls = env
    monkeypatch.setenv("MIMIR_MODELS_DEV_DISK_TTL", "0")
    _write(cache_file, {"disk": {}})
    out = models_dev.fetch_models_dev()
    assert len(calls) == 1, "TTL=0 must restore network-first"
    assert "net" in out


def test_force_refresh_bypasses_disk(env):
    cache_file, calls = env
    _write(cache_file, {"disk": {}})
    out = models_dev.fetch_models_dev(force_refresh=True)
    assert len(calls) == 1
    assert "net" in out


def test_network_failure_falls_back_to_stale_disk(env, monkeypatch):
    """原语义保留：网络失败 => 回退磁盘（即便已过期）。"""
    cache_file, calls = env
    _write(cache_file, {"aged": {}}, age_s=10 * 86400)

    def _boom(*a, **kw):
        calls.append("boom")
        raise OSError("network down")

    monkeypatch.setattr(models_dev.requests, "get", _boom)
    out = models_dev.fetch_models_dev()
    assert calls, "should have attempted network"
    assert "aged" in out, "must fall back to stale disk cache after network failure"


def test_missing_disk_cache_goes_to_network(env):
    cache_file, calls = env
    assert not cache_file.exists()
    out = models_dev.fetch_models_dev()
    assert len(calls) == 1
    assert "net" in out


def test_memory_cache_still_short_circuits(env):
    cache_file, calls = env
    models_dev._models_dev_cache = {"mem": {}}
    models_dev._models_dev_cache_time = time.time()
    out = models_dev.fetch_models_dev()
    assert calls == []
    assert "mem" in out


def test_source_order_disk_before_network():
    """结构闸：源文件里磁盘新鲜分支必须出现在 requests.get 之前。"""
    src = (Path(__file__).resolve().parents[2] / "agent" / "models_dev.py").read_text(encoding="utf-8")
    i_disk = src.index("_load_disk_cache_fresh()")
    i_net = src.index("response = requests.get(MODELS_DEV_URL")
    assert i_disk < i_net, "disk-fresh branch must precede the network fetch"
    assert "MIMIR_MODELS_DEV_DISK_TTL" in src, "rollback knob must exist"
