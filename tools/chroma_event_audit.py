#!/usr/bin/env python3
"""D2/D13 —— chroma 写入事件账本审计（RL-20261020-094）。

判什么
------
账本 `~/.mimiraether/data/chroma_write_events.jsonl` 每行一条事件：
  begin / end / acquire_failed，带 pid、nonce、seq、role、ts、hold_ms。
本脚本不信任任何自我陈述，只从事件序列算四个机器数：

  unpaired    : begin 没有配对的 end      —— 只该在进程被杀（SIGKILL）时 >0
  overlaps    : 不同 pid 的临界区区间相交 —— 必须恒为 0（锁的核心保证）
  timeouts    : acquire_failed/result=timeout 的条数
  errors      : acquire_failed/result=error + end/result=error

区间口径：begin.ts → end.ts（墙钟秒，end.ts 取在**解锁之前**）。配对键 = (pid, nonce)，同键 FIFO。
nonce 自第 2 批起**每次取锁都新发**（`pid:ns:序号`），所以一对 begin/end 唯一对应一个临界区。
B12b 之前 nonce 每进程只生成一次（fd 终生不关），同一 pid 的临界区共用一个键，配对实质
退化成「按 pid 排队」——丢一行会让该 pid 之后整段错配。读老账本时要记住这个差别。

seq：每进程单调计数（第 2 批起）。丢行 ⇒ 空洞 ⇒ `seq_gaps > 0` ⇒ rc=2。老账本没有该字段，
不参与统计（不能因为「旧证据没这个字段」判红）。

样本纪律：n>=20 才出 p95，n<20 只报 max（不出分，避免拿 3 个样本吹分布）。

证据面（为什么 rc=3 不能只判 pairs==0）
--------------------------------------
「数出来是 0」和「根本没数到」是两件事，混成一个 0 就是假绿。以下都算**没有可用证据**：
  · 账本缺失 / 为空
  · 只有 acquire_failed，没有任何成对临界区
  · 账本读不出来（权限/是目录）——读不到≠崩溃，按证据缺失处理
  · 只有一个 pid 的临界区——overlaps 的定义是「不同 pid 区间相交」，单 pid 时空真
  · 证据陈旧：最后一条事件早于 --max-age-s（默认 86400s）
    ※ 关键：MIMIR_CHROMA_EVENTS=0 只是让账本**停止增长**，不会清空历史；
      所以「关掉了」不等于「账本为空」——历史配对会永久输出绿。这条必须靠时间面抓。

退出码（退出码是 API）
  0  有证据（pairs>0、≥2 个 pid、未陈旧）且无违规
  2  有违规：unpaired / overlaps / orphan_ends / parse_errors / unknown_phase /
             seq_gaps（事件账本丢行）/ lock_errors（acquire_failed/result≠timeout，即锁本体报错）任一 > 0
  3  弃权：没有可用证据（见上），或证据陈旧；stderr 会点名是哪一种
说明：end/result=error（临界区内操作失败）**不算违规**——锁本身履职了，那是索引器
健康问题（已有 note_index_failure / 降级机制）。但它不会被静默：rc=0 时也往 stderr 打一行。

用法：
  chroma_event_audit.py [--file PATH] [--json] [--max-age-s N] [--selftest]
  --file 缺省时优先级：MIMIR_CHROMA_EVENTS_FILE（非空）> $MIMIR_HOME/data/chroma_write_events.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

EVENTS_FILE_ENV = "MIMIR_CHROMA_EVENTS_FILE"


def default_events_path() -> Path:
    """默认账本落点——**与写端同源**（tools.chroma_session_indexer.chroma_events_path）。

    为什么不直接 import 写端模块：写端顶层要拉 sqlite3/fcntl 与索引器依赖，审计器
    必须保持「只读、毫秒级启动」（角色卡 L33「Startup time is a feature」）。两侧口径
    不靠人记得同步，靠 test_chroma_event_audit.py 的等值断言：同一条 env 下两个函数
    必须解析出同一个 Path。

    F5（第 3 批）：``MIMIR_CHROMA_EVENTS_FILE`` 让审计器读临时账本；空字符串 =
    没设 ⇒ 回落默认路径（不是「路径为空」）。
    """
    raw = (os.environ.get(EVENTS_FILE_ENV) or "").strip()
    if raw:
        return Path(raw).expanduser()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from mimir_constants import get_mimir_home

    return Path(get_mimir_home()) / "data" / "chroma_write_events.jsonl"


def load_events(path: Path) -> Tuple[List[Dict[str, Any]], int, str]:
    """返回 (记录, 坏行数, 读失败原因)。

    坏行**不再静默吞掉**：一行读不出来就意味着证据少了一条，必须计数上报。
    （B12 之前 `except Exception: continue` 让截断行与整行丢失对审计完全隐形。）

    读不出来（PermissionError / IsADirectoryError / …）**不是崩溃**：它与「账本不存在」
    同类——没有可用证据。B12b 之前这里直接抛 traceback 并返回未声明的 rc=1，
    既破坏了「退出码是 API」，又丢掉了弃权那句最该给的修法指引。
    """
    out: List[Dict[str, Any]] = []
    bad = 0
    try:
        if not path.exists():
            return out, bad, ""
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    bad += 1
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
                else:
                    bad += 1
    except OSError as exc:
        return out, bad, f"{type(exc).__name__}: {exc}"
    return out, bad, ""


def audit(records: List[Dict[str, Any]], *, parse_errors: int = 0) -> Dict[str, Any]:
    open_map: Dict[Tuple[Any, Any], List[Dict[str, Any]]] = {}
    pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    timeouts = 0
    errors = 0
    lock_errors = 0   # acquire_failed 且 result≠timeout：锁本体没能取到（OSError/flock 失败）
    index_errors = 0  # end 且 result=error：锁尽职了，临界区内的写失败（索引器健康问题）
    orphan_ends = 0
    unknown_phase = 0

    for rec in records:
        phase = rec.get("phase")
        if phase == "begin":
            open_map.setdefault((rec.get("pid"), rec.get("nonce")), []).append(rec)
        elif phase == "end":
            key = (rec.get("pid"), rec.get("nonce"))
            queue = open_map.get(key) or []
            if queue:
                pairs.append((queue.pop(0), rec))
            else:
                # end 没有 begin 可配：三种真实来源——① begin 那行被截断/丢行
                # ② _emit_event fail-open（begin 写失败而 end 写成功）③ 账本被外部截断。
                # 三种都不是「干净」，必须出声（B12 之前这里静默丢弃）。
                orphan_ends += 1
            if rec.get("result") == "error":
                index_errors += 1
                errors += 1
        elif phase == "acquire_failed":
            if rec.get("result") == "timeout":
                timeouts += 1
            else:
                lock_errors += 1
                errors += 1
        else:
            # 不认识的 phase：本审计器无法解释它 ⇒ 它的判决不可能完整。
            unknown_phase += 1

    unpaired = [b for q in open_map.values() for b in q]
    intervals = sorted((float(b["ts"]), float(e["ts"]), b.get("pid")) for b, e in pairs)

    # 第 2 批：账本每条事件带进程内单调 seq ⇒ 丢行会留下空洞。
    # 只统计「带 seq 的记录」，老账本（B12b 之前）没有该字段，不能因此判红。
    seq_by_pid: Dict[Any, List[int]] = {}
    for rec in records:
        seq = rec.get("seq")
        if isinstance(seq, int) and not isinstance(seq, bool):
            seq_by_pid.setdefault(rec.get("pid"), []).append(seq)
    seq_gaps = 0
    seq_dups = 0
    for seqs in seq_by_pid.values():
        if len(seqs) < 2:
            continue
        uniq = set(seqs)
        seq_dups += len(seqs) - len(uniq)
        seq_gaps += max(0, (max(uniq) - min(uniq) + 1) - len(uniq))

    overlaps = 0
    active: List[Tuple[float, Any]] = []
    for start, end, pid in intervals:
        active = [a for a in active if a[0] > start]
        overlaps += sum(1 for a in active if a[1] != pid)
        active.append((end, pid))

    holds = sorted(round((e - b) * 1000.0, 3) for b, e, _ in intervals)
    p95 = None
    if len(holds) >= 20:
        idx = max(0, min(len(holds) - 1, int(round(0.95 * (len(holds) - 1)))))
        p95 = holds[idx]

    return {
        "events": len(records),
        "begins": sum(1 for r in records if r.get("phase") == "begin"),
        "ends": sum(1 for r in records if r.get("phase") == "end"),
        "pairs": len(pairs),
        "unpaired": len(unpaired),
        "unpaired_detail": [
            {"pid": b.get("pid"), "nonce": b.get("nonce"), "ts": b.get("ts")} for b in unpaired[:5]
        ],
        "overlaps": overlaps,
        "orphan_ends": orphan_ends,
        "unknown_phase": unknown_phase,
        "parse_errors": parse_errors,
        "seq_gaps": seq_gaps,
        "seq_dups": seq_dups,
        "seq_pids": len(seq_by_pid),
        "no_pairs": not pairs,
        "distinct_pids": len({r.get("pid") for r in records if r.get("pid") is not None}),
        "last_event_ts": max(
            (float(r["ts"]) for r in records if isinstance(r.get("ts"), (int, float))),
            default=None,
        ),
        "timeouts": timeouts,
        "errors": errors,
        "lock_errors": lock_errors,
        "index_errors": index_errors,
        "samples": len(holds),
        "max_hold_ms": holds[-1] if holds else None,
        "p95_hold_ms": p95,
        "p95_note": "n>=20" if p95 is not None else f"n={len(holds)}<20·只报 max",
        "roles": sorted({str(r.get("role")) for r in records if r.get("role")}),
    }


DEFAULT_MAX_AGE_S = 86400.0  # 证据新鲜度上限：超过它就只是「历史干净」，不是「现在干净」


def verdict(
    res: Dict[str, Any],
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
    now: float | None = None,
) -> int:
    """唯一的判据阶梯——main() 与 selftest() 共用，避免「selftest 绿但 rc 阶梯坏」。

    优先级：违规 > 弃权（无证据/单 pid/陈旧）> 0。
    违规优先的理由：已知有证据丢失时，「判不了」不能把「已经坏了」盖过去。
    """
    violations = (
        res["unpaired"]
        or res["overlaps"]
        or res["orphan_ends"]
        or res["parse_errors"]
        or res["unknown_phase"]
        or res.get("lock_errors", 0)
        or res.get("seq_gaps", 0)
    )
    if violations:
        return 2
    if res.get("unreadable"):
        return 3
    if res["no_pairs"]:
        return 3
    # 单 pid：overlaps 的定义是「不同 pid 区间相交」，只有一个 pid 时该数恒 0 = 空真。
    if res.get("distinct_pids", 0) < 2:
        return 3
    if max_age_s > 0:
        last = res.get("last_event_ts")
        if last is None:
            return 3
        if (now if now is not None else time.time()) - last > max_age_s:
            return 3
    return 0


def selftest() -> int:
    base = 1_000.0
    ok_seq = [
        {"phase": "begin", "ts": base, "pid": 1, "nonce": "a"},
        {"phase": "end", "ts": base + 0.1, "pid": 1, "nonce": "a"},
        {"phase": "begin", "ts": base + 0.2, "pid": 2, "nonce": "b"},
        {"phase": "end", "ts": base + 0.3, "pid": 2, "nonce": "b"},
    ]
    overlap = [
        {"phase": "begin", "ts": base, "pid": 1, "nonce": "a"},
        {"phase": "begin", "ts": base + 0.05, "pid": 2, "nonce": "b"},
        {"phase": "end", "ts": base + 0.2, "pid": 1, "nonce": "a"},
        {"phase": "end", "ts": base + 0.3, "pid": 2, "nonce": "b"},
    ]
    unpaired = [{"phase": "begin", "ts": base, "pid": 3, "nonce": "c"}]
    timeout = [{"phase": "acquire_failed", "ts": base, "pid": 4, "result": "timeout"}]
    orphan = [{"phase": "end", "ts": base, "pid": 5, "nonce": "d", "result": "ok"}]
    unknown = [{"phase": "heartbeat", "ts": base, "pid": 6}]

    fails = 0

    def check(name: str, cond: bool) -> None:
        nonlocal fails
        print(("PASS " if cond else "FAIL ") + name)
        fails += 0 if cond else 1

    a = audit(ok_seq)
    check("顺序执行 overlaps=0", a["overlaps"] == 0 and a["pairs"] == 2 and a["unpaired"] == 0)
    b = audit(overlap)
    check("真重叠 overlaps=1", b["overlaps"] == 1)
    c = audit(unpaired)
    check("缺 end unpaired=1", c["unpaired"] == 1)
    d = audit(timeout)
    check("超时计 timeout=1 不污染 unpaired", d["timeouts"] == 1 and d["unpaired"] == 0)
    check("同键 FIFO 配对", audit(ok_seq + ok_seq[:2])["pairs"] == 3)
    # B12：证据面两向——缺一半证据必须能看见
    e = audit(orphan)
    check("孤儿 end 计入 orphan_ends", e["orphan_ends"] == 1 and e["pairs"] == 0)
    f = audit(unknown)
    check("未知 phase 计入 unknown_phase", f["unknown_phase"] == 1)
    g = audit([])
    check("空账本 no_pairs=True", g["no_pairs"] is True and g["events"] == 0)
    check("有证据则 no_pairs=False", a["no_pairs"] is False)
    check("坏行数透传", audit(ok_seq, parse_errors=2)["parse_errors"] == 2)

    # B12b：判据阶梯必须自己也被测。审计员指出——B12 的 10 臂全在 audit() 层，
    # 把 unknown_phase 从 violations 里删掉，selftest 仍然 10/10 全绿。
    check("rc 阶梯 干净⇒0", verdict(a, now=a["last_event_ts"]) == 0)
    check("rc 阶梯 真重叠⇒2", verdict(b, now=b["last_event_ts"]) == 2)
    check("rc 阶梯 空账本⇒3", verdict(g, now=0.0) == 3)
    check("rc 阶梯 违规+无证据并存⇒2（优先级）", verdict(audit(orphan), now=0.0) == 2)
    one_pid = audit([
        {"phase": "begin", "ts": base, "pid": 1, "nonce": "a"},
        {"phase": "end", "ts": base + 0.1, "pid": 1, "nonce": "a"},
    ])
    check("rc 阶梯 单 pid⇒3（空真）", verdict(one_pid, now=base) == 3)
    check("rc 阶梯 陈旧证据⇒3", verdict(a, now=a["last_event_ts"] + 86401) == 3)
    lock_err = audit([{"phase": "acquire_failed", "ts": base, "pid": 1, "result": "error"}])
    check("rc 阶梯 lock_errors⇒2", verdict(lock_err, now=base) == 2)
    idx_err = [dict(r) for r in ok_seq]
    idx_err[1]["result"] = "error"
    check("rc 阶梯 index_errors 不算违规⇒0", verdict(audit(idx_err), now=base + 0.3) == 0)

    # 第 2 批：seq 是「丢行」的唯一证据面
    seq_ok = [dict(r, seq=i + 1) for i, r in enumerate(ok_seq)]
    check("seq 连续⇒无缺口", audit(seq_ok)["seq_gaps"] == 0)
    seq_gap = [dict(r, seq=i + 1) for i, r in enumerate(ok_seq)]
    seq_gap[2]["seq"] = 9  # 3 号那条丢了
    check("seq 空洞计入", audit(seq_gap)["seq_gaps"] > 0)
    check("rc 阶梯 seq 空洞⇒2", verdict(audit(seq_gap), now=base + 0.3) == 2)
    check("无 seq 的老账本不判红", audit(ok_seq)["seq_gaps"] == 0 and "seq" not in ok_seq[0])
    return 2 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--max-age-s",
        type=float,
        default=DEFAULT_MAX_AGE_S,
        help="证据新鲜度上限（秒）；超过则弃权 rc=3。0=不检查新鲜度",
    )
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.file:
        path = Path(args.file)
    else:
        # F5：写端与读端必须认同一条 env（MIMIR_CHROMA_EVENTS_FILE），否则
        # 「演练写到临时账本」会被审计器读成「生产账本没有证据」= 假弃权。
        path = default_events_path()

    records, parse_errors, read_error = load_events(path)
    res = audit(records, parse_errors=parse_errors)
    res["file"] = str(path)
    res["unreadable"] = bool(read_error)
    res["read_error"] = read_error

    rc = verdict(res, max_age_s=args.max_age_s, now=time.time())
    res["max_age_s"] = args.max_age_s
    res["last_event_age_s"] = (
        round(time.time() - res["last_event_ts"], 1) if res["last_event_ts"] is not None else None
    )
    # abstained 只描述 rc==3：B12 里它等于 not pairs，导致孤儿 end 时
    # 同时出现 abstained=true 与 rc=2（下游按字段分流会读反）。审计员指出，已改。
    res["abstained"] = rc == 3
    res["rc"] = rc

    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"file={res['file']}")
        print(f"  events={res['events']} begins={res['begins']} ends={res['ends']} pairs={res['pairs']}")
        print(f"  unpaired={res['unpaired']}  overlaps={res['overlaps']}  "
              f"timeouts={res['timeouts']}  errors={res['errors']}"
              f" (lock={res['lock_errors']} index={res['index_errors']})")
        print(f"  evidence_gaps: orphan_ends={res['orphan_ends']}  "
              f"parse_errors={res['parse_errors']}  unknown_phase={res['unknown_phase']}  "
              f"seq_gaps={res['seq_gaps']}")
        print(f"  pids={res['distinct_pids']}  last_event_age_s={res['last_event_age_s']}"
              f"  (max_age_s={res['max_age_s']})")
        print(f"  hold_ms: max={res['max_hold_ms']} p95={res['p95_hold_ms']} ({res['p95_note']})")
        print(f"  roles={res['roles']}")
        print(f"  rc={res['rc']}")

    if rc == 3:
        # 弃权必须出声：静默的 0 与「证明干净」在日志里长得一模一样。
        if res["unreadable"]:
            why = f"账本读不出来（{res['read_error']}）——查权限/路径（不是目录）、或传 --file"
        elif res["no_pairs"]:
            why = (f"没有任何成对临界区（events={res['events']}）——查账本是否被删/轮转/清空、"
                   "或本机确实还没有跨进程写入")
        elif res["distinct_pids"] < 2:
            why = (f"只有一个 pid（{res['distinct_pids']}）——overlaps 恒 0 是空真，"
                   "跨进程互斥零证明力")
        else:
            why = (f"证据陈旧：最后一条事件在 {res['last_event_age_s']}s 前，"
                   f"超过 max_age_s={res['max_age_s']}——MIMIR_CHROMA_EVENTS=0 只让账本停止增长，"
                   "不会清空历史，所以「关掉了」不等于「查过了」")
        print(f"弃权：{res['file']} 没有可用证据——{why}。"
              "「数到 0」不等于「证明干净」。", file=sys.stderr)
    elif rc == 2:
        print(
            f"违规：unpaired={res['unpaired']} overlaps={res['overlaps']} "
            f"orphan_ends={res['orphan_ends']} parse_errors={res['parse_errors']} "
            f"unknown_phase={res['unknown_phase']} lock_errors={res['lock_errors']} "
            f"seq_gaps={res['seq_gaps']}",
            file=sys.stderr,
        )

    # index_errors 不算违规（锁尽职了），但也不能静默——rc=0 时照样出声。
    if res["index_errors"] and rc != 2:
        print(
            f"注意：index_errors={res['index_errors']}（临界区内写失败，锁本身无异常）"
            f"——查 note_index_failure 渠道与 chroma 降级状态。",
            file=sys.stderr,
        )
    return rc


if __name__ == "__main__":
    sys.exit(main())
