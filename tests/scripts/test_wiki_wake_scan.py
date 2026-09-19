"""wiki_wake_scan 判重三层 - twin-arm 验收（2026-09-19 · 刘哥批）。

## 为什么这么测

被测对象是「派发前的闸」：它的失效形态不会报错，只会静默双唤醒或静默不唤醒。
所以：① 每层都要有「坏样本被拦」与「好样本不被误拦」两侧；② 真实对象
（真 wiki 目录 / 真收件箱 / 真认领目录）零接触 —— 全部重定向到 tmp 夹具，
并在收尾断言其 mtime_ns 未变（负控自身不得污染现场）。

## 臂表

| 臂 | 夹具状态 | 期望 |
|:--|:--|:--|
| A1 | 收件箱有新鲜未处理行 | 抑制（不 POST）— 跨生产者判重主臂 |
| A2 | 认领新鲜且哈希相同 | 跳过（不 POST）— 在飞窗口 |
| A3 | 卡内已有 ## Mimir 段 | 跳过（不 POST）— 产品级幂等（BURNFIX 回归） |
| B1 | 无待处理 + 无认领（孪生） | 唤醒（POST 一次，载荷含卡名） |
| B2 | 认领已过期（stale） | 唤醒 |
| B3 | 认领哈希已变（卡被改过） | 唤醒 |
| B4 | 未处理行已变旧（> 抑制窗） | 唤醒 — 证明 L1 是 fail-open：A 通则坏掉时 B 接管 |
"""

from __future__ import annotations

import importlib
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

CARD = """---
title: fixture
status: mimir
---

# fixture body
"""


class _Catcher(BaseHTTPRequestHandler):
    received: list = []

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace")
        type(self).received.append(raw)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "started", "run_id": "fixture-run"}')

    def log_message(self, *a):  # silence
        return


@pytest.fixture()
def mod(tmp_path, monkeypatch):
    wiki = tmp_path / "discussions"
    wiki.mkdir()
    monkeypatch.setenv("WIKI_WAKE_WIKI_DIR", str(wiki))
    monkeypatch.setenv("WIKI_WAKE_INBOX", str(tmp_path / "inbox.jsonl"))
    monkeypatch.setenv("WIKI_WAKE_OFFSET", str(tmp_path / "inbox.offset"))
    monkeypatch.setenv("WIKI_WAKE_CLAIM_DIR", str(tmp_path / "claims"))
    monkeypatch.setenv("WIKI_WAKE_LOG", str(tmp_path / "wiki-waker.log"))
    monkeypatch.setenv("WIKI_WAKE_SUPPRESS_WINDOW_S", "900")
    monkeypatch.setenv("WIKI_WAKE_CLAIM_TTL_S", "1800")

    import wiki_wake_scan as m

    importlib.reload(m)
    _Catcher.received = []
    srv = HTTPServer(("127.0.0.1", 0), _Catcher)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("WIKI_WAKE_GATEWAY", "http://127.0.0.1:" + str(srv.server_port))
    yield m
    getattr(srv, "shutdown")()


# ---------------------------------------------------------------------------
# 夹具助手
# ---------------------------------------------------------------------------

def _put_card(m, name: str, body: str = CARD) -> Path:
    p = m.wiki_dir() / name
    p.write_text(body, encoding="utf-8")
    return p


def _put_inbox(m, pending: int, ts: float) -> None:
    inbox = m.inbox_path()
    lines = ['{"id": "old", "ts": %d}' % int(ts - 5000)]
    for i in range(pending):
        lines.append('{"id": "p%d", "ts": %d}' % (i, int(ts)))
    inbox.write_text("\n".join(lines) + "\n", encoding="utf-8")
    m.offset_path().write_text("1", encoding="utf-8")  # 只认第 1 行为已处理


def _run(m, *argv) -> int:
    return m.main(list(argv))


# ---------------------------------------------------------------------------
# A 臂 —— 坏样本必须被拦
# ---------------------------------------------------------------------------

def test_A1_fresh_pending_inbox_suppresses(mod):
    """跨生产者判重主臂：A 通路有新鲜未处理行 ⇒ B 不派发。"""
    _put_card(mod, "card-a.md")
    _put_inbox(mod, pending=1, ts=time.time())
    assert _run(mod) == 0
    assert _Catcher.received == [], "有新鲜待处理收件箱行时不得重复派发"
    assert not mod.claim_path(mod.wiki_dir() / "card-a.md").exists()


def test_A2_fresh_claim_same_hash_skips(mod):
    """在飞窗口：同一张卡、同一哈希、认领未过期 ⇒ 跳过。"""
    p = _put_card(mod, "card-b.md")
    mod.write_claim(p, p.read_text(encoding="utf-8"))
    assert _run(mod) == 0
    assert _Catcher.received == []


