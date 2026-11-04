#!/usr/bin/env python3
"""E4 · IQ 复评「现在能不能跑 / 能不能出分」（**不跑复评**）。

两道闸，一个入口：
  闸 A · 机器态（NOT-READY，稍后重试）
    1) MemAvailable >= 2 GB        ← 主判（2026-11-04 改口径）
    2) load average(1m) < 2
    3) 无其他 pytest / 索引进程（bge-m3 / bge-reranker / chroma indexer）
    swap free = **顾问项**：只记录、不阻塞。理由（实测）：本机 swap 4G/4G、
    free=0B 长期如此 ⇒ 以它作 blocking 就是恒红 ⇒ 闸被忽略（与 R7/R10 同族）。
    真正危险信号是 MemAvailable 塌（并发跑 bge-m3+reranker 时 6.2s→31.7s）。
  闸 B · 量具态（NO-SCORE，必须先修尺子再谈分）—— 台账 T-A1
    三量具：feedback_events / verification_results / compression_quality
    每份判四件事：① 存在 ② 可解析（尾段坏行率 <= 1%）③ schema 含关键字段
                  ④ 新鲜度（尾段时间 <= 各自阈值）
    阈值来源（实测节律，2026-11-04）：avg_gap 4.9h / 5.0h / 20.2h
                                    ⇒ 阈值 48h / 48h / 96h（含 ~3-6x 余量）
    语义边界：新鲜度**不能**区分「量具坏了」与「系统长期没跑」——两者对出分同样致命
             （停更量具算出的分不可信），故同判 NO-SCORE，这是**设计意图**不是缺陷。

输出：单行
  `READY mem_avail=<x>GB swap_free=<y>GB load1=<z> | gauges=<n>/3`
  `NO-SCORE <gauge>:<reason>; ...`     量具态失败（优先级最高）
  `NOT-READY <reason1>; <reason2>...`  机器态失败
退出码：0 = READY / 1 = NO-SCORE 或 NOT-READY（可脚本化判断）

用法：
  ~/src/MimirAether/.venv/bin/python3 scripts/iq_reeval_ready_probe.py
  ~/src/MimirAether/.venv/bin/python3 scripts/iq_reeval_ready_probe.py --selftest
  ~/src/MimirAether/.venv/bin/python3 scripts/iq_reeval_ready_probe.py --json
"""
import argparse
import json
import os
import pwd
import re
import subprocess
import sys
import tempfile
import time
from collections import deque

MEM_AVAIL_MIN_GB = float(os.environ.get("IQ_PROBE_MEM_AVAIL_MIN_GB", "2.0"))
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

# ---------------------------------------------------------------- 闸 B 定义
# (文件名, 时间戳字段, 必需字段, 最大允许停更小时数)
GAUGES = [
    ("feedback_events.jsonl", "ts", ("ts", "event_type"), 48.0),
    ("verification_results.jsonl", "timestamp", ("timestamp", "passed"), 48.0),
    ("compression_quality.jsonl", "ts", ("ts", "entity_retention_rate"), 96.0),
]
TAIL_LINES = 200          # 只审尾段：5MB/16k 行全扫无必要，尾段足以判「活着」
BAD_RATIO_MAX = 0.01      # 尾段坏行率上限 1%


def default_data_dir():
    """数据根。用 pwd 取 home，**不用 expanduser**。

    2026-11 实证：沙箱里 HOME 可能被改成 ~/.mimiraether，
    expanduser 会把同一脚本读成不存在的路径 ⇒ 两环境读数不一致 ⇒ 假阴性。
    """
    home = pwd.getpwuid(os.getuid()).pw_dir
    return os.path.join(home, ".mimiraether", "data")


def _tail_lines(path, n):
    with open(path, encoding="utf-8", errors="replace") as f:
        return list(deque(f, maxlen=n))


