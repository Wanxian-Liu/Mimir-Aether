"""B9 一周度量采集器契约测试（RS6）。

关键契约（都来自盘上真实日志格式，非臆造）：
  * `[COMPRESS] skip` 行是 `tokens=… msgs=N`（顺序）
  * `[COMPRESS] abort` 行是 `msgs=N->N … tokens=…`（**顺序相反**，且带 reason）
    → 采集器必须两种都能解析（早期版本按固定顺序写正则，实测漏掉全部 57 行 ⇒ 本测试防回归）
  * `m4`（turn-N 约束准确率）无数据源时必须返回 None + reason，**不得编造**
"""
from __future__ import annotations
import datetime
import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
DATE = datetime.date.today().isoformat()

SAMPLE = f"""\
{DATE} 10:00:00,000 INFO agent.callers_mixin: [S2-cache] prompt=100000 hit=90000 miss=10000 hit_pct=90.0% session= prefix=aaa
{DATE} 10:01:00,000 INFO agent.context_compressor: [COMPRESS-INIT] threshold_tokens=120000 source=env:MIMIR_COMPRESS_THRESHOLD_TOKENS layer=agent
{DATE} 10:02:00,000 INFO agent.context_compressor: [COMPRESS] skip layer=agent tokens=66000 threshold=120000 msgs=130 source=env:MIMIR_COMPRESS_THRESHOLD_TOKENS current_tokens=None
{DATE} 10:02:00,001 WARNING agent.context_compressor: [COMPRESS] abort layer=agent reason=noop msgs=130->130 pruned=0 tokens=66000 threshold=120000 source=env:MIMIR_COMPRESS_THRESHOLD_TOKENS elapsed=0.00s (nothing compressed)
{DATE} 10:03:00,000 INFO agent.callers_mixin: [S2-cache] prompt=200000 hit=200000 miss=0 hit_pct=100.0% session= prefix=bbb
1999-01-01 00:00:00,000 INFO agent.callers_mixin: [S2-cache] prompt=999999 hit=0 miss=999999 hit_pct=0.0% session= old
"""


def _mod():
    spec = importlib.util.spec_from_file_location("b9_metrics", REPO / "scripts" / "b9_weekly_metrics.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _snap(tmp_path):
    log = tmp_path / "agent.log"
    log.write_text(SAMPLE, encoding="utf-8")
    return _mod().collect(log)


def test_compress_states_counted(tmp_path):
    s = _snap(tmp_path)["m3_compress"]
    assert s["skip"] == 1 and s["abort"] == 1
    assert s["abort_noop"] == 1
    assert s["result"] == 0 and s["real_compressions"] == 0


def test_abort_line_field_order_parsed(tmp_path):
    """abort 行 msgs 在 tokens 之前 —— 固定顺序的正则会漏掉它。"""
    s = _snap(tmp_path)["m3_compress"]
    assert s["inner_tokens_last"] == 66000


def test_threshold_and_source(tmp_path):
    s = _snap(tmp_path)["m3_compress"]
    assert s["threshold_tokens"] == 120000
    assert s["threshold_source"] == "env:MIMIR_COMPRESS_THRESHOLD_TOKENS"
    assert s["calls_at_or_above_threshold"] == 1  # 200000 越线；100000 不越线


def test_prompt_distribution_and_old_date_excluded(tmp_path):
    s = _snap(tmp_path)["m1_prompt_tokens"]
    assert s["samples"] == 2 and s["min"] == 100000 and s["max"] == 200000
    assert s["p50"] == 100000


def test_cache_weighted_hit(tmp_path):
    s = _snap(tmp_path)["m2_cache"]
    assert s["prompt_tokens_total"] == 300000
    assert s["hit_tokens_total"] == 290000
    assert s["weighted_hit_pct"] == 96.67


def test_m4_no_source_is_null_not_fabricated(tmp_path):
    s = _snap(tmp_path)["m4_turnN_constraint_accuracy"]
    assert s["value"] is None and s["reason"]
