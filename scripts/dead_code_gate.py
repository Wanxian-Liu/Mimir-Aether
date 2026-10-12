#!/usr/bin/env python3
"""死件闸 —— 「复用前须验证」（MimirAether · 2026-10-13 建）

为什么存在
  用户 2026-10-13：「不要变成有遗漏、有错误，就像这回死代码当成真工作」。
  事故形态：拿一个**零引用**的模块当「只差接线的活件」写进方案（L5 的 S1/S2 前提错，就是这么来的）。
  本闸把「活件三问」变成**可跑、可红**的动作，而不是靠记性。

判定语义（与 cron 退出码纪律一致）
  发现（纪念堂件被新引用 / 被当活件）⇒ **打印 + exit 0**；
  非零退出码只留给「闸自己没跑成」（仓库找不到、扫描崩了）。

用法
  python3 scripts/dead_code_gate.py check <name>     # 查单件（模块名或函数名）
  python3 scripts/dead_code_gate.py scan             # 全量扫：有没有人新引用了纪念堂件
  python3 scripts/dead_code_gate.py three <name>     # 只出「活件三问」读数
"""
import sys
import re
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
SKIP = (".venv", ".worktrees", ".git", "__pycache__", "node_modules", "site-packages")

# ═══ 纪念堂名录（与 docs/死件纪念堂-20261013.md 同源；改一处必须改两处）═══
MEMORIAL_MODULES = {
    "memory_system": "agent/memory_system.py",
    "auxiliary_client_new": "agent/auxiliary_client_new.py",
    "chat_interface": "agent/chat_interface.py",
    "memory_provider": "agent/memory_provider.py",
    "session_manager": "agent/session_manager.py",
}
MEMORIAL_FUNCS = {
    "_prune_stale_seeded_entries": "agent/credential_pool.py",
    "reset_file_dedup": "tools/file_tools.py",
}
# 曾被误判为死、实测有调用者 ⇒ 明确标注「不是死件」（防后人再误杀）
FALSE_DEAD = {
    "get_monitor_min_errors_emergency": "agent/monitor.py（monitor.py:208 有调用）",
    "merge_ring_policy_into_config": "agent/decision_compressor_policy.py（decision_ring.py:142/144 有调用）",
}


SELF = "scripts/dead_code_gate.py"   # 本闸自己的登记表含函数名字面 ⇒ scan/复测必须排除它（否则恒自指）


def py_files():
    out = []
    for p in REPO.rglob("*.py"):
        s = str(p)
        if any(k in s for k in SKIP):
            continue
        if str(p.relative_to(REPO)) == SELF:
            continue
        out.append(p)
    return out


def module_refs(stem):
    """模块零引用判定 —— 返回引用点列表（剔自身文件）。"""
    pats = [
        rf"\bimport\s+{re.escape(stem)}\b",
        rf"\bfrom\s+[\w.]*\.?{re.escape(stem)}\s+import\b",
        rf"\bfrom\s+[\w.]*{re.escape(stem)}\b",
    ]
    own = MEMORIAL_MODULES.get(stem, "")
    hits = []
    for f in py_files():
        rel = str(f.relative_to(REPO))
        if rel == own:
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        for pat in pats:
            for m in re.finditer(pat, t):
                ln = t[: m.start()].count("\n") + 1
                hits.append(f"{rel}:{ln}")
    return hits


def func_calls(name):
    """函数零调用判定 —— 返回 (定义点, 非定义命中)。"""
    defs, calls = [], []
    for f in py_files():
        t = f.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(t.splitlines(), 1):
            if name not in line:
                continue
            loc = f"{f.relative_to(REPO)}:{i}"
            if re.search(rf"\b(def|class)\s+{re.escape(name)}\b", line):
                defs.append(loc)
            else:
                calls.append(loc)
    return defs, calls


