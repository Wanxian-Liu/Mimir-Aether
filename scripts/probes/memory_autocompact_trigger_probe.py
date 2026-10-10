"""L2 探针 · MEMORY.md 80% 自动压缩触发线核算（行49 第12单记忆瘦身复核用）

用途：独立复算「瘦身后是否仍高于运行时自动压缩触发线」。
口径来源（代码真源，本探针不复制口径，直接读源）：
  tools/memory_tool.py `MemoryStore._maybe_compact`: `if current < limit * 0.8: return {}`
  tools/memory_tool.py `MemoryStore.__init__`: `memory_char_limit: int = 8000`

三态（含负控/正控，防恒真）：
  A 现盘 MEMORY.md          → 若 >= 6400 ⇒ 判「仍将触发自动压缩」
  B 瘦身前备份（8000 字符）  → 必须判「触发」（正控：口径对已知样本成立）
  C 合成 6300 字符样本       → 必须判「不触发」（负控：口径不是恒真）
"""
import re
import sys

from pathlib import Path
_REPO = Path(__file__).resolve().parents[2]
SRC = str(_REPO / "tools" / "memory_tool.py")
MEM = str(Path.home() / ".mimiraether" / "memories" / "MEMORY.md")
BAK = str(Path.home() / ".mimiraether" / "memories" /
          "MEMORY.md.bak-pre-slim-20261007-043929")


def read_limit_and_ratio(src=SRC):
    txt = open(src).read()
    limit = re.search(r"memory_char_limit: int = (\d+)", txt).group(1)
    ratio = re.search(r"if current < limit \* ([0-9.]+):", txt).group(1)
    return int(limit), float(ratio)


def n_chars(path):
    return len(open(path).read())


def verdict(n, limit, ratio, label):
    thr = int(limit * ratio)
    trig = n >= thr
    print("[%s] chars=%d limit=%d ratio=%s thr=%d -> %s" % (
        label, n, limit, ratio, thr, "TRIGGERS auto-compact" if trig else "no trigger"))
    return trig


def main():
    limit, ratio = read_limit_and_ratio()
    print("source: %s  limit=%d ratio=%s" % (SRC, limit, ratio))
    ok = True
    a = verdict(n_chars(MEM), limit, ratio, "A 现盘 MEMORY.md")
    b = verdict(n_chars(BAK), limit, ratio, "B 正控 · 瘦身前备份")
    c = verdict(6300, limit, ratio, "C 负控 · 合成 6300")
    if not b:
        print("POSITIVE CONTROL FAILED: 8000 字符样本未判触发 => 探针口径错"); ok = False
    if c:
        print("NEGATIVE CONTROL FAILED: 6300 字符样本被误判触发 => 口径恒真"); ok = False
    print("VERDICT: %s" % ("口径成立（正控/负控双通过）" if ok else "探针不可引用"))
    print("RESULT: A_triggers=%s (True => 现盘仍高于 6400 触发线)" % a)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
