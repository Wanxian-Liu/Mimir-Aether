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

import hashlib
import json
import os
import re
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


def _resolve_ledger_home() -> Path:
    """解析 Mimir home（修 2026-09-16 台账分叉）。

    本机 HOME=$MIMIR_AETHER_HOME（mimir home 即 HOME）⇒ 旧式 expanduser("~/.mimiraether")
    得到 …/.mimiraether/.mimiraether（嵌套假路径）⇒ 自证落进嵌套台账而闸门读真台账
    ⇒「写了但看不见」的确定性重试环。

    优先级：显式 env（带 data/ 存在性校验）> get_mimir_home() > HOME 自身即 mimir home > 旧式回退。
    """
    # ① 显式 env 一律信任（含测试夹具 tmp_path；不加存在性校验，否则会越过夹具读到真台账）
    for key in ("MIMIR_HOME", "MIMIR_AETHER_HOME"):
        v = os.environ.get(key)
        if v and v.strip():
            return Path(v.strip())
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from mimir_constants import get_mimir_home  # type: ignore

        p = Path(get_mimir_home())
        if (p / "data").is_dir():
            return p
    except Exception:
        pass
    if (Path.home() / "data" / "ops").is_dir():
        return Path.home()
    return Path.home() / ".mimiraether"


def default_ledger_path() -> Path:
    return _resolve_ledger_home() / "data" / "ops" / "probe_attest.jsonl"


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


# ── T23（2026-09-14）：探针自己没产出测量时，不得被读成"确认不存在" ──────
# 已实测的洞：`--target` 整仓 rglob 撞 20s 超时，rc=-9 **被记进台账却不参与
# 判定**，空 stdout 经 observe("")→none 被读成"目标不存在" ⇒ VERIFIED。
# 即：rc 记录了、没裁决，等于没记。此判定把"探针死亡"与"观测为 none"分开。
# 注意 rc=1（grep 无匹配）是**有效观测**，不得算死亡；rc=2 是用法/读取错误。
_PROBE_DEATH_RC = {
    -9: "timeout",
    -1: "oserror",
    2: "usage_or_read_error",
    126: "not_executable",
    127: "command_not_found",
    137: "killed_sigkill",
}


def _has_contract_token(stdout: str) -> bool:
    """stdout 是否含可用观测（契约：0 或空 = none；其余 = seen）。"""
    return bool((stdout or "").strip())


