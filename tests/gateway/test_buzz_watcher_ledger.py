"""RS2① 契约：watcher 派发前查账（U15 账本级幂等 · 四方裁决 2026-09-13）。

跑**真实脚本**（``~/.mimiraether/scripts/buzz-inbox-watcher.sh``），三态全测：
  · 账本已处理到 >= total → 不重复派发（INC-10 反演，本卡立项的那一例）
  · 账本缺失 → **降级放行**（派发正文打标 + 账本同流写可见标记行）
  · 账本损坏（行数骤降）→ **fail-closed**（exit 3，不派发）

安全：``MIMIR_GATEWAY_URL`` 指向死端口 —— 即使判据失效也不会真实派发 run。
所有路径经 env 覆写进 tmp_path，**不碰真实收件箱/账本/offset/派发游标**。

2026-10-07 勘误（G2）：上面这句原先**不成立**——fixture 漏覆写
``BUZZ_INBOX_MIMIR_DISPATCHED``，watcher 的 ROTATION 分支（total < max(offset,
dispatched)）遂写到**真实**派发游标（实测 39→0）：整仓 pytest 每跑一次即清空一次
真实派发门控（INC-10 同族重复派发窗口）。四个 env 覆写 ≠ 全部 env 覆写——脚本里每个
``${VAR:-默认}`` 都是一条需要 sandbox 化的真实路径。判据（跑后真游标不得变）见回执。
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
    # G2 (2026-10-07)：**必须**覆写派发游标。watcher 的 ROTATION/TRUNCATION 分支
    # （脚本 L41 `echo 0 > "$DISPATCHED_FILE"`，触发条件 total < max(offset, dispatched)）
    # 会写这个文件；fixture 原先漏了它 ⇒ 脚本读到**真实**游标（实测 39），sandbox 的
    # total 小于它 ⇒ 逐例越界写真实文件。整仓 pytest 每跑一次 = 真实派发门控被清空一次
    # （INC-10 同族重复派发窗口）。test_1 也因真实 d_old=39 < 113 而门控不放行、断言落空。
    dispatched = tmp_path / "inbox.dispatched"
    env = dict(os.environ)
    env.update(
        {
            "BUZZ_INBOX_MIMIR": str(inbox),
            "BUZZ_INBOX_MIMIR_OFFSET": str(offset),
            "BUZZ_INBOX_MIMIR_DISPATCHED": str(dispatched),
            "BUZZ_INBOX_MIMIR_LOCK": str(lock),
            "BUZZ_INBOX_MIMIR_LEDGER": str(ledger),
            "MIMIR_GATEWAY_URL": DEAD,
        }
    )
    return {
        "inbox": inbox,
        "offset": offset,
        "dispatched": dispatched,
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


def _seed(sb, total, offset, ledger_line=None, dispatched=0, extra="", day_dir=None):
    sb["inbox"].write_text(
        "".join('{"id":"m%d"}\n' % i for i in range(1, total + 1)), encoding="utf-8"
    )
    sb["offset"].write_text(str(offset), encoding="utf-8")
    # 派发游标＝同纪元门控判据（watcher L70 `d_old >= total`）；不播种则读不到文件→0。
    sb["dispatched"].write_text(str(dispatched), encoding="utf-8")
    if ledger_line is not None:
        sb["ledger"].write_text(ledger_line, encoding="utf-8")


def test_1_ledger_ahead_blocks_redispatch_inc10(sandbox):
    """INC-10 反演：已处理到 total → 不得重复派发。

    门控语义 2026-10-07 改判（watcher 脚本 L67-73 原文）：「账本最后 up to N >= total」
    → 「**同纪元** dispatched 游标 >= total」。原因：账本编号跨纪元累计（实测 234 vs
    total 34）⇒ 旧判据恒真 ⇒ 门控永久关闭、watcher 自动唤醒静默死。
    故本用例按**现行**语义播种 dispatched=113（本用例最后改动 2026-09-13，早于该改判）。
    账本行仍保留：它现在是 degraded / fail-closed 的判据来源（test_3 / test_4）。
    """
    _seed(sandbox, total=113, offset=112, dispatched=113,
          ledger_line="2026-09-13 10:17:21 processed 1 lines (up to 113)\n")
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


# ── T7-F1（2026-10-07）：认领原子性 —— 同单双投只进一次 + 真实状态不得被碰 ──────
import hashlib  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

REAL_STATE = [
    os.path.expanduser("~/.openclaw/data/buzz-inbox-mimir.offset"),
    os.path.expanduser("~/.openclaw/data/buzz-inbox-mimir.dispatched"),
    os.path.expanduser("~/.openclaw/data/buzz-inbox-mimir.dispatched.claim.json"),
]
CLAIM_TOOL = Path(os.path.expanduser("~/.mimiraether/scripts/buzz_inbox_claim.py"))


def _real_sig():
    out = {}
    for q in REAL_STATE:
        try:
            with open(q, "rb") as f:
                out[q] = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            out[q] = None
    return out


def test_6_claim_concurrency_single_entry(sandbox):
    """同单双投（多进程同刻取同一条记录）⇒ 仅一次进入；真实游标/认领零改动。

    认领器状态文件派生自 DISPATCHED ⇒ sandbox 覆写即隔离（G2 同族回归面）。
    """
    if not CLAIM_TOOL.exists():
        pytest.skip("认领器不在本机")
    before = _real_sig()
    _seed(sandbox, total=3, offset=0, dispatched=0,
          ledger_line="2026-10-07 00:00:00 processed 0 lines (up to 0)\n")
    env = dict(sandbox["env"])
    env["CLAIM_T0"] = "%.6f" % (time.time() + 1.0)
    worker = sandbox["tmp"] / "worker.py"
    worker.write_text(
        "import os,subprocess,sys,time\n"
        "t0=float(os.environ.get('CLAIM_T0','0'))\n"
        "time.sleep(max(0.0,t0-time.time()))\n"
        "sys.exit(subprocess.call(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    procs = [
        subprocess.Popen(
            [sys.executable, str(worker), sys.executable, str(CLAIM_TOOL),
             "reserve", "--owner", "c%d" % i],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for i in range(3)
    ]
    rcs = [pr.wait(timeout=60) for pr in procs]
    assert rcs.count(0) == 1, "并发认领必须恰 1 次进入，实测 rc=%s" % rcs
    assert sandbox["dispatched"].read_text(encoding="utf-8").strip() == "3"
    assert _real_sig() == before, "真实游标/认领文件被越界写（G2 同族）"
