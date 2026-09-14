"""RS17 探针自证闸测试（2026-09-14）。

覆盖：
  ① 控制组语义——好探针 VERIFIED；坏探针（正控/负控失败）UNVERIFIED
  ② 五类结构性无效探针：无占位符 / 控制组相同 / 空探针 /
     空洞期望（vacuous_expectations）/ 控制组即目标（control_is_target）——后两类 T10 加固
  ③ 历史误报回归：未转义 [COMPRESS-RESULT] 正则（09-13 真实误报）
  ④ 闸门语义：无自证拦截 + UNVERIFIED 落账；有自证放行；nudge 只拦一次（反死锁）；hard 模式
  ⑤ 与 verify_before_report_guard 的接线
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import probe_attest as pa  # noqa: E402

REAL_LOG = """\
2026-09-14T15:47:12 [COMPRESS] skip layer=agent threshold=120000 current_tokens=120707
2026-09-14T15:47:12 [COMPRESS] result layer=agent msgs=215->56 mode=llm elapsed=20.42s
2026-09-14T15:58:44 [COMPRESS] result layer=agent msgs=221->66 mode=llm elapsed=18.86s
"""

FALSE_LOG = """\
2026-09-14T15:47:12 [COMPRESS] skip layer=agent threshold=120000 current_tokens=120707
"""

GOOD_PROBE = r'grep -c "\[COMPRESS\] result" {INPUT} '
BAD_PROBE_UNESCAPED = r'grep -c "[COMPRESS-RESULT]" {INPUT} '


@pytest.fixture()
def samples(tmp_path: Path):
    pos = tmp_path / "known_true.log"
    neg = tmp_path / "known_false.log"
    tgt = tmp_path / "target.log"
    pos.write_text(REAL_LOG, encoding="utf-8")
    neg.write_text(FALSE_LOG, encoding="utf-8")
    tgt.write_text(REAL_LOG, encoding="utf-8")
    return pos, neg, tgt


@pytest.fixture()
def ledger(tmp_path: Path) -> Path:
    return tmp_path / "probe_attest.jsonl"


@pytest.fixture()
def gate_on(monkeypatch):
    monkeypatch.setenv("MIMIR_PROBE_ATTEST", "1")
    monkeypatch.delenv("MIMIR_PROBE_ATTEST_MODE", raising=False)


# ── ① 控制组语义 ─────────────────────────────────────────────────────────
def test_good_probe_is_verified(samples, ledger):
    pos, neg, tgt = samples
    rec = pa.attest(claim="result 行存在", probe=GOOD_PROBE, positive=str(pos),
                    negative=str(neg), target=str(tgt), ledger=ledger)
    assert rec["verdict"] == pa.VERIFIED
    assert rec["reason"] is None
    assert rec["controls"]["positive"]["ok"] is True
    assert rec["controls"]["negative"]["ok"] is True
    assert rec["target"]["observed"] == pa.SEEN


def test_broken_probe_caught_by_positive_control(samples, ledger):
    """09-13 真实误报回归：未转义正则 → 正控失败 → UNVERIFIED。"""
    pos, neg, tgt = samples
    rec = pa.attest(claim="今日 result=0", probe=BAD_PROBE_UNESCAPED, positive=str(pos),
                    negative=str(neg), target=str(tgt), ledger=ledger)
    assert rec["verdict"] == pa.UNVERIFIED
    assert rec["reason"] == "positive_control_failed"
    assert rec["controls"]["positive"]["observed"] == pa.NONE


def test_always_true_probe_caught_by_negative_control(samples, ledger):
    pos, neg, tgt = samples
    rec = pa.attest(claim="总是成立", probe="echo 1 {INPUT}", positive=str(pos),
                    negative=str(neg), target=str(tgt), ledger=ledger)
    assert rec["verdict"] == pa.UNVERIFIED
    assert rec["reason"] == "negative_control_failed"


# ── ② 结构性无效 ─────────────────────────────────────────────────────────
def test_probe_without_placeholder_rejected(samples, ledger):
    pos, neg, _ = samples
    rec = pa.attest(claim="c", probe="echo hello", positive=str(pos),
                    negative=str(neg), ledger=ledger)
    assert rec["verdict"] == pa.UNVERIFIED
    assert rec["reason"] == "no_input_placeholder"


def test_identical_controls_rejected(samples, ledger):
    pos, _, _ = samples
    rec = pa.attest(claim="c", probe=GOOD_PROBE, positive=str(pos),
                    negative=str(pos), ledger=ledger)
    assert rec["verdict"] == pa.UNVERIFIED
    assert rec["reason"] == "controls_identical"


def test_vacuous_expectations_rejected(samples, ledger):
    """T10-①：两控制组期望同一观测值 -> 死探针也通过（空洞控制组）。

    取证：2026-09-14 实测 true {INPUT} + 两边 expect=none 曾被判 VERIFIED。
    """
    pos, neg, tgt = samples
    rec = pa.attest(claim="死探针", probe="true {INPUT}", positive=str(pos),
                    negative=str(neg), target=str(tgt),
                    expect_positive=pa.NONE, expect_negative=pa.NONE, ledger=ledger)
    assert rec["verdict"] == pa.UNVERIFIED
    assert rec["reason"] == "vacuous_expectations"


def test_control_is_target_rejected(samples, ledger):
    """T10-②：目标样本兼作控制样本 -> 同义反复。

    已知边界：仅样本字符串相同时可判；内容同而路径不同不可检测（残余风险）。
    """
    pos, neg, _ = samples
    rec = pa.attest(claim="同义反复", probe=GOOD_PROBE, positive=str(pos),
                    negative=str(neg), target=str(pos), ledger=ledger)
    assert rec["verdict"] == pa.UNVERIFIED
    assert rec["reason"] == "control_is_target"


def test_target_reuses_negative_sample_rejected(samples, ledger):
    """T10-③：目标 = 负控样本 -> 目标未经独立测量（单独 reason 便于审计）。"""
    pos, neg, _ = samples
    rec = pa.attest(claim="复用负控", probe=GOOD_PROBE, positive=str(pos),
                    negative=str(neg), target=str(neg), ledger=ledger)
    assert rec["verdict"] == pa.UNVERIFIED
    assert rec["reason"] == "target_reuses_negative"


def test_nudge_states_output_contract():
    """T9：契约必须明示——0/1 计数，字面量 none 会被读成 seen。"""
    txt = pa.build_nudge()
    assert "输出契约" in txt
    assert "echo 1 || echo 0" in txt


def test_empty_probe_rejected(samples, ledger):
    pos, neg, _ = samples
    rec = pa.attest(claim="c", probe="   ", positive=str(pos),
                    negative=str(neg), ledger=ledger)
    assert rec["verdict"] == pa.UNVERIFIED
    assert rec["reason"] == "empty_probe"


@pytest.mark.parametrize("stdout,expected", [
    ("", pa.NONE), ("0", pa.NONE), ("0\n", pa.NONE), (" 0 ", pa.NONE),
    ("3", pa.SEEN), ("0\n0\n", pa.NONE), ("line", pa.SEEN),
])
def test_observe_caliber(stdout, expected):
    assert pa.observe(stdout) == expected


def test_ledger_is_readable_jsonl(samples, ledger):
    pos, neg, tgt = samples
    pa.attest(claim="c1", probe=GOOD_PROBE, positive=str(pos), negative=str(neg),
              target=str(tgt), ledger=ledger)
    pa.attest(claim="c2", probe=BAD_PROBE_UNESCAPED, positive=str(pos), negative=str(neg),
              target=str(tgt), ledger=ledger)
    recs = pa.read_records(ledger=ledger)
    assert [r["claim"] for r in recs] == ["c1", "c2"]
    assert [r["verdict"] for r in recs] == [pa.VERIFIED, pa.UNVERIFIED]
    for line in ledger.read_text(encoding="utf-8").splitlines():
        json.loads(line)


# ── ④ 闸门语义 ───────────────────────────────────────────────────────────
def test_find_negative_claims_dedup():
    hits = pa.find_negative_claims("未生效，为 0，缺失，从未")
    assert "未生效" in hits and "缺失" in hits
    assert len(hits) == len(set(hits))


def test_positive_text_needs_no_attestation(gate_on, ledger):
    assert pa.evaluate_turn("一切正常，压缩已生效", ledger=ledger) is None


def test_negative_claim_blocked_and_logged(gate_on, ledger):
    out = pa.evaluate_turn("今日 result=0，未生效", messages=[], ledger=ledger)
    assert out is not None and out["blocked"] is True
    recs = pa.read_records(ledger=ledger)
    assert len(recs) == 1
    assert recs[0]["verdict"] == pa.UNVERIFIED
    assert recs[0]["reason"] == "no_attestation"
    assert recs[0]["source"] == "verify_before_report_guard"


def test_nudge_only_once_anti_deadlock(gate_on, ledger):
    msgs = [{"role": "user", "content": pa.build_nudge()}]
    out = pa.evaluate_turn("未生效", messages=msgs, ledger=ledger)
    assert out is not None
    assert out["blocked"] is False


def test_hard_mode_blocks_even_after_nudge(gate_on, ledger, monkeypatch):
    monkeypatch.setenv("MIMIR_PROBE_ATTEST_MODE", "hard")
    msgs = [{"role": "user", "content": pa.build_nudge()}]
    out = pa.evaluate_turn("未生效", messages=msgs, ledger=ledger)
    assert out is not None and out["blocked"] is True


def test_mode_off_returns_none(gate_on, ledger, monkeypatch):
    monkeypatch.setenv("MIMIR_PROBE_ATTEST_MODE", "off")
    assert pa.evaluate_turn("未生效", messages=[], ledger=ledger) is None


def test_verified_attestation_releases_claim(gate_on, ledger, samples):
    pos, neg, tgt = samples
    pa.attest(claim="result 行存在", probe=GOOD_PROBE, positive=str(pos),
              negative=str(neg), target=str(tgt), ledger=ledger)
    assert pa.evaluate_turn("未生效", messages=[], ledger=ledger) is None


def test_expired_attestation_does_not_release(gate_on, ledger, samples):
    pos, neg, tgt = samples
    pa.attest(claim="c", probe=GOOD_PROBE, positive=str(pos), negative=str(neg),
              target=str(tgt), ledger=ledger, now=1000.0)
    out = pa.evaluate_turn("未生效", messages=[], ledger=ledger,
                           now=1000.0 + pa.TURN_WINDOW_SECONDS + 1)
    assert out is not None and out["blocked"] is True


def test_unverified_attestation_does_not_release(gate_on, ledger, samples):
    pos, neg, tgt = samples
    pa.attest(claim="c", probe=BAD_PROBE_UNESCAPED, positive=str(pos), negative=str(neg),
              target=str(tgt), ledger=ledger)
    out = pa.evaluate_turn("未生效", messages=[], ledger=ledger)
    assert out is not None and out["blocked"] is True


# ── ⑤ 与 verify_before_report_guard 接线 ────────────────────────────────
def test_guard_blocks_negative_claim_without_attestation(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_VERIFY_BEFORE_REPORT", "1")
    monkeypatch.setenv("MIMIR_PROBE_ATTEST", "1")
    monkeypatch.delenv("MIMIR_PROBE_ATTEST_MODE", raising=False)

    from agent.verify_before_report_guard import should_block_finish

    msgs = [
        {"role": "user", "content": "看一下今天压缩有没有生效"},
        {"role": "assistant", "tool_calls": [{"function": {"name": "terminal"}}]},
        {"role": "tool", "content": "grep 输出"},
    ]
    # 有工具调用（旧判据会放行），但声明未附自证 ⇒ RS17 必须拦
    assert should_block_finish(msgs, "今天压缩未生效，result 为 0") is True


def test_guard_passes_claim_with_verified_attestation(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_VERIFY_BEFORE_REPORT", "1")
    monkeypatch.setenv("MIMIR_PROBE_ATTEST", "1")

    ledger = tmp_path / "data" / "ops" / "probe_attest.jsonl"
    pos = tmp_path / "t.log"
    neg = tmp_path / "f.log"
    tgt = tmp_path / "target.log"   # T10：独立目标样本（原用 pos 兼作 target = 同义反复）
    pos.write_text(REAL_LOG, encoding="utf-8")
    neg.write_text(FALSE_LOG, encoding="utf-8")
    tgt.write_text(REAL_LOG, encoding="utf-8")
    pa.attest(claim="result 行存在", probe=GOOD_PROBE, positive=str(pos), negative=str(neg),
              target=str(tgt), ledger=ledger)

    from agent.verify_before_report_guard import should_block_finish

    msgs = [{"role": "user", "content": "看一下今天压缩有没有生效"}]
    assert should_block_finish(msgs, "今天压缩未生效，result 为 0") is False


def test_guard_respects_gate_off(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_VERIFY_BEFORE_REPORT", "1")
    monkeypatch.setenv("MIMIR_PROBE_ATTEST", "0")

    from agent.verify_before_report_guard import should_block_finish

    msgs = [
        {"role": "user", "content": "状态"},
        {"role": "assistant", "tool_calls": [{"function": {"name": "terminal"}}]},
    ]
    assert should_block_finish(msgs, "未生效") is False


# ── CLI ─────────────────────────────────────────────────────────────────
def test_cli_verified_exit_zero(samples, tmp_path, monkeypatch):
    pos, neg, tgt = samples
    monkeypatch.setenv("MIMIR_HOME", str(tmp_path))
    rc = pa._cli(["--claim", "c", "--probe", GOOD_PROBE, "--positive", str(pos),
                  "--negative", str(neg), "--target", str(tgt), "--json"])
    assert rc == 0


def test_cli_unverified_exit_three(samples, tmp_path, monkeypatch):
    pos, neg, tgt = samples
    monkeypatch.setenv("MIMIR_HOME", str(tmp_path))
    rc = pa._cli(["--claim", "c", "--probe", BAD_PROBE_UNESCAPED, "--positive", str(pos),
                  "--negative", str(neg), "--target", str(tgt), "--json"])
    assert rc == 3


def test_cli_list(samples, tmp_path, monkeypatch, capsys):
    pos, neg, tgt = samples
    monkeypatch.setenv("MIMIR_HOME", str(tmp_path))
    pa._cli(["--claim", "c", "--probe", GOOD_PROBE, "--positive", str(pos),
             "--negative", str(neg), "--target", str(tgt), "--json"])
    capsys.readouterr()  # 清空上一条 --json 的 stdout（否则计数翻倍）
    assert pa._cli(["--list", "5"]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 1
