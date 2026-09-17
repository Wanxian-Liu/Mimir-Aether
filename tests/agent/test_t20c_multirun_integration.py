"""T20-c「挂账—结算」的**跨 run / 跨进程**集成测试（C-3 · Loki 反对① / H2）。

背景：B1/T20-c 验收时**只跑过单 run** —— Loki 票 B-4 反对①：「H2『B1 跨 run 是否退化』
未验证 · 只单 run 验证过 = 红旗·需补多 run 集成测试」。本文件把跨 run / 跨进程路径钉住。

结构事实（**盘上读码，非推断**）：
  `gateway/platforms/api_server.py:1538` `agent = self._create_agent(...)` 位于
  `_run_agent() -> _run()` **体内** ⇒ **每 run 新建 agent（⇒ 每 run 新 compressor）**。
  而挂账是 compressor 的**实例字段** `_pending_post_measure` ⇒ 跨 run **必归零**。

本文件 4 臂（单变量 = 实例 / 进程身份）：
  A 同 run（**正控**）   : 同实例结算 ⇒ 台账出现 `kind=post_measure` / `settle_reason=settled`
  B 跨 run（同进程）     : 挂账在实例 A，结算由**新实例 B**发起 ⇒ 台账**不增**（挂账对 B 不可见）
  C 跨进程（真·杀重起）  : 子进程①挂账后退出；子进程②尝试结算 ⇒ 台账**不增**
  D 已落记录持久性       : 已结算的 `post_measure` 行**跨进程仍在**（读文件即可复现）

⚠️ 本文件**不**断言「跨 run 应否可用」——那是 LOKI 反对① 给两选项的**待裁项**
（a 补跨 run 结算通路 / b 接受「仅单 run 生效」并写明）。本文件钉的是**现状事实**，
修 (a) 时 B/C 臂应按新契约改写（届时会红，属预期）。
"""
import json
import os
import pathlib
import subprocess
import sys
import time

import pytest

import agent.context_compressor as CC
from agent.context_compressor import MimirContextCompressor

REPO = pathlib.Path(CC.__file__).resolve().parent.parent


def _mk():
    c = MimirContextCompressor(
        model="test-model", context_length=8000, threshold_percent=0.5,
        protect_first_n=3, protect_last_n=6, tail_token_budget=2000,
        api_key="fake-key", base_url="http://127.0.0.1:9",
    )
    c.update_model("test-model", 8000)
    return c


def _arm(c, **kw):
    """挂账（与生产 applied 分支同形状；直接置字段以隔离 compression 过程）。"""
    base = dict(
        of_ts="2026-09-17T00:00:00", pre_actual=100_000, pre_estimate=100_500,
        estimate_after=40_000, summary_total_tokens=5_000, summary_prompt_tokens=4_800,
        summary_mode="llm", gate_version="test.mr.v1", armed_at=time.time(),
        compressed_count=35, original_count=400,
    )
    base.update(kw)
    c._pending_post_measure = base
    return base


def _ledger(home):
    p = pathlib.Path(home) / "data" / "compression_quality.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _posts(home):
    return [r for r in _ledger(home) if r.get("kind") == "post_measure"]


def _home_of():
    from mimir_constants import get_mimir_home
    return get_mimir_home()


# 子进程用的探针源码（跨进程臂）。参数经环境变量传入，避免 argv 形态差异。
_PROBE = """
import os, sys, time
sys.path.insert(0, {repo!r})
import agent.context_compressor as CC
from agent.context_compressor import MimirContextCompressor as M
c = M(model="test-model", context_length=8000, threshold_percent=0.5,
      protect_first_n=3, protect_last_n=6, tail_token_budget=2000,
      api_key="fake-key", base_url="http://127.0.0.1:9")
c.update_model("test-model", 8000)
mode = sys.argv[1]
if mode == "arm":
    c._pending_post_measure = dict(
        of_ts="2026-09-17T00:00:00", pre_actual=100000, pre_estimate=100500,
        estimate_after=40000, summary_total_tokens=5000, summary_prompt_tokens=4800,
        summary_mode="llm", gate_version="test.mr.v1", armed_at=time.time(),
        compressed_count=35, original_count=400)
    print("ARMED", os.getpid())
elif mode == "settle":
    c.settle_post_measure(49326, message_count=56)
    print("SETTLED", os.getpid())
elif mode == "arm_and_settle":
    c._pending_post_measure = dict(
        of_ts="2026-09-17T00:00:00", pre_actual=100000, pre_estimate=100500,
        estimate_after=40000, summary_total_tokens=5000, summary_prompt_tokens=4800,
        summary_mode="llm", gate_version="test.mr.v1", armed_at=time.time(),
        compressed_count=35, original_count=400)
    c.settle_post_measure(49326, message_count=56)
    print("DONE", os.getpid())
"""


def _run_probe(mode, home, repo=None):
    env = dict(os.environ)
    for k in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "HERMES_HOME"):
        env[k] = str(home)
    return subprocess.run(
        [sys.executable, "-c", _PROBE.format(repo=str(repo or REPO)), mode],
        cwd=str(REPO), env=env, capture_output=True, text=True, timeout=300,
    )


# ── A · 同 run 结算（正控：证明结算通路本身可用）────────────────────────────

