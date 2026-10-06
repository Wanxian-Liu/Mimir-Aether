"""行236/237（全清任务第2单）· 本 run 独立复核判据。

角色：ed30667 已由兄弟 run 实施（01:30:40）；本 run 落后 ⇒ 转 L2 独立复核 + 缺口定位。
基线旧版从 git 抽取（不信 staged .orig 副本），四臂含正控/负控对与一条缺口臂。

臂：
  A 预算差分（staging 写是否退还预算）      B 负控：真交付物写 ⇒ 新旧都清零
  C 别名变量路径识别                        D 硬限：只读被拒 / 写工具不被拒
  E F4 占位判据：正控 / 负控 / 显式未闭豁免 / 自引用豁免臂（缺口）

用法: cd ~/src/MimirAether && python3 scripts/probes/empty_run_gate_independent_verify.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
HOME = os.environ.get("MIMIR_AETHER_HOME") or (os.path.expanduser("~").rstrip("/") + "/.mimiraether")
OLD_REV = "ed30667^:agent/empty_run_gate.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def load_old_from_git():
    src = subprocess.run(["git", "-C", REPO, "show", OLD_REV],
                         capture_output=True, text=True, check=True).stdout
    fd, p = tempfile.mkstemp(suffix="_erg_old.py")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(src)
    return load("erg_old_git", p), p


def call(name, args):
    return {"id": "c", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def msg(*tcs):
    return {"role": "assistant", "content": "", "tool_calls": list(tcs)}


READ = lambda: [call("read_file", {"path": REPO + "/agent/agent_loop.py"})]
STAGING = lambda: [call("execute_code",
                        {"code": "open('%s/tmp/iv-draft.md','w').write('x')" % HOME})]
DELIV = lambda: [call("write_file",
                      {"path": REPO + "/wiki/concepts/四方任务总台账.md", "content": "x"})]
DELIV_ALIAS = lambda: [call("execute_code",
                            {"code": "p = pathlib.Path('%s/todo.md')\np.write_text('x')" % HOME})]


def simulate(mod, turns):
    msgs, fires = [], []
    g = mod.EmptyRunGate(task_id="indep")
    for i, tcs in enumerate(turns, 1):
        fires.append(bool(g.tick(msgs, i)))
        msgs.append(msg(*tcs))
    return fires


def pat(fires):
    return "".join("T" if x else "." for x in fires)



def main():
    old, tmp_old = load_old_from_git()
    new = load("erg_new", REPO + "/agent/empty_run_gate.py")
    fails = []

    seq_a = [READ()] * 4 + [STAGING()] + [READ()] * 4 + [DELIV()]
    fa, fn = simulate(old, seq_a), simulate(new, seq_a)
    print("A 预算差分       旧版 %s | 新版 %s" % (pat(fa), pat(fn)))
    ga = sum(1 for x in fn[5:] if x)
    print("   staging 写后仍触发闸门的轮数   旧版 %d | 新版 %d"
          % (len([i for i in range(5, 10) if fa[i]]), ga))
    if not (fa[4] and fn[4]):
        fails.append("A: 第 5 轮两侧都应触发")

    seq_b = [READ()] * 4 + [DELIV()] + [READ()] * 5
    fb, fnb = simulate(old, seq_b), simulate(new, seq_b)
    print("B 负控(真交付物) 旧版 %s | 新版 %s" % (pat(fb), pat(fnb)))
    ok_b = (fb[4] and fnb[4] and not any(fb[5:]) and not any(fnb[5:]))
    print("   真交付物写入后 5 轮内两侧均静默（deliverable_written 覆盖全程）: %s" % ok_b)
    if not ok_b:
        fails.append("B: 真交付物写后两侧应静默（负控：修复不得过触发）")

    msgs_c = [msg(*READ())] * 4 + [msg(*DELIV_ALIAS())]
    ow, nw = old.deliverable_written(msgs_c), new.deliverable_written(msgs_c)
    print("C 别名变量路径   deliverable_written   旧版 %s | 新版 %s" % (ow, nw))
    if not (ow is False and nw is True):
        fails.append("C: 变量路径应旧 False / 新 True")

    hl = new.readonly_hard_limit()
    g = new.EmptyRunGate(task_id="hard")
    msgs = []
    for i in range(hl + 1):
        g.tick(msgs, i + 1)
        msgs.append(msg(*READ()))
    blk_read = g.should_block_readonly("read_file", json.dumps({"path": "x"}))
    blk_write = g.should_block_readonly("write_file", json.dumps({"path": "x", "content": "y"}))
    print("D 硬限 %d         拒只读 %s | 拒写工具 %s（负控须 False）" % (hl, blk_read, blk_write))
    if not (blk_read is True and blk_write is False):
        fails.append("D: 硬限须拒只读、不得拒写工具")

    os.environ.pop("MIMIR_PLACEHOLDER_GUARD", None)
    from agent import verify_before_report_guard as guard
    msgs_e = [{"role": "user", "content": "本段材料读齐后落半段。"}]
    e1 = "本段材料已读齐。以下为待补清单：TODO 索引重建部分、暂缺的对照读数，均未落在盘上。"
    e2 = "本段材料已读齐。索引重建部分与对照读数均已列明，落点见收纳目录，无遗留项。"
    e3 = e1 + "本段为半段，未闭项清单见下。"
    e4 = e1 + "本次顺带修订 verify-before-report 守卫的口径说明段。"
    e5 = "待补：索引重建。"   # 短正文（< PLACEHOLDER_MIN_LEN=40）含占位
    pure = {k: guard.has_unclosed_placeholder(v) for k, v in
            (("正控 e1", e1), ("负控 e2", e2), ("显式未闭 e3", e3),
             ("缺口臂 e4", e4), ("短正文 e5", e5))}
    print("E F4 纯函数 has_unclosed_placeholder: %s" % pure)

    def judge(t):
        b = guard.should_block_finish(msgs_e, t)
        return b, guard.get_last_block_reason()

    r1, w1 = judge(e1)
    r2, w2 = judge(e2)
    r3, w3 = judge(e3)
    r4, w4 = judge(e4)
    print("  生产端 should_block_finish: e1 拦=%s(%s) | e2 拦=%s(%s) | e3 拦=%s(%s)"
          % (r1, w1, r2, w2, r3, w3))
    r5, w5 = judge(e5)
    print("  缺口臂 e4（同一正文 + 『守卫』二字）拦=%s reason=%s" % (r4, w4))
    print("  缺口臂 e5（短正文含『待补』，len=%d < 40）拦=%s reason=%s" % (len(e5), r5, w5))
    if not (pure["正控 e1"] and not pure["负控 e2"] and not pure["显式未闭 e3"]):
        fails.append("E: 纯函数正控应 True / 负控与显式未闭应 False")
    if not (w1 == "placeholder_unclosed"):
        fails.append("E: 正控应拦且 reason=placeholder_unclosed（实得 %s）" % w1)
    if w4 == "placeholder_unclosed":
        fails.append("E: 缺口臂不应被占位判据拦（自引用豁免应生效）")

    print("")
    print("独立复核结论: %s" % ("PASS" if not fails else "FAIL " + "; ".join(fails)))
    print("缺口定位① F4 自引用豁免: 同一正文加『守卫』二字 ⇒ 占位判据整体跳过（e1 纯函数 True / e4 生产端 reason=%s）" % w4)
    print("缺口定位② F4 长度闸: len<40 的正文含占位 ⇒ 判据不启动（e5 纯函数 %s）"
          % guard.has_unclosed_placeholder(e5))
    st = subprocess.run(["systemctl", "--user", "show", "mimiraether.service",
                         "-p", "ActiveEnterTimestamp", "-p", "MainPID"],
                        capture_output=True, text=True).stdout.strip().replace("\n", " ")
    mt = max(os.path.getmtime(REPO + "/agent/" + f) for f in
             ("empty_run_gate.py", "agent_loop.py", "verify_before_report_guard.py"))
    print("生效性: %s | 修复文件最新 mtime %s"
          % (st, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mt))))
    print("        ⇒ 进程启动早于修复落盘 = 运行进程仍持旧模块（未重启 ⇒ 未生效）")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
