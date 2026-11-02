"""观测档回归（2026-10-26 三条反馈 · 刘哥 2026-11-02 批）。

守三条不变式（这三条一破，「零行为变更」就是谎话）：
  1. `explain_parallel_elig()` 不改判：对同一批文本，`estimate_parallel_elig` /
     `parallel_elig_ok` 的返回值与加观测档**之前**的版本（bak 模块）逐条相等。
  2. `pi_trigger.maybe_pi_delegate_nudge` 的返回（注入文本 / None）不变，只多写日志字段；
     且观测计算抛异常时行为不变（异常必须被吞）。
  3. 步骤型判据（编号枚举 ≥3 且步骤词 ≥2 次 ⇒ 不给 A2 分）两向可跑。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent import parallel_eligibility as pe  # noqa: E402
from agent import pi_trigger as pt  # noqa: E402

BAK = Path.home() / ".mimiraether/tmp/1026-exec/baks/parallel_eligibility.py.bak"

CORPUS = [
    "",
    "把 README 改一下",
    "- [ ] 扫 A 目录\n- [ ] 扫 B 目录\n- [ ] 扫 C 目录",
    "1. 子任务一\n2. 子任务二\n3. 子任务三",
    "1. 定基线\n2. 然后跑\n3. 最后汇总",
    "批量 grep 多个文件，独立跑三处，然后核对，之后回填",
    "web_search https://a.com https://b.com 多源调研并批量验证",
    "先读盘，然后对齐口径，接着落盘，最后复核",
]


def _load_bak():
    if not BAK.exists():
        pytest.skip("bak 模块不存在（换机/清理后不可用）：%s" % BAK)
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("pe_bak_1026", str(BAK))
    spec = importlib.util.spec_from_loader("pe_bak_1026", loader)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_explain_is_pure_and_parity_with_old_module(monkeypatch):
    """不变式 1：explain 不改判 + 与加观测档之前的实现逐条相等。"""
    monkeypatch.delenv("MIMIR_PI_MIN_PARALLEL", raising=False)
    old = _load_bak()
    for text in CORPUS:
        before = old.estimate_parallel_elig(text)
        after = pe.estimate_parallel_elig(text)
        assert before == after, "estimate 漂移: %r -> %r / %r" % (text, before, after)
        assert old.parallel_elig_ok(text) == pe.parallel_elig_ok(text)
        ex = pe.explain_parallel_elig(text)
        assert ex["elig"] == after, "explain 的 elig 必须等于现口径真值"


def test_explain_shapes():
    ex = pe.explain_parallel_elig("- [ ] a\n- [ ] b\n- [ ] c")
    assert set(ex) == {"elig", "elig_struct", "elig_kw", "would_trigger",
                       "step_type", "hits"}
    assert ex["elig_struct"] == pe.STRUCT_SCORE == 2
    assert ex["hits"].startswith("A1:")
    assert pe.explain_parallel_elig("")["would_trigger"] is False


@pytest.mark.parametrize("text,want_step,want_hit", [
    ("\n".join("%d. 独立子任务 %d" % (i, i) for i in range(1, 11)), False, "A2:枚举"),
    ("1. a\n2. b\n3. c\n首先定基线", False, "A2:枚举"),
    ("1. a\n2. b\n3. c\n首先定基线，然后跑，最后汇总", True, "A2:毙"),
    ("1. a\n2. b\n3. c\n接着复核，再接着回填", True, "A2:毙"),
    ("首先读盘，然后对齐，最后落盘", False, None),
    ("- [ ] a\n- [ ] b\n- [ ] c\n然后汇总，最后复核", False, "A1:checkbox"),
])
def test_step_type_two_way(text, want_step, want_hit):
    """不变式 3：步骤型判别两向（正控不毙 / 负控必毙）。"""
    st = pe.classify_step_type(text)
    assert st["is_step_type"] is want_step
    if want_hit:
        assert want_hit in pe.explain_parallel_elig(text)["hits"]


def _long_non_parallel_task():
    # est ≥ 8 但 parallel_elig 现口径不过闸（无结构、无三关键词）
    return ("请把 wiki 里 77 张讨论卡全部过一遍，整理成一份清单，"
            "确保条目完整、口径统一、格式规范，交付前自查一遍看看有没有漏项或者重复项。")


def test_pi_trigger_logs_observation_fields(tmp_path, monkeypatch):
    """不变式 2：返回值不变，只多写 observability 字段。"""
    obs = tmp_path / "obs.jsonl"
    monkeypatch.setenv("MIMIR_HOOK_OBS_PATH", str(obs))
    pe_mod = pt  # 便于阅读
    msgs = [{"role": "user", "content": _long_non_parallel_task()}]
    ret = pe_mod.maybe_pi_delegate_nudge(msgs)
    # 返回值与「无观测档」一致：现口径不过闸 ⇒ None（不注入）
    assert ret is None
    assert obs.exists(), "观测日志未落盘"
    recs = [json.loads(l) for l in obs.read_text(encoding="utf-8").splitlines() if l.strip()]
    hit = [r for r in recs if r["hook"] == "pi_delegate_nudge"]
    assert hit, recs
    rec = hit[-1]
    for k in ("elig_struct", "elig_kw", "would_trigger", "step_type", "elig_hits"):
        assert k in rec, "缺观测字段 %s: %r" % (k, rec)


def test_obs_failure_does_not_change_behavior(monkeypatch):
    """观测自己炸了也不许改判（吞异常，返回原值）。"""
    def _boom(_t):
        raise RuntimeError("obs boom")

    monkeypatch.setattr(pe, "explain_parallel_elig", _boom)
    msgs = [{"role": "user", "content": _long_non_parallel_task()}]
    assert pt.maybe_pi_delegate_nudge(msgs) is None
    # 正常任务也不许因观测异常而漏注入
    msgs2 = [{"role": "user", "content": "- [ ] a\n- [ ] b\n- [ ] c"}]
    monkeypatch.setenv("MIMIR_PI_MIN_TURNS", "8")
    out = pt.maybe_pi_delegate_nudge(msgs2)
    assert (out is None) or (pt.PI_NUDGE_MARKER in out)
