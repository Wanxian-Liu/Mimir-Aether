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
    """**2026-09-15 A1 口径变更**：本测试原用「压缩已生效」——而"已生效"属 assertive
    声明族，新策略下**应当被拦**（"把改法已定写成已完成"正是要治的病）。
    故改为：**无声明词**的文本才免自证；声明族（含"已生效"）见下方 A1 段。"""
    assert pa.evaluate_turn("一切正常，压缩在跑", ledger=ledger) is None


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


# ── ⑥ A1（2026-09-15）：claim_polarity **执法**（assertive 声明族）─────────
# 病：assertive（"已完成/已修复/全绿/已生效"）只被分类、只写台账，不参与判定
#     ⇒「把改法已定写成已完成」无闸（四方卡 D7）。

def _msg_with_tool(name: str):
    return [{"role": "assistant", "tool_calls": [{"function": {"name": name}}]}]


def test_a1_assertive_claim_without_evidence_blocked(gate_on, ledger):
    out = pa.evaluate_turn("批 1 已完成，全绿", messages=[], ledger=ledger)
    assert out is not None and out["blocked"] is True
    assert out["assertive_enforced"] is True
    assert any(c.startswith("[assertive]") for c in out["claims"])


def test_a1_assertive_claim_with_write_evidence_passes(gate_on, ledger):
    """本轮有 write_file 动作 ⇒ 声明有据 ⇒ 不拦（防误伤正常收尾）。"""
    out = pa.evaluate_turn("批 1 已完成，全绿", messages=_msg_with_tool("write_file"),
                           ledger=ledger)
    assert out is None


def test_a1_execute_code_is_not_write_evidence(gate_on, ledger):
    """**刻意**不算证据：与四方 Q9 裁决一致（"点名工具"判据要被"盘上增量"替换）。
    这条测试把该取舍钉死，防以后有人"顺手"把 execute_code 加进去。"""
    out = pa.evaluate_turn("已落盘", messages=_msg_with_tool("execute_code"), ledger=ledger)
    assert out is not None and out["blocked"] is True


def test_a1_enforcement_is_reversible(gate_on, ledger, monkeypatch):
    monkeypatch.setenv(pa.ASSERTIVE_ENFORCE_ENV, "0")
    assert pa.evaluate_turn("已落盘", messages=[], ledger=ledger) is None


def test_a1_assertive_released_by_verified_attestation(gate_on, ledger, samples):
    """与否定性声明共用放行机制：TTL 内有 VERIFIED 自证 ⇒ 放行。"""
    pos, neg, tgt = samples
    pa.attest(claim="c", probe=GOOD_PROBE, positive=str(pos), negative=str(neg),
              target=str(tgt), ledger=ledger)
    assert pa.evaluate_turn("已落盘，全绿", messages=[], ledger=ledger) is None


def test_a1_polarity_mixed_lists_both(gate_on, ledger):
    out = pa.evaluate_turn("已修复；但 result=0 未生效", messages=[], ledger=ledger)
    assert out is not None and out["claim_polarity"] == "mixed"


# ── ⑦ A3（2026-09-15）：探针闸残余三类 ────────────────────────────────────

def test_a3_prose_view_strips_code():
    """prose_view 此前**有实现无测试**（A3 残余②）。"""
    # 声明词**在代码里** ⇒ 剥掉；在代码外 ⇒ 保留
    assert "已完成" not in pa.prose_view("```已完成```")
    assert "已完成" not in pa.prose_view("`已完成`")
    assert "已完成" in pa.prose_view("已完成，且无代码块")
    # 围栏块内即使含声明词也被剥掉；行内代码同理
    assert pa.prose_view("```\n已完成\n```").strip() == ""


def test_a3_controls_identical_content_rejected(tmp_path, ledger):
    """路径不同、**内容**相同 —— 修前只比路径字符串 ⇒ 控制组无鉴别力却判 VERIFIED。"""
    a = tmp_path / "a.log"; b = tmp_path / "b.log"; c = tmp_path / "c.log"
    a.write_text(REAL_LOG, encoding="utf-8")
    b.write_text(REAL_LOG, encoding="utf-8")   # 与 a 内容相同、路径不同
    c.write_text(FALSE_LOG, encoding="utf-8")
    rec = pa.attest(claim="c", probe=GOOD_PROBE, positive=str(a), negative=str(b),
                    target=str(c), ledger=ledger)
    assert rec["verdict"] == pa.UNVERIFIED
    assert rec["reason"] == "controls_identical_content"


def test_a3_target_reuses_negative_content_rejected(tmp_path, ledger):
    a = tmp_path / "a.log"; b = tmp_path / "b.log"; t = tmp_path / "t.log"
    a.write_text(REAL_LOG, encoding="utf-8")
    b.write_text(FALSE_LOG, encoding="utf-8")
    t.write_text(FALSE_LOG, encoding="utf-8")   # 与负控内容相同、路径不同
    rec = pa.attest(claim="c", probe=GOOD_PROBE, positive=str(a), negative=str(b),
                    target=str(t), ledger=ledger)
    assert rec["verdict"] == pa.UNVERIFIED
    assert rec["reason"] == "target_reuses_negative_content"


@pytest.mark.parametrize("rc,stdout,dead", [
    (3, "", True),        # 未知正数 rc + 无观测 ⇒ 修前被判 none（后门）
    (3, "1\n", False),    # 有契约 token ⇒ 不冤枉
    (1, "", False),       # grep 无匹配 = 有效观测
    (0, "", False),
    (-9, "", True),       # 已知超时码
])
def test_a3_unknown_positive_rc_backdoor(rc, stdout, dead):
    r = pa._probe_death_reason(rc, stdout)
    assert bool(r) is dead, (rc, stdout, r)


def test_a3_dead_target_via_unexpected_rc_blocks_verified(ledger):
    """端到端：目标探针 rc=3 且无输出 ⇒ target_probe_dead（修前 = VERIFIED 假绿）。"""
    def _runner(cmd, timeout, cwd):
        if "SAMPLE_POS" in cmd:
            return {"rc": 0, "stdout": "1\n", "stderr": ""}
        if "SAMPLE_NEG" in cmd:
            return {"rc": 1, "stdout": "", "stderr": ""}
        return {"rc": 3, "stdout": "", "stderr": ""}
    rec = pa.attest(claim="c", probe="grep -c x {INPUT}", positive="SAMPLE_POS",
                    negative="SAMPLE_NEG", target="SAMPLE_TGT",
                    runner=_runner, ledger=ledger)
    assert rec["verdict"] == pa.UNVERIFIED
    assert rec["reason"].startswith("target_probe_dead")
    assert "unexpected_rc" in rec["reason"]
