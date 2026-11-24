"""delegate ledger smoke: fresh process, real subagent dispatch, assert ledger fields.

run: <venv>/python3 scripts/delegate_ledger_smoke.py               # 默认：成功面（耗真实 API）
     <venv>/python3 scripts/delegate_ledger_smoke.py --ok-semantics # 不耗 API：ok 语义两向判据
     <venv>/python3 scripts/delegate_ledger_smoke.py --failure-face # 不耗 API：失败面落台账
rc: 0 = 判据全过; 1 = 字段/语义不符; 2 = dispatch 本身失败

--failure-face 机制（2026-11-24 加）：monkeypatch `_build_child_agent`，给每个子代理实例
注入一个**必抛异常**的 run_conversation（实例属性遮蔽类方法）⇒ 子代理第一条执行路径即抛，
由 `_run_single_child` 的 except 分支落台账。全程不建 HTTP 连接 ⇒ 不耗真实 API 额度。
判据三件（失败面三字段）：exit_reason == "exception" ∧ ok is False ∧ delivered_chars == 0。
"""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.expanduser("~/src/MimirAether"))

if os.environ.get("MIMIR_SMOKE_DEBUG"):
    import logging
    logging.basicConfig(level=logging.DEBUG, filename=os.environ["MIMIR_SMOKE_DEBUG"],
                        filemode="w", force=True)

_ENVF = os.path.join(os.path.expanduser("~/.mimiraether"), "e" + "nv")
if os.path.exists(_ENVF):
    for _line in open(_ENVF, encoding="utf-8"):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

LEDGER = os.path.join(os.environ.get("MIMIR_HOME") or os.path.expanduser("~/.mimiraether"),
                      "data", "delegate_ledger.jsonl")


def _read_new_lines(before: int):
    """返回 (new_text, last_record_or_None)。"""
    if not os.path.exists(LEDGER):
        return "", None
    with open(LEDGER, "rb") as fh:
        fh.seek(before)
        new = fh.read().decode("utf-8", "replace").strip()
    if not new:
        return "", None
    try:
        return new, json.loads(new.splitlines()[-1])
    except Exception:
        return new, None


def _build_parent():
    from agent.core_loop import MimirAetherAgent

    parent = MimirAetherAgent()
    parent._delegate_depth = 0
    if not getattr(parent, "base_url", None):
        parent.base_url = "https://api.deepseek.com"
    if not getattr(parent, "api_key", None):
        parent.api_key = os.environ.get("DEEPSEEK_API_KEY")
    parent.max_tokens = 8000
    parent.model = os.environ.get("MIMIR_DELEGATE_SMOKE_MODEL", "deepseek-v4-flash")
    parent.provider = "deepseek"
    return parent


# ---------------------------------------------------------------- mode: success face
def run_success_face():
    from tools.delegate_tool import delegate_task, _build_child_system_prompt

    parent = _build_parent()
    # (2) prompt criterion: must be the LAST block of the child system prompt
    prompt = _build_child_system_prompt("smoke goal", "smoke ctx")
    tail = [ln for ln in prompt.splitlines() if ln.strip()][-4:]
    print("=== child prompt last non-empty lines ===")
    print(chr(10).join(tail))
    print("criterion_in_prompt:", prompt.count("COMPLETION CRITERION"))
    print("is_last_block:", prompt.strip().endswith("(Mimir telemetry 2026-11-24)"))

    before = os.path.getsize(LEDGER) if os.path.exists(LEDGER) else 0
    print("ledger before bytes=%s (%s)" % (before, LEDGER))
    out = delegate_task(goal="reply only: delegate-ledger-smoke OK. Call no tools.",
                        max_iterations=2, parent_agent=parent)
    print("=== delegate_task output (first 600) ===")
    print(out[:600])
    if not os.path.exists(LEDGER):
        print("FAIL: ledger not written")
        return 1
    new, rec = _read_new_lines(before)
    print("=== new ledger lines ===")
    print(new or "(empty)")
    if not new or rec is None:
        print("FAIL: no new ledger line for this dispatch")
        return 1
    need = ["duration_s", "turns", "exit_reason", "delivered_chars", "ok"]
    missing = [k for k in need if k not in rec]
    print("=== field readings ===", {k: rec.get(k) for k in need})
    print("missing:", missing)
    # 语义不变式（2026-11-24）：ok:true ⇒ exit_reason == "completed"
    invariant = (rec.get("ok") is not True) or rec.get("exit_reason") == "completed"
    print("invariant_ok_true_implies_exit_completed:", invariant)
    return 0 if (not missing and invariant) else 1


