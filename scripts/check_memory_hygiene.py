"""记忆卫生闸（2026-09-27 · Mimir 定案）

背景：MEMORY.md 曾到 98%（7,815/8,000），一旦越过 80% 阈值就会触发
memory_tool._maybe_compact()，其中 Phase 2.5 会把 >1200 字符的条目按
「头 2/3 + 标记 + 尾 1/3」截断——历史上 300 字符版本已造成 45 处不可恢复丢失。

本闸把「不许接近阈值 / 不许条目过长 / 注入态不许出现截断标记」变成可复算的
退出码，而不是靠自觉。三条判据：
  R1 任一注入文件最长条目 > MAX_ENTRY_CHARS(1200)  => FAIL
  R2 任一注入文件用量 > 85% 上限                    => FAIL
  R3 任一注入文件含截断标记（表示已发生结构性丢失）  => FAIL

用法：python3 scripts/check_memory_hygiene.py [--home <MIMIR_AETHER_HOME>]
"""
import argparse
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

USAGE_LIMIT_PCT = 85.0
TRUNC_MARK = "[" + "..." + "] (truncated)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=None, help="覆盖 MIMIR_AETHER_HOME（自测用）")
    args = ap.parse_args()

    if args.home:
        os.environ["MIMIR_AETHER_HOME"] = args.home

    from tools.memory_tool import MAX_ENTRY_CHARS, get_memory_store

    store = get_memory_store()
    store.load_from_disk()

    fails = []
    for target in ("memory", "user"):
        entries = store._entries_for(target)
        cur = store._char_count(target)
        lim = store._char_limit(target)
        pct = (cur / lim * 100) if lim else 0.0
        mx = max((len(e) for e in entries), default=0)
        trunc = sum(1 for e in entries if TRUNC_MARK in e)
        print(f"[{target}] entries={len(entries)} chars={cur}/{lim} ({pct:.1f}%) "
              f"max_entry={mx} trunc_markers={trunc}")
        if mx > MAX_ENTRY_CHARS:
            fails.append(f"{target}: 最长条目 {mx} > 上限 {MAX_ENTRY_CHARS}")
        if pct > USAGE_LIMIT_PCT:
            fails.append(f"{target}: 用量 {pct:.1f}% > 阈值 {USAGE_LIMIT_PCT}%")
        if trunc:
            fails.append(f"{target}: 含截断标记 {trunc} 处（已发生结构性丢失）")

    print("VERDICT: " + ("FAIL" if fails else "PASS"))
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