def three(name):
    """活件三问读数。"""
    print(f"  ── 活件三问：{name}")
    if name in MEMORIAL_MODULES:
        rel = MEMORIAL_MODULES[name]
        p = REPO / rel
        exists = p.exists()
        print(f"     ① 有调用者吗？ → import/from 引用点 = {len(module_refs(name))} 个")
        print(f"     ② 目标库/产物存在吗？ → 件本身 {'在盘' if exists else '不在盘'}"
              f"（{rel}{'·' + str(p.stat().st_size) + 'B' if exists else ''}）")
        print("     ③ 运行时真在用吗？ → 需人工查进程/日志（本闸不给结论）")
    elif name in MEMORIAL_FUNCS:
        defs, calls = func_calls(name)
        print(f"     ① 有调用者吗？ → 定义 {len(defs)} 处 · 非定义命中 **{len(calls)}** 处")
        print(f"     ② 目标库/产物存在吗？ → 函数无独立产物（随宿主文件）")
        print("     ③ 运行时真在用吗？ → 需人工查（本闸不给结论）")
    elif name in FALSE_DEAD:
        print(f"     ⚠️ 此件**曾被误判为死**，实测有调用者：{FALSE_DEAD[name]}")
    else:
        print(f"     不在纪念堂名录里（可能本来就是活件，或名字写错）")


def check(name):
    print(f"  ═══ 闸 · check {name} ═══")
    live_dead = False
    if name in MEMORIAL_MODULES:
        n = len(module_refs(name))
        live_dead = n == 0
        print(f"     🔴 **已纪念堂化**（{MEMORIAL_MODULES[name]}）")
        print(f"     现值复测：引用点 = {n} ⇒ {'仍为零引用（死）' if live_dead else '**已被人引用（状态变了！）**'}")
    elif name in MEMORIAL_FUNCS:
        defs, calls = func_calls(name)
        live_dead = len(calls) == 0
        print(f"     🔴 **已纪念堂化**（{MEMORIAL_FUNCS[name]}）")
        print(f"     现值复测：非定义命中 = {len(calls)} ⇒ {'仍为零调用（死）' if live_dead else '**已被人调用（状态变了！）**'}")
    elif name in FALSE_DEAD:
        print(f"     ✅ **不是死件**——曾被误判，实测有调用者：{FALSE_DEAD[name]}")
        print("     ⇒ 按活件对待；若要改它，走正常的改动纪律，不适用「复用前验证」。")
        three(name)
        return 0
    else:
        print(f"     ✅ 不在纪念堂名录 ⇒ 视为活件（本闸不拦）。")
        three(name)
        return 0

    print()
    print("     🚧 **复用前须验证（活件三问）**——任一为「否/查不到」⇒ 不许写「复用」，只能写「迁入」或另起设计：")
    three(name)
    if live_dead:
        print("     ⇒ 结论：**禁止直接复用**。要用它 = 先补①②③并附读数，再动手。")
    return 0


def scan():
    print("  ═══ 闸 · scan（有没有人新引用了纪念堂件）═══")
    findings = []
    for stem in MEMORIAL_MODULES:
        hits = module_refs(stem)
        if hits:
            findings.append((f"模块 {stem}", hits))
    for fn in MEMORIAL_FUNCS:
        _, calls = func_calls(fn)
        if calls:
            findings.append((f"函数 {fn}", calls))
    if not findings:
        print(f"     ✅ 干净：{len(MEMORIAL_MODULES)} 模块 + {len(MEMORIAL_FUNCS)} 函数，全部仍是零引用/零调用。")
    else:
        print(f"     ⚠️ 发现 {len(findings)} 处新引用（**不是故障·是提醒**）：")
        for what, hits in findings:
            print(f"        · {what} ← {', '.join(hits[:5])}")
        print("     ⇒ 若属**有意复用**：请先在 docs/死件纪念堂-20261013.md 记「为什么它又活了」，再继续。")
    return 0


def main():
    if not (REPO / "agent").is_dir():
        print(f"❌ 闸没跑成：仓库路径不对（{REPO}）", file=sys.stderr)
        return 2
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 0
    cmd, rest = args[0], args[1:]
    try:
        if cmd == "check" and rest:
            return check(rest[0])
        if cmd == "scan":
            return scan()
        if cmd == "three" and rest:
            three(rest[0])
            return 0
    except Exception as e:  # noqa: BLE001 —— 闸自己坏了，必须非零
        print(f"❌ 闸没跑成：{type(e).__name__}: {e}", file=sys.stderr)
        return 2
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
