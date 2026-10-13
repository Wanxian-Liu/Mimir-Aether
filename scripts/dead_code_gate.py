#!/usr/bin/env python3
"""死件闸 —— 「复用前须验证」（MimirAether · 2026-10-13 建）

为什么存在
  用户 2026-10-13：「不要变成有遗漏、有错误，就像这回死代码当成真工作」。
  事故形态：拿一个**零引用**的模块当「只差接线的活件」写进方案（L5 的 S1/S2 前提错，就是这么来的）。
  本闸把「活件三问」变成**可跑、可红**的动作，而不是靠记性。

判定语义（与 cron 退出码纪律一致）
  发现（纪念堂件被新引用 / 被当活件）⇒ **打印 + exit 0**；
  非零退出码只留给「闸自己没跑成」（仓库找不到、扫描崩了）。

三态语义（2026-10-13 修 · 治「带路径调用假放行」）
  ① 在名录           ⇒ 打印「禁止直接复用」（+ 现值复测）
  ② 不在名录·查不到件  ⇒ 「**件不存在**」（名字写错 / 已删）——**不得**读成「安全」
  ③ 不在名录·盘上有件  ⇒ 「**未登记 ⇒ 需人工确认 ≠ 安全**」——不再打印旧措辞「视为活件（本闸不拦）」
  ＋ 完整性副态：名录有登记但盘上无件 ⇒ 「件不存在（名录/盘不一致）」
  ⚠️ 三态**只改措辞与分支语义**，不改退出码（仍是发现即 exit 0）。

用法
  python3 scripts/dead_code_gate.py check <name>     # 查单件（模块名/函数名/路径/文件名，均可）
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


def norm(name):
    """输入归一化 —— 把「路径写法」与「stem 写法」并到一个键空间。

    2026-10-13 修（本闸的因）：审计方按**最自然的写法** `check agent/memory_system.py` 调用，
    旧版按字面条目查表 ⇒ 未命中 ⇒ 落 `else` ⇒ 打印「视为活件（本闸不拦）」= **假放行**。
    语义：`agent/memory_system.py` ≡ `memory_system.py` ≡ `memory_system`
      · 取 basename（去掉目录：`agent/`、`/abs/path/`、`./` 一视同仁）
      · 去末尾 `.py`（模块/文件后缀）
      · 函数名（`reset_file_dedup`、`obj.method` 取末段）不受影响 ⇒ 归一化对它恒等
    只做**形状归一**，不猜语义：归一后仍查不到 ⇒ 走「未登记」三态，**不猜成安全**。
    """
    s = str(name).strip().strip("'\"")
    s = s.rstrip("/")
    s = s.replace("\\", "/").split("/")[-1]      # basename：路径/相对路径/绝对路径同一化
    if s.endswith(".py"):
        s = s[:-3]
    return s


def on_disk(key):
    """盘上找件 —— 返回命中说明（'' = 没找到）。

    用于区分三态 ②/③：不在名录时，**盘上有件**才叫「未登记·需人工确认」；
    盘上也没有 ⇒ 「件不存在」（名字写错 / 已删）——两者都**不等于安全**。
    """
    for p in py_files():
        if p.stem == key:
            return str(p.relative_to(REPO))
    defs, _ = func_calls(key)
    if defs:
        return defs[0] + "（def 定义行）"
    return ""


def resolve(name):
    """三态解析 —— 返回 (态, 归一后键, 命中说明)。

    态取值：'module' | 'func' | 'false_dead' | 'unregistered' | 'nonexistent' | 'missing'
    这是本闸**唯一**的判定入口；`check()` / `three()` 共用它 ⇒ 两条命令同判（防两处漂移）。
    """
    key = norm(name)
    if key in MEMORIAL_MODULES:
        rel = MEMORIAL_MODULES[key]
        if not (REPO / rel).exists():
            return "missing", key, rel          # ③ 在名录但件不在盘（名录/盘上不一致）
        return "module", key, rel
    if key in MEMORIAL_FUNCS:
        return "func", key, MEMORIAL_FUNCS[key]
    if key in FALSE_DEAD:
        return "false_dead", key, FALSE_DEAD[key]
    loc = on_disk(key)
    if loc:
        return "unregistered", key, loc          # ③ 未登记（盘上有件）⇒ 需人工确认，**不等于安全**
    return "nonexistent", key, ""                # ② 查不到该件 ⇒ 件不存在


NOTE_UNREGISTERED = (
    "⚠️ **未登记**（不在纪念堂名录）⇒ **需人工确认，不等于安全**——\n"
    "       本闸只能证明「它没被登记为死件」，**不能**证明「它有人在用」。\n"
    "       要写「复用既有 X」前，仍须自己跑活件三问（下）并附读数。"
)
NOTE_NONEXISTENT = (
    "🚫 **件不存在**（名录里没有它，盘上也找不到同名文件 / 定义）——\n"
    "       名字可能写错，或该件已被删；**不得**把本行读成「安全」。"
)
NOTE_MISSING = "🚫 **件不存在**（名录里有登记、盘上却找不到该件）⇒ 名录与仓不一致，请先核对名录。"


def note_for(state, shown, loc):
    """三态措辞的唯一出口（check / three 共用，防两处漂移）。"""
    if state == "unregistered":
        return NOTE_UNREGISTERED + f"\n       （盘上找到：{loc}）"
    if state == "nonexistent":
        return NOTE_NONEXISTENT
    if state == "missing":
        return NOTE_MISSING + f"\n       （登记位置：{loc}）"
    return ""


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
    state, key, note = resolve(name)
    shown = key if key != name else name
    print(f"  ── 活件三问：{shown}")
    if state == "module":
        rel = note
        p = REPO / rel
        exists = p.exists()
        print(f"     ① 有调用者吗？ → import/from 引用点 = {len(module_refs(key))} 个")
        print(f"     ② 目标库/产物存在吗？ → 件本身 {'在盘' if exists else '不在盘'}"
              f"（{rel}{'·' + str(p.stat().st_size) + 'B' if exists else ''}）")
        print("     ③ 运行时真在用吗？ → 需人工查进程/日志（本闸不给结论）")
    elif state == "func":
        defs, calls = func_calls(key)
        print(f"     ① 有调用者吗？ → 定义 {len(defs)} 处 · 非定义命中 **{len(calls)}** 处")
        print("     ② 目标库/产物存在吗？ → 函数无独立产物（随宿主文件）")
        print("     ③ 运行时真在用吗？ → 需人工查（本闸不给结论）")
    elif state == "false_dead":
        print(f"     ⚠️ 此件**曾被误判为死**，实测有调用者：{note}")
    elif state in ("missing", "nonexistent", "unregistered"):
        print(f"     {note_for(state, shown, note)}")


def check(name):
    state, key, note = resolve(name)
    shown = key if key != name else name
    print(f"  ═══ 闸 · check {name} ═══")
    if shown != name:
        print(f"     （输入归一化：`{name}` → `{shown}`）")
    live_dead = False
    if state in ("missing", "nonexistent"):
        print(f"     {note_for(state, shown, note)}")
        three(name)
        return 0
    if state == "module":
        n = len(module_refs(key))
        live_dead = n == 0
        print(f"     🔴 **已纪念堂化**（{note}）")
        print(f"     现值复测：引用点 = {n} ⇒ {'仍为零引用（死）' if live_dead else '**已被人引用（状态变了！）**'}")
    elif state == "func":
        defs, calls = func_calls(key)
        live_dead = len(calls) == 0
        print(f"     🔴 **已纪念堂化**（{note}）")
        print(f"     现值复测：非定义命中 = {len(calls)} ⇒ {'仍为零调用（死）' if live_dead else '**已被人调用（状态变了！）**'}")
    elif state == "false_dead":
        print(f"     ✅ **不是死件**——曾被误判，实测有调用者：{note}")
        print("     ⇒ 按活件对待；若要改它，走正常的改动纪律，不适用「复用前验证」。")
        three(name)
        return 0
    else:
        print(f"     {note_for(state, shown, note)}")
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