def test_A3_existing_mimir_section_skips(mod):
    """产品级幂等（原 BURNFIX 行为必须保留）。"""
    _put_card(mod, "card-c.md", CARD + "\n## Mimir - 2026-09-18\n已处理。\n")
    assert _run(mod) == 0
    assert _Catcher.received == []
    ok, why = mod.is_candidate(CARD + "\n## Mimir x\n")
    assert ok is False and "already-has" in why


# ---------------------------------------------------------------------------
# B 臂 —— 好样本不得被误拦（孪生对照）
# ---------------------------------------------------------------------------

def test_B1_clean_fixture_wakes(mod):
    """孪生：无待处理、无认领、卡待接棒 ⇒ 必须唤醒，且载荷含卡名。"""
    _put_card(mod, "card-d.md")
    assert _run(mod) == 0
    assert len(_Catcher.received) == 1
    payload = _Catcher.received[0]
    assert "card-d.md" in payload
    assert '"source": "wiki-watcher"' in payload
    assert mod.claim_path(mod.wiki_dir() / "card-d.md").exists(), "唤醒成功后必须落认领"


def test_B2_stale_claim_wakes(mod):
    """认领过期 ⇒ 不得阻止唤醒（否则慢 run 场景卡死）。"""
    p = _put_card(mod, "card-e.md")
    mod.write_claim(p, p.read_text(encoding="utf-8"))
    cp = mod.claim_path(p)
    data = json.loads(cp.read_text(encoding="utf-8"))
    data["ts"] = time.time() - mod.CLAIM_TTL_S - 60
    cp.write_text(json.dumps(data), encoding="utf-8")
    assert _run(mod) == 0
    assert len(_Catcher.received) == 1


def test_B3_changed_hash_wakes(mod):
    """卡被改过（哈希变）⇒ 认领失效，必须唤醒。"""
    p = _put_card(mod, "card-f.md")
    mod.write_claim(p, p.read_text(encoding="utf-8"))
    p.write_text(CARD + "\n新增一段。\n", encoding="utf-8")
    assert _run(mod) == 0
    assert len(_Catcher.received) == 1


def test_B4_stale_inbox_pending_fails_open(mod):
    """L1 是 fail-open：未处理行已变旧（A 通则坏掉）⇒ B 必须接管。"""
    _put_card(mod, "card-g.md")
    _put_inbox(mod, pending=1, ts=time.time() - mod.SUPPRESS_WINDOW_S - 300)
    assert mod.suppression_reason(mod.inbox_path(), mod.offset_path()) is None
    assert _run(mod) == 0
    assert len(_Catcher.received) == 1, "A 通路停摆时 B 必须接管（否则安全网失效）"


# ---------------------------------------------------------------------------
# 边界与失败面
# ---------------------------------------------------------------------------

def test_no_candidate_is_silent(mod):
    """无事可做必须零输出（cron 侧据此不投递、不噪声）。"""
    assert _run(mod) == 0
    assert _Catcher.received == []


def test_gateway_unreachable_returns_nonzero(mod, monkeypatch):
    """网关不可达 ⇒ 退出码非 0（cron 记 error ⇒ 失败可听），且不得落认领。"""
    _put_card(mod, "card-h.md")
    monkeypatch.setenv("WIKI_WAKE_GATEWAY", "http://127.0.0.1:9")  # 死端口
    assert _run(mod) == 1
    assert not mod.claim_path(mod.wiki_dir() / "card-h.md").exists()


def test_pending_without_offset_counts_all(mod):
    """offset 缺失 ⇒ 全部行视为未处理（保守方向：宁可抑制）。"""
    p = _put_card(mod, "card-i.md")
    _put_inbox(mod, pending=1, ts=time.time())
    mod.offset_path().unlink()
    pending, last_ts, why = mod.inbox_pending(mod.inbox_path(), mod.offset_path())
    assert pending == 2 and why == "pending"
    assert mod.suppression_reason(mod.inbox_path(), mod.offset_path()) is not None
    assert _run(mod) == 0
    assert _Catcher.received == []
    assert p.exists()


# ---------------------------------------------------------------------------
# 现场零污染（RS17 同族：负控自身不得改真实对象）
# ---------------------------------------------------------------------------

def test_real_objects_untouched(mod):
    """真实 wiki / 收件箱 / 认领目录的 mtime_ns 必须与测试前一致。"""
    watched = []
    for p in (Path.home() / "wiki" / "discussions", Path.home() / ".openclaw" / "data" / "buzz-inbox-mimir.jsonl"):
        if p.exists():
            watched.append((p, p.stat().st_mtime_ns))
    _put_card(mod, "card-j.md")
    _run(mod)
    for p, before in watched:
        assert p.stat().st_mtime_ns == before, f"测试污染了真实对象: {p}"
