#!/usr/bin/env python3
"""E4 · IQ 复评「现在能不能跑」只读探针（**不跑复评**）。

判据（派单件）：
  1) swap free >= 1 GB
  2) load average(1m) < 2
  3) 无其他 pytest / 索引进程（bge-m3 / bge-reranker / chroma indexer）

输出：单行 `READY` 或 `NOT-READY <原因1; 原因2...>`
退出码：0 = READY / 1 = NOT-READY（可脚本化判断）
用法：~/src/MimirAether/.venv/bin/python3 ~/.mimiraether/scripts/iq_reeval_ready_probe.py
"""
import os
import re
import subprocess
import sys

SWAP_MIN_GB = float(os.environ.get("IQ_PROBE_SWAP_MIN_GB", "1.0"))
LOAD_MAX = float(os.environ.get("IQ_PROBE_LOAD_MAX", "2.0"))
# 探针自测用：IQ_PROBE_IGNORE_BUSY=1 跳过「占用进程」检查（只为正控，不为放行）
# 只匹配「真跑」的进程；本探针自身与 grep 自身不算
BUSY_PATTERNS = [
    (r"pytest", "有 pytest 在跑"),
    (r"bge-m3", "bge-m3 嵌入进程在跑"),
    (r"bge-reranker", "bge-reranker 重排在跑"),
    (r"chroma_session_indexer|session_indexer|backfill_sessions", "索引/回填进程在跑"),
    (r"lm-evaluation-harness|lm_eval", "评测进程在跑"),
]


def swap_free_gb():
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("SwapFree:"):
                    return int(line.split()[1]) / 1024.0 / 1024.0
    except OSError:
        pass
    return 0.0


def load1():
    try:
        return os.getloadavg()[0]
    except OSError:
        return 99.0


def busy_procs():
    out = []
    ps = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True).stdout
    me = str(os.getpid())
    for line in ps.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        pid, _, args = line.partition(" ")
        if pid == me or "iq_reeval_ready_probe" in args or "ps -eo pid,args" in args:
            continue
        for pat, label in BUSY_PATTERNS:
            if re.search(pat, args, re.IGNORECASE):
                out.append("%s(pid=%s)" % (label, pid))
                break
    return out


def main() -> int:
    reasons = []
    sf = swap_free_gb()
    ld = load1()
    if sf < SWAP_MIN_GB:
        reasons.append("swap free %.2fGB < %.1fGB" % (sf, SWAP_MIN_GB))
    if ld >= LOAD_MAX:
        reasons.append("load1 %.2f >= %.1f" % (ld, LOAD_MAX))
    busy = [] if os.environ.get("IQ_PROBE_IGNORE_BUSY") == "1" else busy_procs()
    if busy:
        reasons.append("占用进程: " + ", ".join(busy))
    if reasons:
        print("NOT-READY " + "; ".join(reasons))
        return 1
    print("READY swap_free=%.2fGB load1=%.2f" % (sf, ld))
    return 0


if __name__ == "__main__":
    sys.exit(main())