def _sample_fingerprint(sample: Optional[str]) -> Optional[str]:
    """样本**内容**指纹（A3）：路径不同但内容相同 ⇒ 控制组无鉴别力。

    目录 / 不存在 / 读不动 ⇒ 返回 None（无法按内容比对，退回路径比对）。
    """
    if not sample:
        return None
    try:
        p = Path(sample)
        if not p.is_file():
            return None
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _probe_death_reason(rc: Any, stdout: str) -> Optional[str]:
    """返回死亡原因（None = 探针确实跑出了结果）。

    死亡 ⇒ 该次观测**不可用**（既不算 seen 也不算 none），据此禁止 VERIFIED。
    """
    if rc is None:
        return None
    try:
        _rc = int(rc)
    except (TypeError, ValueError):
        return None
    if _rc == 0:
        return None
    if _rc in _PROBE_DEATH_RC:
        return "%s(rc=%d)" % (_PROBE_DEATH_RC[_rc], _rc)
    if _rc < 0:
        return "signal(%d)" % (-_rc)
    # ── A3-3（2026-09-15）：未知**正数** rc 曾是后门 ─────────────────────
    # 修前：rc=3/4/8… 一律 `return None`（不算死）⇒ 空 stdout 经 observe("")→none
    # 被读成"目标不存在" ⇒ 打嗝的探针 = 确认不存在（T23 同族、未覆盖的第二类）。
    # 修后：rc=1 视为合法（grep 无匹配 = 有效观测）；其余未知正数 rc **当且仅当
    #       stdout 无可用观测**时判死（不冤枉会打印契约 token 的探针）。
    if _rc != 1 and not _has_contract_token(stdout):
        return "unexpected_rc(rc=%d)" % _rc
    return None


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
            return {"input": None, "cmd": None, "stdout": "", "rc": None,
                    "death": None, "observed": None}
        if INPUT_PLACEHOLDER in probe:
            cmd = probe.replace(INPUT_PLACEHOLDER, sample)
        else:
            cmd = "%s %s" % (probe, sample)
        r = run(cmd, timeout, cwd)
        _rc = r.get("rc")
        return {"input": sample, "cmd": cmd, "stdout": (r.get("stdout") or "")[:300],
                "rc": _rc,
                "death": _probe_death_reason(_rc, r.get("stdout") or ""),
                "observed": observe(r.get("stdout") or "")}

    _fp_pos = _sample_fingerprint(positive)
    _fp_neg = _sample_fingerprint(negative)
    _fp_tgt = _sample_fingerprint(target)

    pos = _one(positive)
    neg = _one(negative)
    tgt = _one(target) if target is not None else {
        "input": None, "cmd": None, "stdout": "", "rc": None,
        "death": None, "observed": None}

    reason: Optional[str] = None
    # ── 裁决优先级（D4 定死，2026-09-14）───────────────────────────────
    # 顺序按**证据强度**排：控制组判定"探针有没有鉴别力"，逻辑上先于任何目标结论。
    # ① 结构无效 → ② 目标复用控制组 → ③ 正控不一致 → ④ 负控不一致
    # → ⑤ 控制组死亡但观测巧合一致 → ⑥ 目标死亡 → ⑦ 目标不一致 → VERIFIED。
    # 死因信息不丢：仍在 controls.{positive,negative}.death 与 probe_health.* 里。
    if not (probe or "").strip():
        reason = "empty_probe"
    elif INPUT_PLACEHOLDER not in probe and target is None:
        reason = "no_input_placeholder"
    elif positive == negative:
        reason = "controls_identical"
    elif _fp_pos is not None and _fp_pos == _fp_neg:
        # A3-1：**内容**同、路径异 —— 修前只比路径字符串 ⇒ 控制组其实无鉴别力
        # （两个内容一模一样的样本）却照样判 VERIFIED。
        reason = "controls_identical_content"
    elif expect_positive == expect_negative:
        # 两个控制组期待同一个观测值 => 无论探针死活都能通过（空洞控制组）
        reason = "vacuous_expectations"
    elif target is not None and target == positive:
        # 目标 = 正控样本 => 用被测对象自证被测对象（同义反复）
        reason = "control_is_target"
    elif target is not None and target == negative:
        # 目标 = 负控样本 => 目标未经独立测量（与上者区分，便于审计）
        reason = "target_reuses_negative"
    elif _fp_tgt is not None and _fp_tgt == _fp_neg:
        # A3-1 同族：目标与负控**内容**相同（路径异）⇒ 目标未经独立测量
        reason = "target_reuses_negative_content"
    elif pos["observed"] != expect_positive:
        # D4 定死：控制组不一致优先于目标死亡 —— 探针有鉴别力是任何目标结论的
        # **前提**；正控已坏时目标是死是活都不可读，先报探针坏才指向真根因。
        # （all-probes-dead 场景下两者都成立，回归锚点要求报本条：
        #   tests/agent/test_probe_attest.py:80 broken-probe => positive_control_failed）
        reason = "positive_control_failed"
    elif neg["observed"] != expect_negative:
        reason = "negative_control_failed"
    elif pos.get("death"):
        # 观测巧合与期望一致，但探针确实死了（rc=2/-9/127…）⇒ 仍不得 VERIFIED
        reason = "positive_probe_dead(%s)" % pos["death"]
    elif neg.get("death"):
        reason = "negative_probe_dead(%s)" % neg["death"]
    elif tgt.get("death"):
        # T23 核心：目标探针死亡（超时/被杀/用法错误）⇒ stdout 空 ⇒ observe→none
        # 恰好等于 expect_negative ⇒ **修前判 VERIFIED**（空前洞）。
        reason = "target_probe_dead(%s)" % tgt["death"]

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
        "probe_health": {
            "positive": pos.get("death") or "ok",
            "negative": neg.get("death") or "ok",
            "target": tgt.get("death") or "ok",
            "any_death": bool(tgt.get("death") or pos.get("death") or neg.get("death")),
        },
        "duration_s": round(time.time() - t0, 3),
    }
    if write:
        rec["ledger"] = str(append_record(rec, ledger=ledger))
    return rec


_CODE_FENCE_RE = re.compile(r"```.*?```", re.S)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

# 建设性/完成性声明（与否定性声明对称，用于判定**结论极性**）
ASSERTIVE_CLAIM_PATTERNS: tuple = (
    "已完成", "已修复", "已通过", "已推送", "已落盘", "已提交", "已接入",
    "已生效", "已清零", "已闭环", "已收口", "全绿", "已验证", "修好了", "搞定了",
)


# ── A1（2026-09-15）：assertive 类声明的执法开关与"本轮写盘证据" ──────────
# 证据工具集合与汇报闸 agent/verify_before_report_guard.WRITE_TOOLS **同集合**，
# 避免两闸口径分叉（口径分叉本身就是历史事故源）。
# execute_code / terminal **刻意不计**：见 A2（Q9 裁决 = 改用"盘上增量"判据）。
WRITE_EVIDENCE_TOOLS: frozenset = frozenset({"write_file", "patch", "apply_patch", "edit"})
ASSERTIVE_ENFORCE_ENV = "MIMIR_PROBE_ATTEST_ASSERTIVE"


def assert_claims_enforced() -> bool:
    """默认开；置 0 可一键退回"只分类不执法"的旧行为（可逆）。"""
    return os.environ.get(ASSERTIVE_ENFORCE_ENV, "1") == "1"


def _turn_write_evidence(messages: Optional[Sequence[Dict[str, Any]]]) -> bool:
    """本轮（最后一条真实 user 之后）是否出现过写盘类工具调用。

    与 verify_before_report_guard._has_written_this_turn 同语义，但独立实现
    （probe_attest 可能被当脚本导入，不能反向依赖 guards 模块）。
    """
    for msg in reversed(list(messages or [])):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                try:
                    name = tc.get("function", {}).get("name", "")
                except AttributeError:
                    continue
                if name in WRITE_EVIDENCE_TOOLS:
                    return True
        if msg.get("role") == "user":
            break
    return False