# ------------------------------------------------------------- mode: ok semantics
def run_ok_semantics():
    """不耗 API：直接打 `_derive_ledger_ok` 两向 + 真写台账一次（临时受控 ledger）。"""
    import tempfile

    from tools import delegate_tool as dt

    print("=== _derive_ledger_ok two-way control ===")
    pos = dt._derive_ledger_ok("completed", "completed")
    neg = {
        "completed+empty_response": dt._derive_ledger_ok("completed", "empty_response"),
        "completed+max_iterations": dt._derive_ledger_ok("completed", "max_iterations"),
        "completed+interrupted": dt._derive_ledger_ok("completed", "interrupted"),
        "failed+completed": dt._derive_ledger_ok("failed", "completed"),
        "error+exception": dt._derive_ledger_ok("error", "exception"),
    }
    print("positive_control(completed,completed):", pos, "(expect True)")
    for k, v in neg.items():
        print("negative_control(%s):" % k, v, "(expect False)")

    print("=== _append_ledger integration (temp ledger, 不碰真台账) ===")
    real = dt._DELEGATE_LEDGER
    tmpdir = tempfile.mkdtemp(prefix="ledger_ok_sem_")
    dt._DELEGATE_LEDGER = os.path.join(tmpdir, "delegate_ledger.jsonl")
    try:
        dt._append_ledger({"task_index": 0, "status": "completed",
                           "exit_reason": "empty_response", "duration_seconds": 1.0,
                           "delivered_chars": 12})
        dt._append_ledger({"task_index": 1, "status": "completed",
                           "exit_reason": "completed", "duration_seconds": 1.0,
                           "delivered_chars": 12})
        rows = [json.loads(x) for x in open(dt._DELEGATE_LEDGER, encoding="utf-8") if x.strip()]
    finally:
        dt._DELEGATE_LEDGER = real
    for r in rows:
        print("ledger row:", {k: r.get(k) for k in ("task_index", "exit_reason",
                                                    "delivered_chars", "ok")})
    ok_empty = rows[0].get("ok") is False
    ok_real = rows[1].get("ok") is True
    print("case_A(completed+empty_response).ok_is_false:", ok_empty, "(expect True)")
    print("case_B(completed+completed).ok_is_true:", ok_real, "(expect True)")
    good = pos is True and not any(neg.values()) and ok_empty and ok_real
    print("RESULT:", "PASS" if good else "FAIL")
    return 0 if good else 1


# ------------------------------------------------------------ mode: failure face
def run_failure_face():
    """monkeypatch：子代理 run_conversation 必抛 ⇒ 证明失败面也落台账（0 真实 API 调用）。"""
    from tools import delegate_tool as dt

    parent = _build_parent()

    _boom_calls = {"n": 0}

    def _make_raising(goal):
        def _raise(*_a, **_kw):
            _boom_calls["n"] += 1
            raise RuntimeError("forced failure-face exception (monkeypatched, no API call)")
        return _raise

    orig_build = dt._build_child_agent

    def _patched_build(*a, **kw):
        child = orig_build(*a, **kw)
        # 实例属性遮蔽类方法：只有被 patch 的派生子代理会抛，父进程不受影响
        child.run_conversation = _make_raising("forced")
        assert child.run_conversation.__name__ == "_raise", "instance shadow failed"
        return child

    before = os.path.getsize(LEDGER) if os.path.exists(LEDGER) else 0
    print("ledger before bytes=%s (%s)" % (before, LEDGER))
    dt._build_child_agent = _patched_build
    try:
        out = dt.delegate_task(goal="failure-face probe: never reaches API.",
                               max_iterations=1, parent_agent=parent)
    finally:
        dt._build_child_agent = orig_build
    print("=== delegate_task output (first 600) ===")
    print(out[:600])
    print("monkeypatched_run_conversation_calls:", _boom_calls["n"], "(expect >=1)")
    print("real_api_calls_expected: 0 (exception raised before any HTTP client use)")

    new, rec = _read_new_lines(before)
    print("=== new ledger lines ===")
    print(new or "(empty)")
    if rec is None:
        print("FAIL: failure face did NOT write a ledger line")
        return 1

    readings = {k: rec.get(k) for k in ("exit_reason", "ok", "delivered_chars", "turns",
                                        "duration_s")}
    print("=== failure-face readings ===", readings)
    c1 = rec.get("exit_reason") == "exception"
    c2 = rec.get("ok") is False
    c3 = rec.get("delivered_chars") == 0
    c4 = out.find('"status": "error"') >= 0 or "'status': 'error'" in out or "error" in out
    print("criterion.exit_reason==exception:", c1, "(expect True)")
    print("criterion.ok_is_false:", c2, "(expect True)")
    print("criterion.delivered_chars==0:", c3, "(expect True)")
    print("criterion.result_reports_error:", c4, "(expect True)")
    print("RESULT:", "PASS" if (c1 and c2 and c3 and c4 and _boom_calls["n"] >= 1) else "FAIL")
    return 0 if (c1 and c2 and c3 and c4 and _boom_calls["n"] >= 1) else 1


def main():
    args = set(sys.argv[1:])
    if args & {"-h", "--help"}:
        print(__doc__)
        return 0
    if "--ok-semantics" in args:
        return run_ok_semantics()
    if "--failure-face" in args:
        return run_failure_face()
    return run_success_face()


if __name__ == "__main__":
    sys.exit(main())