def _parse_ts(v):
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return None
    try:
        return time.mktime(time.strptime(v[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return None


def evaluate_gauges(data_dir, now=None):
    """纯函数：返回 (ok: bool, details: list[dict], reasons: list[str])。

    只读数据面、不读进程态 ⇒ 可被自测用临时目录完整驱动（无需绕过任何闸）。
    """
    now = time.time() if now is None else now
    details = []
    reasons = []

    def _fail(d, status, reason):
        d["status"] = status
        d["reason"] = reason
        reasons.append("%s:%s" % (d["gauge"], reason))
        details.append(d)

    for name, ts_key, required, max_age_h in GAUGES:
        path = os.path.join(data_dir, name)
        d = {"gauge": name, "status": "ok", "lines": 0, "bad": 0,
             "last_age_h": None, "reason": None}
        if not os.path.exists(path):
            _fail(d, "missing", "文件不存在")
            continue
        if os.path.getsize(path) == 0:
            _fail(d, "empty", "文件为空")
            continue
        try:
            lines = _tail_lines(path, TAIL_LINES)
        except OSError as e:
            _fail(d, "unreadable", "读失败(errno=%s)" % e.errno)
            continue
        parsed = []
        bad = 0
        for line in lines:
            s = line.strip()
            if not s:
                continue
            try:
                parsed.append(json.loads(s))
            except Exception:
                bad += 1
        total = len(parsed) + bad
        d["lines"] = len(parsed)
        d["bad"] = bad
        if total == 0:
            _fail(d, "empty", "尾段无有效行")
            continue
        if bad / float(total) > BAD_RATIO_MAX:
            _fail(d, "corrupt", "尾段坏行 %d/%d 超 %.0f%%" % (bad, total, BAD_RATIO_MAX * 100))
            continue
        last = parsed[-1]
        missing = [k for k in required if k not in last]
        if missing:
            _fail(d, "schema", "缺关键字段 %s" % ",".join(missing))
            continue
        ts_list = [t for t in (_parse_ts(o.get(ts_key)) for o in parsed) if t]
        if not ts_list:
            _fail(d, "no_ts", "无可解析时间戳")
            continue
        age_h = (now - max(ts_list)) / 3600.0
        d["last_age_h"] = round(age_h, 1)
        if age_h > max_age_h:
            _fail(d, "stale", "停更 %.1fh 超阈值 %.0fh" % (age_h, max_age_h))
            continue
        details.append(d)

    ok = not reasons
    return ok, details, reasons


# ---------------------------------------------------------------- 闸 A
def mem_available_gb():
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024.0 / 1024.0
    except OSError:
        pass
    return 0.0


def swap_free_gb():
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("SwapFree:"):
                    return int(line.split()[1]) / 1024.0 / 1024.0
    except OSError:
        pass
    return 0.0


def evaluate_machine(mem_avail_gb, swap_free_gb, ld, busy,
                     mem_min=None, load_max=None):
    """机器态判定（纯函数：值全注入 ⇒ 可两向自测，不读真机）。

    swap_free_gb 只进 advisory，**不进 reasons**（顾问项不阻塞）。
    """
    mem_min = MEM_AVAIL_MIN_GB if mem_min is None else mem_min
    load_max = LOAD_MAX if load_max is None else load_max
    reasons = []
    if mem_avail_gb < mem_min:
        reasons.append("MemAvailable %.2fGB < %.1fGB" % (mem_avail_gb, mem_min))
    if ld >= load_max:
        reasons.append("load1 %.2f >= %.1f" % (ld, load_max))
    if busy:
        reasons.append("占用进程: " + ", ".join(busy))
    advisory = {"swap_free_gb": round(swap_free_gb, 2), "swap_is_advisory": True}
    return (not reasons), reasons, advisory


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


# ---------------------------------------------------------------- 自测（两向）
def _write_gauge(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _seed(dirpath, now, ages=(0.5, 0.5, 0.5)):
    _write_gauge(os.path.join(dirpath, "feedback_events.jsonl"),
                 [{"ts": now - ages[0] * 3600, "event_type": "pipeline_close"}])
    _write_gauge(os.path.join(dirpath, "verification_results.jsonl"),
                 [{"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S",
                                              time.localtime(now - ages[1] * 3600)),
                   "passed": True}])
    _write_gauge(os.path.join(dirpath, "compression_quality.jsonl"),
                 [{"ts": time.strftime("%Y-%m-%dT%H:%M:%S",
                                       time.localtime(now - ages[2] * 3600)),
                   "entity_retention_rate": 1.0}])


def selftest():
    """两向控制：正控必须放行、负控必须拦住，且**拦的理由要对**（不只判 rc）。

    期望值必须不同（正控 rc=0 / 负控 rc=1），目标样本不得兼作控制样本。
    """
    now = time.time()
    cases = []

    def run(label, prep, expect_ok, expect_substr):
        d = tempfile.mkdtemp(prefix="gauge_selftest_")
        try:
            prep(d)
            ok, details, reasons = evaluate_gauges(d, now=now)
            got = ("ok" if ok else ";".join(reasons))
            hit = expect_substr in got
            cases.append((label, expect_ok == ok and hit,
                          "expect_ok=%s got_ok=%s expect~%r got=%r"
                          % (expect_ok, ok, expect_substr, got)))
        finally:
            for fn in os.listdir(d):
                os.unlink(os.path.join(d, fn))
            os.rmdir(d)

    # 正控：三量具齐全、新鲜、schema 正确 ⇒ 放行
    run("POS 全部健康", lambda d: _seed(d, now), True, "ok")
    # 负控 1：缺一份
    def _miss(d):
        _seed(d, now)
        os.unlink(os.path.join(d, "verification_results.jsonl"))
    run("NEG 缺文件", _miss, False, "文件不存在")
    # 负控 2：停更
    run("NEG 停更", lambda d: _seed(d, now, ages=(0.5, 0.5, 500.0)), False, "停更")
    # 负控 3：坏行
    def _corrupt(d):
        _seed(d, now)
        with open(os.path.join(d, "feedback_events.jsonl"), "a", encoding="utf-8") as f:
            for _ in range(10):
                f.write("{not json\n")
    run("NEG 坏行", _corrupt, False, "坏行")
    # 负控 4：schema 缺字段
    def _schema(d):
        _seed(d, now)
        _write_gauge(os.path.join(d, "compression_quality.jsonl"), [{"ts": now}])
    run("NEG 缺字段", _schema, False, "缺关键字段")
    # 负控 5：空文件
    run("NEG 空文件",
        lambda d: (_seed(d, now),
                   open(os.path.join(d, "feedback_events.jsonl"), "w").close()),
        False, "文件为空")

    # ---- 闸 A（机器态）两向：纯函数注入，不读真机 ----
    # 设计要点：NEG 用例必须**拦得住**且理由要对；POS 里必须有一条
    # 「swap 全满但内存充足 ⇒ 放行」——这正是 2026-11-04 改口径要保的行为
    # （旧口径 swap_free>=1GB 在本机恒红，闸等于没有）。
    mach = [
        ("POS 机器态健康", dict(mem_avail_gb=4.0, swap_free_gb=8.0, ld=0.5, busy=[]),
         True, "ok"),
        ("POS swap=0 内存足", dict(mem_avail_gb=4.7, swap_free_gb=0.0, ld=1.0, busy=[]),
         True, "ok"),
        ("NEG 内存不足", dict(mem_avail_gb=0.5, swap_free_gb=8.0, ld=0.2, busy=[]),
         False, "MemAvailable"),
        ("NEG 负载高", dict(mem_avail_gb=8.0, swap_free_gb=8.0, ld=3.0, busy=[]),
         False, "load1"),
        ("NEG 占用进程", dict(mem_avail_gb=8.0, swap_free_gb=8.0, ld=0.2, busy=["bge-m3"]),
         False, "占用进程"),
    ]
    for label, kw, expect_ok, substr in mach:
        ok, reasons, adv = evaluate_machine(**kw)
        got = "ok" if ok else ";".join(reasons)
        cases.append((label, expect_ok == ok and substr in got,
                      "expect_ok=%s got=%r adv=%r" % (expect_ok, got, adv)))

    passed = 0
    for label, ok, detail in cases:
        print("%s %-16s %s" % ("PASS" if ok else "FAIL", label, detail))
        passed += 1 if ok else 0
    print("--- %d/%d passed" % (passed, len(cases)))
    return 0 if passed == len(cases) else 1


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--selftest", action="store_true", help="两向控制自检（不读真库）")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--data-dir", default=None, help="覆盖数据根（默认 ~/.mimiraether/data）")
    ap.add_argument("--skip-machine", action="store_true",
                    help="只跑闸 B（量具态），不跑闸 A（机器态）")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    data_dir = args.data_dir or default_data_dir()
    g_ok, g_details, g_reasons = evaluate_gauges(data_dir)

    if args.json:
        payload = {"verdict": "READY" if g_ok else "NO-SCORE",
                   "gates": {"gauges": {"ok": g_ok, "details": g_details,
                                        "reasons": g_reasons},
                             "machine": None}}
        if not args.skip_machine:
            sf = swap_free_gb()
            ma = mem_available_gb()
            ld = load1()
            busy = [] if os.environ.get("IQ_PROBE_IGNORE_BUSY") == "1" else busy_procs()
            m_ok, m_reasons, adv = evaluate_machine(ma, sf, ld, busy)
            payload["gates"]["machine"] = {"ok": m_ok, "mem_available_gb": round(ma, 2),
                                           "load1": round(ld, 2), "reasons": m_reasons,
                                           **adv}
            if not m_reasons and g_ok:
                payload["verdict"] = "READY"
            elif not g_ok:
                payload["verdict"] = "NO-SCORE"
            else:
                payload["verdict"] = "NOT-READY"
        print(json.dumps(payload, ensure_ascii=False))
        if not g_ok:
            return 1
        return 0 if payload["verdict"] == "READY" else 1

    # 闸 B 优先：尺子不健康，机器再空闲也不该出分
    if not g_ok:
        print("NO-SCORE " + "; ".join(g_reasons))
        return 1

    if args.skip_machine:
        print("READY | gauges=%d/%d (machine skipped)" % (len(g_details), len(GAUGES)))
        return 0

    sf = swap_free_gb()
    ma = mem_available_gb()
    ld = load1()
    busy = [] if os.environ.get("IQ_PROBE_IGNORE_BUSY") == "1" else busy_procs()
    m_ok, reasons, _adv = evaluate_machine(ma, sf, ld, busy)
    if not m_ok:
        print("NOT-READY " + "; ".join(reasons))
        return 1
    print("READY mem_avail=%.2fGB swap_free=%.2fGB load1=%.2f | gauges=%d/%d"
          % (ma, sf, ld, len(g_details), len(GAUGES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