def prose_view(text: str) -> str:
    """剥掉围栏代码块与行内代码——它们承载**证据**，不承载**声明**。

    背景（2026-09-14 实测 ≥4 次误拦）：扫描把 diff 里的 `- 0 次`、日志原文
    `未生效`、探针期望值字符串都当成"我的结论" ⇒ 拦的是证据，不是断言。
    """
    t = _CODE_FENCE_RE.sub(" ", text or "")
    return _INLINE_CODE_RE.sub(" ", t)


def classify_claim_polarity(text: str, *, prose_only: bool = True) -> Dict[str, Any]:
    """claim_polarity：按**结论极性**给触发面分类，而不是按句子用途。

    返回 polarity ∈ {negative, assertive, mixed, code_only, none}。
    · negative   = 散文里含否定性结论（"未生效/为 0/缺失"）⇒ 需要自证
    · assertive  = 散文里含完成性声明（"已修复/全绿"）⇒ 同样需要自证
    · code_only  = 只出现在代码块/行内代码里（已被剥掉，记为可观测信号，不拦）
    """
    raw = text or ""
    view = prose_view(raw) if prose_only else raw
    neg = find_negative_claims(view, prose_only=False)
    pos = [p for p in ASSERTIVE_CLAIM_PATTERNS if p in view]
    raw_neg = find_negative_claims(raw, prose_only=False)
    raw_pos = [p for p in ASSERTIVE_CLAIM_PATTERNS if p in raw]
    code_only = bool(not neg and not pos and (raw_neg or raw_pos))
    if neg and pos:
        pol = "mixed"
    elif neg:
        pol = "negative"
    elif pos:
        pol = "assertive"
    elif code_only:
        pol = "code_only"
    else:
        pol = "none"
    return {
        "polarity": pol,
        "negative": neg,
        "assertive": pos,
        "code_only": code_only,
        "code_only_terms": (raw_neg + raw_pos)[:8] if code_only else [],
        "scan_scope": "prose" if prose_only else "raw",
    }


def find_negative_claims(text: str, *, prose_only: bool = True) -> List[str]:
    """返回命中的声明类结论模式（去重、保序）。

    prose_only=True（默认，2026-09-14 起）：只扫散文，剥掉代码块/行内代码。
    """
    t = prose_view(text) if prose_only else (text or "")
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

    pol = classify_claim_polarity(assistant_text)
    _has_ev = _turn_write_evidence(messages)
    claims = list(pol["negative"])
    _assertive_enforced: List[str] = []
    # ── A1（2026-09-15）：claim_polarity 执法 ─────────────────────────────
    # 病：assertive（"已完成/已修复/全绿"）只被分类、只写台账，**不参与判定**
    #     ⇒「把改法已定写成已完成」这条最贵的病一直没有闸（四方卡 D7）。
    # 判据：该声明出现 **且本轮无写盘证据** ⇒ 与否定性声明同等待遇（须自证）。
    if assert_claims_enforced() and pol["assertive"] and not _has_ev:
        _assertive_enforced = list(pol["assertive"])
        claims = claims + ["[assertive] " + t for t in _assertive_enforced]
    if not claims:
        # 声明只出现在代码块里（多为我自己贴的证据）⇒ 不拦，但记观测信号
        if pol["code_only"] and record:
            _n = now if now else time.time()
            append_record({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(_n)),
                "epoch": round(_n, 3),
                "claim": "[auto-guard] 声明仅出现于代码块（未拦）：" + ", ".join(pol["code_only_terms"]),
                "probe": None, "controls": None, "target": None,
                "verdict": UNVERIFIED, "reason": "claim_in_code_block",
                "source": "verify_before_report_guard",
                "claim_polarity": pol["polarity"], "scan_scope": pol["scan_scope"],
            }, ledger=ledger)
        return None

    if verified_since(ledger=ledger, ttl=ttl, now=now):
        return None

    blocked = gate_mode() == "hard" or not already_nudged(messages)
    result = {"claims": claims, "missing": claims, "blocked": blocked,
              "mode": gate_mode(), "reason": "no_attestation",
              "claim_polarity": pol["polarity"], "scan_scope": pol["scan_scope"],
              "code_only": pol["code_only"],
              "assertive_enforced": bool(_assertive_enforced),
              "write_evidence": _has_ev}

    if record:
        _now = now if now else time.time()
        append_record({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(_now)),
            "epoch": round(_now, 3),
            "claim": "[auto-guard] 声明未附自证：" + ", ".join(claims),
            "probe": None, "controls": None, "target": None,
            "verdict": UNVERIFIED, "reason": "no_attestation",
            "source": "verify_before_report_guard",
            "claim_polarity": pol["polarity"], "scan_scope": pol["scan_scope"],
            "assertive_terms": pol["assertive"][:8], "code_only": pol["code_only"],
            "assertive_enforced": bool(_assertive_enforced),
            "write_evidence": _has_ev,
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
