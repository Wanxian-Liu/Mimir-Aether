"""一次性取证：③ 归因表各窗口「单文件 vs 收轮转档」的 turns 覆盖对比。

问题来源：统筹席问「收档后归因表 13 行空会变成几行非空」。
口径：与 slo_dashboard.attribution_section 同构（同 TURN_RE、同窗口边界、同 stat_cells 判空 = n==0 ⇒ '无数据'）。
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.expanduser("~"), "src/MimirAether/scripts"))
from datetime import datetime
from pathlib import Path
import slo_dashboard as S


def parse_full_glob():
    """与 parse_log_full 同正则同 ts 解析，但读 glob(agent.log*) —— 即 ⑤ 段的数据源。"""
    turns = []
    for path in sorted(Path(S.LOG_DIR).glob("agent.log*")):
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    ts_str = line[:19]
                    try:
                        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        continue
                    m = S.TURN_RE.search(line)
                    if m:
                        tid, tnum, api, ntools, total = m.groups()
                        turns.append((ts, float(api), int(ntools), float(total)))
        except FileNotFoundError:
            continue
    return turns


def main():
    single = S.parse_log_full()
    gl = parse_full_glob()
    print(f"LOG_FILE = {S.LOG_FILE}")
    print(f"files    = {[p.name for p in sorted(Path(S.LOG_DIR).glob('agent.log*'))]}")
    print(f"single_full_turns = {len(single)}")
    print(f"glob_full_turns   = {len(gl)}")
    if single:
        print(f"single span = {single[0][0]} .. {single[-1][0]}")
    if gl:
        print(f"glob   span = {gl[0][0]} .. {gl[-1][0]}")

    commits = S.git_perf_commits()
    round_start = datetime(2026, 8, 19, 0, 0, 0)
    rc = [c for c in commits if c[0] >= round_start]
    # pre_cutoff 必须与 slo_dashboard.main() 同逻辑（P0-1 并行上线时刻），
    # 否则 pre 行读的不是生产口径 —— 2026-11-08 实测：用「首个 round commit」会凭空得到 5197 条。
    pre_cutoff = None
    for ts, h, subj in commits:
        if "P0-1" in subj and "并行" in subj:
            pre_cutoff = ts
            break
    if pre_cutoff is None:
        pre_cutoff = datetime(2026, 8, 19, 2, 8, 0)
    print(f"round_commits = {len(rc)}  pre_cutoff = {pre_cutoff}")

    rows_single, rows_glob = [], []
    for i, (ts, h, subj) in enumerate(rc):
        end = rc[i + 1][0] if i + 1 < len(rc) else datetime.now()
        ns = len([t for t in single if ts <= t[0] < end])
        ng = len([t for t in gl if ts <= t[0] < end])
        rows_single.append(ns)
        rows_glob.append(ng)
    # pre 行
    ns_pre = len([t for t in single if t[0] < pre_cutoff])
    ng_pre = len([t for t in gl if t[0] < pre_cutoff])

    print("\nidx | commit | window_single | window_glob")
    for i, (ts, h, subj) in enumerate(rc):
        print(f"{i:>3} | {h} | {rows_single[i]:>5} | {rows_glob[i]:>5}")
    print(f"  pre | <{pre_cutoff.strftime('%Y-%m-%d %H:%M')} | {ns_pre:>5} | {ng_pre:>5}")
    print(f"  （pre 口径 = slo_dashboard.main() 的 P0-1并行 上线时刻；"
          f"日志最早 turn = {min(t[0] for t in gl) if gl else '无'}）")

    empty_s = sum(1 for n in rows_single if n == 0)
    empty_g = sum(1 for n in rows_glob if n == 0)
    print(f"\nROWS = {len(rc)}  空行(窗口无数据) single={empty_s} glob={empty_g}")
    print(f"非空行 single={len(rc)-empty_s} glob={len(rc)-empty_g}")
    print(f"pre 行: single n={ns_pre} ({'空' if ns_pre==0 else '非空'}) · glob n={ng_pre} ({'空' if ng_pre==0 else '非空'})")
    # 只靠收档才能非空的行（single 空 且 glob 非空）
    only_glob = [i for i in range(len(rc)) if rows_single[i] == 0 and rows_glob[i] > 0]
    only_single = [i for i in range(len(rc)) if rows_single[i] > 0 and rows_glob[i] == 0]
    print(f"仅收档才非空的行 idx = {only_glob}")
    print(f"仅单文件才非空的行 idx = {only_single}")


if __name__ == "__main__":
    main()
