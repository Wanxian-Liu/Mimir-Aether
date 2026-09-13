"""RS2① 契约：watcher 派发前查账（U15 账本级幂等 · 四方裁决 2026-09-13）。

跑**真实脚本**（``~/.mimiraether/scripts/buzz-inbox-watcher.sh``），三态全测：
  · 账本已处理到 >= total → 不重复派发（INC-10 反演，本卡立项的那一例）
  · 账本缺失 → **降级放行**（派发正文打标 + 账本同流写可见标记行）
  · 账本损坏（行数骤降）→ **fail-closed**（exit 3，不派发）

安全：``MIMIR_GATEWAY_URL`` 指向死端口 —— 即使判据失效也不会真实派发 run。
所有路径经 env 覆写进 tmp_path，**不碰真实收件箱/账本/offset**。
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(os.path.expanduser("~/.mimiraether/scripts/buzz-inbox-watcher.sh"))
DEAD = "http://127.0.0.1:9"  # discard 端口：连接必被拒

pytestmark = pytest.mark.skipif(
    not SCRIPT.exists(), reason="watcher 脚本不在本机（home 侧资产）"
)


@pytest.fixture
def sandbox(tmp_path):
    inbox = tmp_path / "inbox.jsonl"
    offset = tmp_path / "inbox.offset"
    lock = tmp_path / "inbox.waking"
    ledger = tmp_path / "inbox-processed.log"
    env = dict(os.environ)
    env.update(
        {
            "BUZZ_INBOX_MIMIR": str(inbox),
            "BUZZ_INBOX_MIMIR_OFFSET": str(offset),
            "BUZZ_INBOX_MIMIR_LOCK": str(lock),
            "BUZZ_INBOX_MIMIR_LEDGER": str(ledger),
            "MIMIR_GATEWAY_URL": DEAD,
        }
    )
    env.pop("BUZZ_INBOX_MIMIR_OFFSET", None) if False else None
    return {
        "inbox": inbox,
        "offset": offset,
        "lock": lock,
        "ledger": ledger,
        "env": env,
        "tmp": tmp_path,
    }


def _run(sb):
    return subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=sb["env"],
        timeout=30,
    )


def _seed(sb, total, offset, ledger_line=None, extra="", day_dir=None):
    sb["inbox"].write_text(
        "".join('{"id":"m%d"}\n' % i for i in range(1, total + 1)), encoding="utf-8"
    )
    sb["offset"].write_text(str(offset), encoding="utf-8")
    if ledger_line is not None:
        sb["ledger"].write_text(ledger_line, encoding="utf-8")


def test_1_ledger_ahead_blocks_redispatch_inc10(sandbox):
    """INC-10 反演：total=113 / offset=112 / 账本「up to 113」→ 不得重复派发。"""
    _seed(sandbox, total=113, offset=112, ledger_line="2026-09-13 10:17:21 processed 1 lines (up to 113)\n")
    r = _run(sandbox)
    assert r.returncode == 0, r.stderr
    assert "不重复派发" in r.stdout, r.stdout
    assert sandbox["offset"].read_text(encoding="utf-8").strip() == "112", "offset 不得推进"


def test_2_ledger_behind_dispatches(sandbox):
    """账本落后于 total → 允许派发（查账不得把正常通路也堵死）。"""
    _seed(sandbox, total=100, offset=90, ledger_line="2026-09-13 09:00:01 processed 1 lines (up to 50)\n")
    r = _run(sandbox)
    assert "不重复派发" not in r.stdout
    assert "唤醒失败" in r.stdout or "唤醒成功" in r.stdout, r.stdout


def test_3_missing_ledger_degrades_with_visible_marker(sandbox):
    """账本缺失 → 降级放行 + 派发正文打标 + 账本同流写可见标记行（防降级成沉默常态）。"""
    _seed(sandbox, total=10, offset=5)  # 无 ledger 文件
    r = _run(sandbox)
    assert r.returncode == 0, r.stderr
    assert "唤醒失败" in r.stdout or "唤醒成功" in r.stdout, "应尝试派发（降级放行）: " + r.stdout
    assert sandbox["ledger"].exists(), "降级必须留下可见标记行"
    assert "DEGRADED dispatch" in sandbox["ledger"].read_text(encoding="utf-8")


def test_4_corrupted_ledger_fails_closed(sandbox):
    """账本损坏（行数骤降 < 高水位一半）→ fail-closed：exit 3 + 不派发。"""
    _seed(sandbox, total=10, offset=5, ledger_line="x\n" * 100)
    sandbox["ledger"].with_name(sandbox["ledger"].name + ".hwm").write_text("100\n", encoding="utf-8")
    # 先跑一次把 hwm 建立为 100（脚本只在增长时更新，此处直接写入更稳）
    sb = sandbox
    sb["ledger"].write_text("x\n" * 20, encoding="utf-8")  # 20 < 100/2
    r = _run(sb)
    assert r.returncode == 3, "损坏必须 fail-closed，实际 rc=%s stdout=%s" % (r.returncode, r.stdout)
    assert "账本损坏" in r.stdout
    assert sb["offset"].read_text(encoding="utf-8").strip() == "5", "fail-closed 不得推进 offset"


def test_5_no_new_lines_is_silent_unchanged(sandbox):
    """基线不回归：无增量 → 静默 exit 0（零 token 预扫描语义保持）。"""
    _seed(sandbox, total=5, offset=5, ledger_line="2026-09-13 08:00:00 processed 5 lines (up to 5)\n")
    r = _run(sandbox)
    assert r.returncode == 0
    assert r.stdout.strip() == ""
