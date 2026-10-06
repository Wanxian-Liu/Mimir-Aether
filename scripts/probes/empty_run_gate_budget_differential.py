#!/usr/bin/env python3
"""#12 空跑闸门 · 预算计数语义 受控差分（旧版 vs 新版）。

唯一变量 = 计数口径（readonly_streak 的清零条件）；输入轨迹逐字相同。
  旧版：命中**任意 write** 即清零 —— staging 写（tmp 草稿 / logs）退还预算。
  新版：只有**真写交付物**才清零。

用法: python3 scripts/probes/empty_run_gate_budget_differential.py
"""
import importlib.util
import json
import sys
from pathlib import Path
import os

# HOME 在 execute_code 沙箱 / systemd 下会被改写为 <real>/.mimiraether ⇒ 不能直接 expanduser
_MH = os.environ.get("MIMIR_AETHER_HOME") or (str(Path.home()) + "/.mimiraether")
_H = os.path.dirname(_MH) if os.path.basename(_MH.rstrip("/")) == ".mimiraether" else str(Path.home())

ORIG = _H + "/.mimiraether/tmp/baseline/empty_run_gate.orig.py"
NEW = _H + "/src/MimirAether/agent/empty_run_gate.py"
CARD = _H + "/wiki/discussions/2026-10-07-空跑闸门-受控差分.md"
DRAFT = _H + "/.mimiraether/tmp/diff-draft.md"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def call(name, args):
    return {"id": "c", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def msg(*tcs):
    return {"role": "assistant", "content": "", "tool_calls": list(tcs)}


READ = lambda: [call("read_file", {"path": _H + "/src/MimirAether/agent/agent_loop.py"})]
STAGING = lambda: [call("execute_code", {"code": "open('%s','w').write('x')" % DRAFT})]
DELIV = lambda: [call("write_file", {"path": CARD, "content": "x"})]
DELIV_VAR = lambda: [call("execute_code", {"code": "p = pathlib.Path('%s')\np.write_text('x')" % CARD})]


def simulate(mod, turns, gate=None):
    """逐轮回放：每轮**前**调用 tick（与 agent_loop 接线一致，turn+1）。"""
    msgs = []
    fires = []
    g = gate or mod.EmptyRunGate(task_id="diff")
    for i, tcs in enumerate(turns, 1):
        fires.append(bool(g.tick(msgs, i)))
        msgs.append(msg(*tcs))
    return fires, g


def main():
    o, n = load("erg_orig", ORIG), load("erg_new", NEW)
    turns = [READ(), READ(), READ(), READ(), STAGING()] + [READ()] * 4 + [DELIV()]

    fo, go = simulate(o, turns)
    fn, gn = simulate(n, turns)

    print("轨迹: 4x只读 -> staging 写(tmp 草稿) -> 4x只读 -> 交付物写  (共 %d 轮)" % len(turns))
    print("旧版 tick 触发: %s" % "".join("T" if x else "." for x in fo))
    print("新版 tick 触发: %s" % "".join("T" if x else "." for x in fn))
    gap_old = 0
    for x in fo[5:]:
        if x:
            break
        gap_old += 1
    gap_new = 0
    for x in fn[5:]:
        if x:
            break
        gap_new += 1
    print("staging 写后的静默轮数 -- 旧版 %d / 新版 %d" % (gap_old, gap_new))

    msgs_var = [msg(*READ())] * 4 + [msg(*DELIV_VAR())]
    print("变量路径写交付物 -- 旧版 deliverable 识别 %s / 新版 %s"
          % (o.deliverable_written(msgs_var), n.deliverable_written(msgs_var)))

    hl = n.readonly_hard_limit()
    g = n.EmptyRunGate(task_id="hard")
    simulate(n, [READ()] * (hl + 1), gate=g)
    blocked = g.should_block_readonly("read_file", json.dumps({"path": "x"}))
    print("硬限 %d -- 连续 %d 轮只读后被拒 read_file: %s" % (hl, hl + 1, blocked))

    import os
    os.environ["MIMIR_READONLY_HARD_LIMIT"] = "0"
    off = n.EmptyRunGate(task_id="off").should_block_readonly("read_file", "{}")
    print("硬限 0(关) 时不被拒: %s" % (not off))
    os.environ.pop("MIMIR_READONLY_HARD_LIMIT", None)

    ok = bool(fo[4]) and not fo[5] and bool(fn[4]) and bool(fn[5]) and gap_new == 0
    print("\n差分结论: %s" % ("PASS -- 旧版计数语义确证（staging 写退还预算）" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
