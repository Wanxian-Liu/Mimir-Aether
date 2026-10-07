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
    monkeypatch.setenv("WIKI_WAKE_OFFSET", str(tmp_path / "inbox.offset"))  # 退役：只展示
    monkeypatch.setenv("WIKI_WAKE_DISPATCHED", str(tmp_path / "inbox.dispatched"))
    monkeypatch.setenv("WIKI_WAKE_LEDGER", str(tmp_path / "inbox-processed.log"))
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


def _set_watermarks(m, dispatched=None, ledger=None, note: str = "") -> None:
    """写**活水位**：None ⇒ 删该源（用于"单源推进"/"量具不可用"臂）。"""
    dp = m.dispatched_path()
    if dispatched is None:
        dp.unlink(missing_ok=True)
    else:
        dp.write_text(str(dispatched), encoding="utf-8")
    lp = m.ledger_path()
    if ledger is None:
        lp.unlink(missing_ok=True)
    else:
        lp.write_text("2026-10-07 00:00:00 processed 1 lines (up to %d)%s\n" % (ledger, note),
                      encoding="utf-8")


def _put_inbox(m, pending: int, ts: float, watermark: int = 1) -> None:
    """夹具：1 行旧行 + `pending` 行新行；活水位推到 `watermark`（前 watermark 行视为已消费）。"""
    inbox = m.inbox_path()
    lines = ['{"id": "old", "ts": %d}' % int(ts - 5000)]
    for i in range(pending):
        lines.append('{"id": "p%d", "ts": %d}' % (i, int(ts)))
    inbox.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _set_watermarks(m, dispatched=watermark, ledger=watermark)


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
    assert mod.suppression_reason(mod.inbox_path(), mod.offset_hint_path()) is None
    assert _run(mod) == 0
    assert len(_Catcher.received) == 1, "A 通路停摆时 B 必须接管（否则安全网失效）"


# ---------------------------------------------------------------------------
# 活水位（P-2b · 2026-10-07 · 死水位退役）—— 正控 / 负控 / 反掩盖
# ---------------------------------------------------------------------------

def test_C1_retired_offset_frozen_below_n_does_not_suppress(mod):
    """**主回归**：`.offset` 冻在 1（退役死水位）而活水位推到 2 ⇒ pending=0、不得抑制。

    这是生产事故现场复刻：旧口径 `2-1=1` ⇒ 永久假红；新口径取活水位 ⇒ 0。"""
    _put_card(mod, "card-k.md")
    _put_inbox(mod, pending=1, ts=time.time(), watermark=2)   # 活水位=2，offset 缺席=退役
    mod.offset_hint_path().write_text("1", encoding="utf-8")   # 死水位落后
    pend, _ts, why = mod.inbox_pending(mod.inbox_path(), mod.offset_hint_path())
    assert pend == 0 and why == "no-pending"
    assert mod.suppression_reason(mod.inbox_path(), mod.offset_hint_path()) is None
    assert _run(mod) == 0
    assert len(_Catcher.received) == 1, "活水位已到顶 ⇒ 必须唤醒（不得被死水位压住）"


def test_C2_single_source_suffices(mod):
    """三源任一推进即视为已消费：仅台账到顶 / 仅 .dispatched 到顶 都不算积压。"""
    for dsp, led in ((0, 3), (3, 0)):
        _Catcher.received = []
        _put_card(mod, f"card-s{dsp}{led}.md")
        mod.inbox_path().write_text('{"id": "o", "ts": 1}\n{"id": "a", "ts": 2}\n'
                                    '{"id": "b", "ts": 3}\n', encoding="utf-8")
        _set_watermarks(mod, dispatched=dsp, ledger=led)
        pend, _ts, why = mod.inbox_pending(mod.inbox_path(), mod.offset_hint_path())
        assert pend == 0 and why == "no-pending", f"dsp={dsp} led={led} ⇒ {pend}/{why}"


def test_C3_dead_offset_ahead_does_not_mask_backlog(mod):
    """**负控（真未消费仍要抓得到）**：死水位反向领先（=9）不得掩盖活水位欠账。"""
    _put_card(mod, "card-l.md")
    mod.inbox_path().write_text("".join('{"id": "x%d", "ts": %d}\n' % (i, int(time.time()))
                                      for i in range(5)), encoding="utf-8")
    _set_watermarks(mod, dispatched=2, ledger=2)
    mod.offset_hint_path().write_text("9", encoding="utf-8")   # 死水位领先（脏值）
    pend, _ts, why = mod.inbox_pending(mod.inbox_path(), mod.offset_hint_path())
    assert pend == 3 and why == "pending"
    assert mod.suppression_reason(mod.inbox_path(), mod.offset_hint_path()) is not None
    assert _run(mod) == 0
    assert _Catcher.received == [], "真欠账必须抑制（死水位不得给假绿）"


def test_C4_ledger_note_with_unrelated_up_to_is_ignored(mod):
    """台账备注里出现无关 `up to 234` ⇒ 水位必须取台账行末条（锚定句式）。"""
    _put_card(mod, "card-m.md")
    _put_inbox(mod, pending=2, ts=time.time(), watermark=1)
    lp = mod.ledger_path()
    lp.write_text("2026-10-07 00:00:00 processed 1 lines (up to 1)\n"
                  "备注：另一台账 up to 234 与本水位无关\n", encoding="utf-8")
    wm, meta = mod.consumed_watermark(mod.ledger_path(), mod.dispatched_path(), mod.offset_hint_path())
    assert wm == 1 and meta["ledger_watermark"] == 1, "裸 `up to (\\d+)` 会误取 234"
    assert meta["offset_hint_retired"] is None, ".offset 缺席 ⇒ hint=None（退役字段可缺，不进判据）"


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


def test_pending_without_live_watermark_counts_all(mod):
    """**活水位缺失**（台账与 .dispatched 均不可用）⇒ 全部行视为未处理（宁可抑制）。

    2026-10-07 改造：原臂 `test_pending_without_offset_counts_all` 判的是退役的 `.offset`；
    语义保留、口径换活水位，`why` 细化为 `pending-watermark-unknown`（量具不可用
    必须与"真无积压"区分开 —— §5.5 错误语义不可裁剪）。
    """
    p = _put_card(mod, "card-i.md")
    _put_inbox(mod, pending=1, ts=time.time())
    _set_watermarks(mod, dispatched=None, ledger=None)
    pending, last_ts, why = mod.inbox_pending(mod.inbox_path(), mod.offset_hint_path())
    assert pending == 2 and why == "pending-watermark-unknown"
    assert mod.suppression_reason(mod.inbox_path(), mod.offset_hint_path()) is not None
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
