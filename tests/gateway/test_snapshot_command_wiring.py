"""M-3 接线验收：/snapshot 命令通到 restore_quick_snapshot（此前零调用者断头路）。

复核会 2026-09-22 M-3：restore_quick_snapshot 只有函数定义，网关派发表无
`snapshot` 键——run_quick_backup 打印的 "Restore with: /snapshot restore <id>"
指向不存在的命令。接线 = handler + 派发表注册。
"""

import asyncio

import pytest


class FakeEvent:
    def __init__(self, args):
        self._args = args

    def get_command_args(self):
        return self._args


@pytest.fixture
def iso_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("model:\n  default: test\n")
    return tmp_path


def test_handler_exists_on_gateway_runner():
    """接线判据 1：方法挂在 GatewayRunner 类树上（RouterMixin 继承链）。"""
    from gateway.run import GatewayRunner

    assert hasattr(GatewayRunner, "_handle_snapshot_command")


def test_dispatch_table_has_snapshot():
    """接线判据 2：派发表有 snapshot 键且指向该 handler。"""
    import gateway.run as run_mod

    src = open(run_mod.__file__, encoding="utf-8").read()
    assert '"snapshot": "_handle_snapshot_command"' in src


def test_snapshot_create_list_restore_roundtrip(iso_home):
    """行为契约：create → list 可见 → 改坏 → restore 复原。"""
    from mimir_cli.backup import (
        create_quick_snapshot,
        list_quick_snapshots,
        restore_quick_snapshot,
    )

    sid = create_quick_snapshot(label="rt-test")
    assert sid, "create 失败（状态文件未命中？）"
    assert any(s.get("id") == sid for s in list_quick_snapshots())

    (iso_home / "config.yaml").write_text("CORRUPTED")
    assert restore_quick_snapshot(sid)
    content = (iso_home / "config.yaml").read_text()
    assert "CORRUPTED" not in content and "default: test" in content


def test_handler_list_and_bad_restore(iso_home):
    """行为契约：/snapshot 列表含新快照；restore 不存在 id 明确报错。"""
    from gateway.run import GatewayRunner
    from mimir_cli.backup import create_quick_snapshot

    sid = create_quick_snapshot(label="ui-test")
    assert sid

    class FakeRunner:
        _handle_snapshot_command = GatewayRunner._handle_snapshot_command

    runner = FakeRunner()
    out = asyncio.run(runner._handle_snapshot_command(FakeEvent("")))
    assert "snapshot(s)" in out and sid in out

    out2 = asyncio.run(runner._handle_snapshot_command(FakeEvent("restore no-such-id")))
    assert "❌" in out2

    out3 = asyncio.run(runner._handle_snapshot_command(FakeEvent("bogus_action")))
    assert "Usage" in out3