class TestSameRunSettle:
    def test_same_instance_settles_and_writes_ledger(self, tmp_path):
        home = _home_of()
        before = len(_posts(home))
        c = _mk()
        _arm(c)
        c.settle_post_measure(49_326, message_count=56)
        posts = _posts(home)
        assert len(posts) == before + 1, "同实例结算未落台账 ⇒ 结算通路本身坏了（后续臂无意义）"
        r = posts[-1]
        assert r["settle_reason"] == "settled"
        assert r["post_actual_prompt_tokens"] == 49_326
        assert r["actual_delta_tokens"] == 100_000 - 49_326
        assert r["net_tokens"] == (100_000 - 49_326) - 5_000
        assert r["net_sign"] == "positive"
        assert c._pending_post_measure is None, "结算后应清账（单飞）"


# ── B · 跨 run（同进程新实例）⇒ 挂账不可见 ──────────────────────────────────

class TestCrossRunNewInstance:
    def test_new_instance_cannot_settle_previous_instance_pending(self):
        """单变量 = 实例身份：同样的挂账、同样的 post，只换**发起结算的实例**。"""
        home = _home_of()
        before = len(_posts(home))
        a = _mk()
        _arm(a)                               # run N 挂账（生产：run 结束）
        b = _mk()                             # run N+1：新 agent ⇒ 新 compressor（api_server.py:1538）
        b.settle_post_measure(49_326, message_count=56)
        assert len(_posts(home)) == before, "新实例竟能结算上一实例的挂账（与结构事实矛盾）"
        assert b._pending_post_measure is None
        assert a._pending_post_measure is not None, "旧实例挂账未被触碰（生产上该实例已析构 ⇒ 该账永久丢失）"


# ── C · 跨进程（真·杀进程重起）──────────────────────────────────────────────

class TestProcessRestart:
    def test_pending_does_not_survive_process_exit(self, tmp_path):
        """子进程①挂账后**退出**（真进程边界，非 mock）；子进程②尝试结算 ⇒ 台账不增。"""
        home = tmp_path / "h"
        (home / "data").mkdir(parents=True, exist_ok=True)
        r1 = _run_probe("arm", home)
        assert r1.returncode == 0 and "ARMED" in r1.stdout, r1.stderr[-400:]
        r2 = _run_probe("settle", home)
        assert r2.returncode == 0, r2.stderr[-400:]
        assert _posts(home) == [], (
            "跨进程竟结算成功 ⇒ 要么挂账已持久化（则本臂应改写为新契约），"
            "要么结算读到了不该读的状态"
        )

    def test_pending_is_in_memory_only(self, tmp_path):
        """同进程内 arm 后立即同进程 settle ⇒ 有行；据此与上一臂对比，坐实「仅内存」。"""
        home = tmp_path / "h"
        (home / "data").mkdir(parents=True, exist_ok=True)
        r = _run_probe("arm_and_settle", home)
        assert r.returncode == 0 and "DONE" in r.stdout, r.stderr[-400:]
        posts = _posts(home)
        assert len(posts) == 1
        assert posts[0]["settle_reason"] == "settled"
        assert posts[0]["pending_age_s"] is not None


# ── D · 已落 post 行的持久性（「post 仍存」的成立面）───────────────────────

class TestSettledRecordsPersist:
    def test_written_post_line_survives_process_boundary(self, tmp_path):
        """**已结算**的 post_measure 行确实跨进程仍存（文件即真源）——
        与 C 臂合读：**已落的行持久，未结算的挂账不持久**（两者不可混为一谈）。"""
        home = tmp_path / "h"
        (home / "data").mkdir(parents=True, exist_ok=True)
        r = _run_probe("arm_and_settle", home)
        assert r.returncode == 0, r.stderr[-400:]
        p = home / "data" / "compression_quality.jsonl"
        assert p.exists(), "已结算行未落盘"
        rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        got = [x for x in rows if x.get("kind") == "post_measure"]
        assert len(got) == 1
        assert got[0]["post_actual_prompt_tokens"] == 49_326
        # 新起一个进程**只读**该文件（证「跨进程可读」而非依赖内存）
        r2 = subprocess.run(
            [sys.executable, "-c",
             "import json,sys;rows=[json.loads(l) for l in open(sys.argv[1]) if l.strip()];"
             "print(sum(1 for r in rows if r.get('kind')=='post_measure'))",
             str(p)], capture_output=True, text=True, timeout=120)
        assert r2.stdout.strip() == "1"


# ── E · 结构闸：本文件赖以成立的两条结构事实必须仍成立 ─────────────────────

class TestStructuralFactsStillHold:
    def test_api_server_creates_agent_inside_run(self):
        """`_create_agent` 必须在 `_run()` **体内**（⇒ 每 run 新实例）。一旦被改成
        复用 agent，B/C 臂的结论即失效 —— 那时应改写本文件而不是让它悄悄绿着。"""
        src = (REPO / "gateway" / "platforms" / "api_server.py").read_text(encoding="utf-8")
        seg = src.split("async def _run_agent", 1)[1].split("async def ", 1)[0]
        assert "self._create_agent(" in seg.split("loop.run_in_executor", 1)[0]

    def test_pending_state_is_instance_field(self):
        """挂账若被改成类级/模块级（即已持久化），C 臂语义变化 ⇒ 本闸报警。"""
        src = (REPO / "agent" / "context_compressor.py").read_text(encoding="utf-8")
        assert "self._pending_post_measure = None" in src, "挂账初始化不再是实例字段"
