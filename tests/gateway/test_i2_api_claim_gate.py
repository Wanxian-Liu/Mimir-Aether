"""I-2 契约：api 直连通道与 buzz-watcher 共用**同一套**收件箱认领闸（2026-10-07）。

判据（任务书 §3）：断言「api 通道投递后 watcher 不得重复认领」。
做法：跑**真实** claim 工具 + **真实** watcher.sh，全部路径 env 覆写进 tmp_path；
网关指向死端口（即使判据失效也不会真实派发 run）。

为什么必须有这条用例：`~/.hermes/scripts/mimir-send.sh` 把同一封信封
①写入 buzz 收件箱 ②同时 POST /v1/runs 直连唤醒；watcher（<=5min）只看
「行号 vs dispatched 游标」⇒ 改动前同一单被唤醒两次（实证 2026-10-07
03:36:17 api 投第 8 单 / 03:50:01 watcher RESERVE range=44..44 prev_dispatched=43）。

安全（学 test_buzz_watcher_ledger G2 勘误）：**凡 `${VAR:-默认}` 都必须在 fixture 里覆写**，
否则脚本/认领器会写到**真实**收件箱游标。本 fixture 覆写 6 个键 + claim 台账键。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from gateway.inbox_claim_gate import (  # noqa: E402
    abort_api_claim,
    claim_for_api_run,
    commit_api_claim,
    parse_inbox_line,
)

SCRIPT = Path(os.path.expanduser("~/.mimiraether/scripts/buzz-inbox-watcher.sh"))
CLAIM_TOOL = Path(os.path.expanduser("~/.mimiraether/scripts/buzz_inbox_claim.py"))
DEAD = "http://127.0.0.1:9"  # discard 端口：连接必被拒


@pytest.fixture
def sb(tmp_path, monkeypatch):
    """全隔离沙箱：6 个 env 键 + claim 台账键；并把它们注入本进程 env（认领器是子进程）。"""
    d = {
        "inbox": tmp_path / "inbox.jsonl",
        "offset": tmp_path / "inbox.offset",
        "dispatched": tmp_path / "inbox.dispatched",
        "lock": tmp_path / "inbox.waking",
        "ledger": tmp_path / "inbox-processed.log",
        "gate": tmp_path / "api_claim_gate.jsonl",
        "tmp": tmp_path,
    }
    d["inbox"].write_text(
        json.dumps({"id": "m1", "from": "hermes", "to": "mimir", "kind": 1,
                    "content": "【I-2 用例】同一信封"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    d["offset"].write_text("0\n", encoding="utf-8")
    d["dispatched"].write_text("0\n", encoding="utf-8")
    d["ledger"].write_text("", encoding="utf-8")
    overrides = {
        "BUZZ_INBOX_MIMIR": str(d["inbox"]),
        "BUZZ_INBOX_MIMIR_OFFSET": str(d["offset"]),
        "BUZZ_INBOX_MIMIR_DISPATCHED": str(d["dispatched"]),
        "BUZZ_INBOX_MIMIR_LOCK": str(d["lock"]),
        "BUZZ_INBOX_MIMIR_LEDGER": str(d["ledger"]),
        "BUZZ_INBOX_MIMIR_CLAIM_TOOL": str(CLAIM_TOOL),
        "BUZZ_INBOX_CLAIM_GATE_LOG": str(d["gate"]),
        "MIMIR_GATEWAY_URL": DEAD,
    }
    for k, v in overrides.items():
        monkeypatch.setenv(k, v)
    d["env"] = dict(os.environ)
    d["overrides"] = overrides
    return d


def _run_watcher(d):
    return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True,
                          env=d["env"], timeout=30)


def _dispatched(d):
    return d["dispatched"].read_text(encoding="utf-8").strip()


def _gate_rows(d):
    if not d["gate"].exists():
        return []
    return [json.loads(x) for x in d["gate"].read_text(encoding="utf-8").splitlines() if x.strip()]


# ── 正控：证明探针有效（不认领时 watcher 确实会尝试唤醒）─────────────────────
def test_1_positive_control_watcher_would_wake(sb):
    r = _run_watcher(sb)
    assert "唤醒失败" in r.stdout, "正控失败：watcher 未到派发步（探针恒否，判据无意义）"
    assert _dispatched(sb) == "0", "派发失败不得推进游标（下次要能重试）"


# ── 核心判据：api 通道认领后，watcher 不得重复认领 ──────────────────────────
def test_2_api_claim_then_watcher_does_not_reclaim(sb):
    d = claim_for_api_run("run_case2", {"inbox_line": 1})
    assert d.state == "issued", d.readout()
    assert d.start == 1 and d.end == 1
    commit_api_claim(d)
    assert _dispatched(sb) == "1", "认领即推进：dispatched 必须已被原子抬到 1"

    r = _run_watcher(sb)
    assert "不重复派发" in r.stdout, "watcher 未走门控（读数缺失）: %r" % r.stdout
    assert "唤醒失败" not in r.stdout, "重复唤醒未被拦（本用例要治的那一例）: %r" % r.stdout
    assert _dispatched(sb) == "1", "dispatched 被二次推进（%s）" % _dispatched(sb)


# ── 并发形态：第一个认领未落地（未 commit）⇒ 第二个必须被 HELD 拒 ────────────
def test_3_open_claim_blocks_the_other_channel(sb):
    a = claim_for_api_run("run_a", {"inbox_line": 1})
    assert a.state == "issued", a.readout()
    b = claim_for_api_run("run_b", {"inbox_line": 1})   # 不同 owner = 真并发消费者
    assert b.state == "rejected", b.readout()
    assert b.rc == 2, "应为 HELD(rc=2)，实际 rc=%s detail=%s" % (b.rc, b.detail)


# ── 顺序形态：认领已 commit ⇒ 后来的认领返「无增量」被拒 ─────────────────────
def test_4_committed_claim_blocks_late_duplicate(sb):
    a = claim_for_api_run("run_a", {"inbox_line": 1})
    assert a.state == "issued", a.readout()
    commit_api_claim(a)
    b = claim_for_api_run("run_b", {"inbox_line": 1})
    assert b.state == "rejected", b.readout()
    assert b.rc == 1, "应为 rc=1（无增量），实际 rc=%s detail=%s" % (b.rc, b.detail)
    abort_api_claim(b)   # 幂等：非 issued 不发 abort（应无副作用）


# ── 不许改变正常投递：不带 inbox_line 的 api 调用完全不触碰 claim ────────────
def test_5_plain_api_request_does_not_touch_claim(sb):
    d = claim_for_api_run("run_plain", {})
    assert d.state == "none", d.readout()
    assert _dispatched(sb) == "0", "普通 api 调用不得推进收件箱游标"
    assert not (sb["tmp"] / "inbox.dispatched.claim.json").exists(), "不得产生认领记录"
    assert _gate_rows(sb) == [], "普通 api 调用不得写闸台账"


# ── 判据 2：闸拒必须**可见**（日志/台账行），不许静默丢弃 ────────────────────
def test_6_rejection_is_visible_in_ledger(sb):
    a = claim_for_api_run("run_a", {"inbox_line": 1})
    commit_api_claim(a)
    claim_for_api_run("run_b", {"inbox_line": 1})
    rows = _gate_rows(sb)
    rej = [r for r in rows if r.get("event") == "rejected"]
    assert rej, "闸拒未留台账行（静默丢弃 = 老病）: %r" % rows
    assert rej[0].get("rc") == 1 and "already dispatched" in rej[0].get("reason", "")
    assert rej[0].get("run_id") == "run_b"


# ── 闸故障不停摆：认领器缺失 ⇒ degraded（放行）且出声 ───────────────────────
def test_7_missing_claim_tool_degrades_open(sb, monkeypatch):
    monkeypatch.setenv("BUZZ_INBOX_MIMIR_CLAIM_TOOL", str(sb["tmp"] / "nope.py"))
    sb["env"] = dict(os.environ)
    d = claim_for_api_run("run_case7", {"inbox_line": 1})
    assert d.state == "degraded", d.readout()
    rows = _gate_rows(sb)
    assert any(r.get("event") == "degraded" for r in rows), "降级未留读数: %r" % rows


# ── inbox_line 解析形态（派单方手写方便，机器只认这几种）────────────────────
@pytest.mark.parametrize("raw,expect", [
    (44, (44, 44)),
    ("44", (44, 44)),
    ("44..44", (44, 44)),
    ("44-45", (44, 45)),
    ([44, 45], (44, 45)),
    ({"line": 7}, (7, 7)),
    ({"start": 7, "end": 9}, (7, 9)),
    (0, None),
    ("abc", None),
    (None, None),
    (True, None),
])
def test_8_parse_inbox_line_forms(raw, expect):
    assert parse_inbox_line({"inbox_line": raw}) == expect
    assert parse_inbox_line({}) is None
    assert parse_inbox_line(None) is None
