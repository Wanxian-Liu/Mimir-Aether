"""RS17（2026-09-14）——探针自证闸（Probe Attestation Gate）。

问题（刘哥 2026-09-14 批准立项）：
    09-12 我命名了「探针未验证就下结论」，随后两天里重犯 14 次——给失败命名
    ≠ 修好失败。所有误报都出自同一步：探针失效被读成事实。

机制（而不是意志）：
    凡声明类结论（"未生效 / 为 0 / 缺失 / 从未 / not found"…），落盘前必须附一条
    控制组通过的探针自证。自证 = 同一探针在已知为真的样本上必须报"见到"、
    在已知为假的样本上必须报"没见到"。跑不通过 ⇒ 探针本身失效 ⇒ 结论标 UNVERIFIED。
    缺自证 ⇒ 结论自动标 UNVERIFIED，不许当事实用。

    关键：它检验的是探针的鉴别力，而不是探针的结论。
    例：09-13 我用未转义的 [COMPRESS-RESULT] 当正则跑出 result=0——该探针在
    已知含真结果行的样本上同样返回 0 ⇒ 正控失败 ⇒ 当场被判 UNVERIFIED。

台账：~/.mimiraether/data/ops/probe_attest.jsonl（append-only，四方可审计）
闸门：agent/verify_before_report_guard.py（内联触发 + 自动 UNVERIFIED 落账）

环境变量：
    MIMIR_PROBE_ATTEST       = 1|0   闸门总开关（默认 1）
    MIMIR_PROBE_ATTEST_MODE  = off|nudge|hard   默认 nudge（拦一次并要求自证）
    MIMIR_PROBE_ATTEST_TTL   = 秒    自证有效窗口（默认 900）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

TURN_WINDOW_SECONDS = 900
INPUT_PLACEHOLDER = "{INPUT}"

NEGATIVE_CLAIM_PATTERNS: tuple[str, ...] = (
    "未生效", "没生效", "没有生效", "未装载", "未加载", "未安装", "未记录",
    "为 0", "为0", "= 0", "=0", "0 次", "0次", "零次", "从未", "全 0", "全0",
    "缺失", "不存在", "未找到", "没有找到", "无记录", "没有记录", "查无",
    "not found", "no such", "absent",
)

SEEN = "seen"
NONE = "none"
VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"
NUDGE_MARKER = "[BLOCKED:probe-attest]"


def gate_enabled() -> bool:
    return os.environ.get("MIMIR_PROBE_ATTEST", "1") == "1"


def gate_mode() -> str:
    m = (os.environ.get("MIMIR_PROBE_ATTEST_MODE", "nudge") or "").strip().lower()
    return m if m in {"off", "nudge", "hard"} else "nudge"


def gate_ttl() -> int:
    try:
        return int(os.environ.get("MIMIR_PROBE_ATTEST_TTL", str(TURN_WINDOW_SECONDS)))
    except ValueError:
        return TURN_WINDOW_SECONDS


def default_ledger_path() -> Path:
    home = os.environ.get("MIMIR_HOME") or os.path.expanduser("~/.mimiraether")
    return Path(home) / "data" / "ops" / "probe_attest.jsonl"


def append_record(record: Dict[str, Any], *, ledger: Optional[Path] = None) -> Path:
    p = Path(ledger) if ledger else default_ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p


def read_records(*, ledger: Optional[Path] = None, limit: int = 300) -> List[Dict[str, Any]]:
    p = Path(ledger) if ledger else default_ledger_path()
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out[-limit:]


def observe(stdout: str) -> str:
    """把探针 stdout 归一为 seen / none（grep -c 的单个 0 视为"没见到"）。"""
    s = (stdout or "").strip()
    if not s:
        return NONE
    if all(ch in "0 \t\r\n" for ch in s):
        return NONE
    return SEEN


def _run_shell(cmd: str, timeout: int, cwd: Optional[str]) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        return {"rc": proc.returncode, "stdout": proc.stdout or "",
                "stderr": (proc.stderr or "")[:400]}
    except subprocess.TimeoutExpired:
        return {"rc": -9, "stdout": "", "stderr": "timeout after %ss" % timeout}
    except OSError as exc:  # pragma: no cover
        return {"rc": -1, "stdout": "", "stderr": "oserror: %s" % exc}


Runner = Callable[[str, int, Optional[str]], Dict[str, Any]]


def attest(
    *,
    claim: str,
    probe: str,
    positive: str,
    negative: str,
    target: Optional[str] = None,
    expect_positive: str = SEEN,
    expect_negative: str = NONE,
    timeout: int = 20,
    cwd: Optional[str] = None,
    runner: Optional[Runner] = None,
    ledger: Optional[Path] = None,
    write: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """跑探针三次：正控（已知为真）→ 负控（已知为假）→ 目标（真实样本）。

    只有两个控制组都符合预期，目标运行才被允许标 VERIFIED；
    否则整条记录标 UNVERIFIED，reason 指出哪一组控制失败。
    """
    run = runner or _run_shell
    t0 = time.time()

    def _one(sample: Optional[str]) -> Dict[str, Any]:
        if sample is None:
            return {"input": None, "cmd": None, "stdout": "", "rc": None, "observed": None}
        if INPUT_PLACEHOLDER in probe:
            cmd = probe.replace(INPUT_PLACEHOLDER, sample)
        else:
            cmd = "%s %s" % (probe, sample)
        r = run(cmd, timeout, cwd)
        return {"input": sample, "cmd": cmd, "stdout": (r.get("stdout") or "")[:300],
                "rc": r.get("rc"), "observed": observe(r.get("stdout") or "")}

    pos = _one(positive)
    neg = _one(negative)
    tgt = _one(target) if target is not None else {
        "input": None, "cmd": None, "stdout": "", "rc": None, "observed": None}

    reason: Optional[str] = None
    if not (probe or "").strip():
        reason = "empty_probe"
    elif INPUT_PLACEHOLDER not in probe and target is None:
        reason = "no_input_placeholder"
    elif positive == negative:
        reason = "controls_identical"
    elif expect_positive == expect_negative:
        # 两个控制组期待同一个观测值 => 无论探针死活都能通过（空洞控制组）
        reason = "vacuous_expectations"
    elif target is not None and target == positive:
        # 目标 = 正控样本 => 用被测对象自证被测对象（同义反复）
        reason = "control_is_target"
    elif target is not None and target == negative:
        # 目标 = 负控样本 => 目标未经独立测量（与上者区分，便于审计）
        reason = "target_reuses_negative"
    elif pos["observed"] != expect_positive:
        reason = "positive_control_failed"
    elif neg["observed"] != expect_negative:
        reason = "negative_control_failed"

    verdict = VERIFIED if reason is None else UNVERIFIED
    _now = now if now else time.time()
    rec: Dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(_now)),
        "epoch": round(_now, 3),
        "claim": claim,
        "probe": probe,
        "controls": {
            "positive": {**pos, "expect": expect_positive, "ok": pos["observed"] == expect_positive},
            "negative": {**neg, "expect": expect_negative, "ok": neg["observed"] == expect_negative},
        },
        "target": tgt,
        "verdict": verdict,
        "reason": reason,
        "source": "probe_attest",
        "duration_s": round(time.time() - t0, 3),
    }
    if write:
        rec["ledger"] = str(append_record(rec, ledger=ledger))
    return rec


def find_negative_claims(text: str) -> List[str]:
    """返回命中的声明类结论模式（去重、保序）。"""
    t = text or ""
    hits: List[str] = []
    for pat in NEGATIVE_CLAIM_PATTERNS:
        if pat in t and pat not in hits:
            hits.append(pat)
    return hits


def verified_since(*, ledger: Optional[Path] = None, ttl: Optional[int] = None,
                   now: Optional[float] = None) -> List[Dict[str, Any]]:
    _now = now if now else time.time()
    _ttl = TURN_WINDOW_SECONDS if ttl is None else ttl
    return [r for r in read_records(ledger=ledger)
            if r.get("verdict") == VERIFIED and (_now - float(r.get("epoch") or 0)) <= _ttl]


def already_nudged(messages: Optional[Sequence[Dict[str, Any]]]) -> bool:
    """反死锁：本轮已注入过 probe-attest 提示 ⇒ 不再拦第二次。"""
    for msg in messages or []:
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            if NUDGE_MARKER in msg["content"]:
                return True
    return False


def evaluate_turn(assistant_text: str, *, messages=None, ledger: Optional[Path] = None,
                  ttl: Optional[int] = None, now: Optional[float] = None,
                  record: bool = True) -> Optional[Dict[str, Any]]:
    """闸门判定。返回 None = 无需干预；否则给出 claims / 是否拦截。"""
    if not gate_enabled() or gate_mode() == "off":
        return None

    claims = find_negative_claims(assistant_text)
    if not claims:
        return None

    if verified_since(ledger=ledger, ttl=ttl, now=now):
        return None

    blocked = gate_mode() == "hard" or not already_nudged(messages)
    result = {"claims": claims, "missing": claims, "blocked": blocked,
              "mode": gate_mode(), "reason": "no_attestation"}

    if record:
        _now = now if now else time.time()
        append_record({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(_now)),
            "epoch": round(_now, 3),
            "claim": "[auto-guard] 声明未附自证：" + ", ".join(claims),
            "probe": None, "controls": None, "target": None,
            "verdict": UNVERIFIED, "reason": "no_attestation",
            "source": "verify_before_report_guard",
            "preview": (assistant_text or "")[:300],
        }, ledger=ledger)
    return result


def build_nudge() -> str:
    return (
        NUDGE_MARKER + " 你的回复含有声明类结论（未生效/为 0/缺失/从未…），但没有附"
        "控制组通过的探针自证。请先跑一条自证，再重新输出结论：\n"
        "python3 -m agent.probe_attest --claim '<结论>' "
        "--probe '<探针命令，用 {INPUT} 占位>' --positive <已知为真的样本> "
        "--negative <已知为假的样本> --target <真实样本>\n"
        "两个控制组必须分别报 seen / none；否则探针无鉴别力，结论只能标 UNVERIFIED。\n"
        "【输出契约】探针 stdout 必须是 0/1 或 grep -c 的计数：0 或空 = none，其余 = seen。\n"
        "  反例：test -e {INPUT} && echo seen || echo none —— 字面量 none 被读成 seen，负控必失。\n"
        "  正例：test -e {INPUT} && echo 1 || echo 0。\n"
        "【三条硬约束】① 两控制组样本必须不同 ② 期望值必须不同（都写 none = 空洞控制组）\n"
        "  ③ 目标样本不得兼作控制样本（同义反复 -> control_is_target）。"
    )


def _cli(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="probe_attest", description="RS17 探针自证闸")
    ap.add_argument("--claim")
    ap.add_argument("--probe")
    ap.add_argument("--positive")
    ap.add_argument("--negative")
    ap.add_argument("--target", default=None)
    ap.add_argument("--expect-positive", default=SEEN, choices=[SEEN, NONE])
    ap.add_argument("--expect-negative", default=NONE, choices=[SEEN, NONE])
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--cwd", default=None)
    ap.add_argument("--list", type=int, default=0, help="打印台账末尾 N 条后退出")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        recs = read_records(limit=args.list)
        for r in recs:
            print(json.dumps(r, ensure_ascii=False))
        print("# ledger=%s records=%d" % (default_ledger_path(), len(recs)), file=sys.stderr)
        return 0

    if not (args.claim and args.probe and args.positive and args.negative):
        ap.error("需要 --claim --probe --positive --negative（或 --list N）")

    rec = attest(claim=args.claim, probe=args.probe, positive=args.positive,
                 negative=args.negative, target=args.target,
                 expect_positive=args.expect_positive, expect_negative=args.expect_negative,
                 timeout=args.timeout, cwd=args.cwd)
    if args.json:
        print(json.dumps(rec, ensure_ascii=False))
    else:
        c = rec["controls"]
        print("verdict      : %s%s" % (rec["verdict"], ("  reason=" + rec["reason"]) if rec["reason"] else ""))
        print("positive ctrl: observed=%s expect=%s ok=%s" % (c["positive"]["observed"], c["positive"]["expect"], c["positive"]["ok"]))
        print("negative ctrl: observed=%s expect=%s ok=%s" % (c["negative"]["observed"], c["negative"]["expect"], c["negative"]["ok"]))
        print("target       : observed=%s stdout=%r" % (rec["target"]["observed"], rec["target"]["stdout"]))
        print("ledger       : %s" % rec.get("ledger"))
    return 0 if rec["verdict"] == VERIFIED else 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
