#!/usr/bin/env python3
"""P4 SLO 看板 v2（2026-08-19 执行卡 #5）——pre 基线回填 + 7 天滚动 + bootstrap CI 逐 commit 归因

v1（2026-08-19 执行卡 #4）：每日报告：延迟 P50/P95/P99 + 工具数分布 + turns 分布
v2（2026-08-19 执行卡 #5）新增：
  1. pre 基线回填：修复前（P0-1 并行执行上线 2026-08-19 02:08 之前）的延迟基线
  2. 7 天滚动：按天输出 P50/P95/P99（滚动窗口，SLO_DAYS 默认 7）
  3. bootstrap CI：逐 commit 归因——按性能相关 commit 时间戳划分窗口，输出每窗口延迟

v3（2026-09-24 D 组三件）：
  1. D1 无数据口径：`stats_of([])` ⇒ 印 `无数据`/`—`，**禁印 0.0**（0.0 是有效读数，不是缺数据）
  2. D2 新鲜度断言：④ 段打印「距今 N 小时」，> `STALE_HOURS`(26) ⇒ 标 **数据陈旧**（且**不再**渲染「最新测量」字样）；
     报告头部有门禁状态位 `context_baseline_fresh=<bool>`；文件缺失 ⇒ 显式 `无数据`（不印 0）
  3. D3 口径标注：`chars/4` → `bytes//4` 粗口径（**不改算式**——保序列可比；注明**非 tokenizer 计数**）

v4（2026-11-08 · D1/D2/D3 口径统一 · 派单裁决执行）：
  1. **D1 窗口**：窗口改为**滚动 168 小时**（`SLO_WINDOW_HOURS`，默认 168；`SLO_DAYS` 仅兼容换算）。
     报表标题与字段名一律写「近 168 小时」，并打印**窗口锚点（生成时刻）**+**实际最早计入行**
     ——自证是滚动小时窗而非整日切点；禁再用「近 7 天」这类含糊词。
  2. **D2 数据源收档**：② 段数据源由单 `agent.log` 改为与 ⑤ 同为 `agent.log*`（含轮转档）；
     报告打印**数据源切换点**（收档起点），并声明 ② 历史序列在切换点前后**不可比**；
     ② 段 n 跳变处写明跳变原因（口径变化，非流量突变）。
  3. **D3 闸三态**（`scripts/check_window_parity.py`）：0 一致 / 1 偏离 / 2 无法判定；
     **数据缺失（空目录 / 日志真空）禁落 0**。

数据源: ~/.mimiraether/logs/agent.log*（D2 后 ② ⑤ 同源，含轮转档）
输出: ~/.mimiraether/slo/YYYY-MM-DD.md
"""
import os, re, sys, glob, subprocess, json, random
from datetime import datetime, timedelta
from collections import Counter, defaultdict

LOG_DIR = os.path.expanduser("~/.mimiraether/logs")
OUT_DIR = os.path.expanduser("~/.mimiraether/slo")
LOG_FILE = os.path.join(LOG_DIR, "agent.log")
# 源码仓路径：env 优先，其次 ~/src/MimirAether（不写死家目录字面值）
SRC_REPO = os.environ.get("MIMIR_SRC_REPO") or os.path.expanduser("~/src/MimirAether")
BASELINE_LOG = os.path.expanduser("~/.mimiraether/data/context_baseline.jsonl")

# D2（2026-09-24）：新鲜度阈值——默认 26h（容一次漏跑），超时 ⇒ 标「数据陈旧」不静默当现值
STALE_HOURS = float(os.environ.get("MIMIR_CONTEXT_STALE_HOURS", "26") or "26")

# D1（2026-11-08）：窗口单位 = 小时。滚动 168h = 「近 168 小时」；SLO_DAYS 仅作兼容换算（day*24）。
WINDOW_HOURS = int(float(os.environ.get("SLO_WINDOW_HOURS")
                        or float(os.environ.get("SLO_DAYS", "7") or "7") * 24))


def window_hours(days=None):
    """days → 小时。days 显式给出按 days*24（兼容旧调用），否则用 WINDOW_HOURS。"""
    return WINDOW_HOURS if days is None else int(days) * 24


def _context_baseline_freshness(stale_hours=None):
    """D2 新鲜度判定——返回 (fresh: bool, age_hours|None, ts_disp|None)。文件缺失/空/解析失败 ⇒ (False, None, None)。"""
    stale_hours = STALE_HOURS if stale_hours is None else stale_hours
    if not os.path.exists(BASELINE_LOG):
        return (False, None, None)
    rows = []
    with open(BASELINE_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if not rows:
        return (False, None, None)
    raw_ts = rows[-1].get("ts")
    try:
        ts = (datetime.fromtimestamp(raw_ts)
              if isinstance(raw_ts, (int, float))
              else datetime.fromisoformat(str(raw_ts)))
    except (ValueError, OSError):
        return (False, None, str(raw_ts))
    age_h = (datetime.now() - ts).total_seconds() / 3600.0
    return (age_h <= stale_hours, age_h, str(raw_ts))

# 性能相关 commit 关键词（bootstrap CI 归因用）——P0-1/P0-4/P1-1/P2-1/B1/B2 等
PERF_KEYWORDS = ("P0-1", "P0-4", "P1-1", "P2-1", "B1", "B2", "retry", "nudge",
                 "并行", "性能", "parallel", "nudge", "超时", "timeout", "压缩")

TURN_RE = re.compile(
    r"\[([0-9a-f]{8})\] turn (\d+): api=([\d.]+)s, (\d+) tools, total=([\d.]+)s"
)
EXIT_RE = re.compile(
    r"\[([0-9a-f]{8})\] \[EXIT\] reason=(\S+) turns=(\d+) has_written=(\S+)"
)

def _log_source_files():
    """D2（2026-11-08）：② ⑤ 共用同一数据源 = `agent.log*`（含轮转档）。"""
    return sorted(glob.glob(LOG_GLOB))


def _rotation_files():
    """轮转档 = `agent.log*` 中除当前主档之外的档（D2 收档范围的判据）。"""
    return [p for p in _log_source_files()
            if os.path.abspath(p) != os.path.abspath(LOG_FILE)]


def data_source_switch_note():
    """D2：数据源切换点（收档起点）标记——② 由单文件改为 glob 后的口径分界。

    返回可直接 append 进报告的行列表。无轮转档 ⇒ 未发生收档（仍是单文件口径）。
    """
    rot = _rotation_files()
    if not rot:
        return ["- 数据源切换点: **无**（当前仅 `agent.log` 单文件，尚未发生收档；"
                "② 与 ⑤ 同为单文件口径）"]
    stamps = []
    for p in rot:
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        stamps.append(datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S"))
                    except ValueError:
                        continue
        except OSError:
            continue
    if not stamps:
        return ["- 数据源切换点: 轮转档 %d 个但无可解析行（空档）⇒ 收档起点不可判定" % len(rot)]
    first, last = min(stamps), max(stamps)
    return [
        "- 数据源切换点（收档起点）: %s（轮转档 %d 个：%s；档内最新行 %s）"
        % (first.strftime("%Y-%m-%d %H:%M:%S"), len(rot),
           ", ".join(os.path.basename(p) for p in rot),
           last.strftime("%Y-%m-%d %H:%M:%S")),
        "- ② 历史序列在切换点前后**不可比**：切换前为单 `agent.log` 口径（只含未轮转部分），"
        "切换后含轮转档 ⇒ 同名指标（n / P50 / P95）是两套口径的拼接，禁跨切换点比大小",
    ]


def log_coverage_watermark():
    """档数水印（2026-11-08 第二刀）——治「轮转档被清 ⇒ n 回落被读成流量下降」。

    ②/⑤ 的 n 是**数据源可见范围**的函数：轮转档（agent.log.1/2/3）一旦被清理，
    同一 168h 窗口内 n 会回落。报告只印 n、不印「这次读到几档、最早一档起于何时」，
    读者就无法区分「流量下降」与「历史档被删」两种完全不同的原因。

    返回 (档数, 其中轮转档数, 最早可解析时间戳|None)；空目录 / 全空档 ⇒ (0, 0, None)。
    """
    files = _log_source_files()
    earliest = None
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        ts = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        continue
                    if earliest is None or ts < earliest:
                        earliest = ts
        except OSError:
            continue
    return len(files), len(_rotation_files()), earliest


def log_coverage_watermark_lines():
    """报告头水印行（两行：档数 / 最早档起点）——`grep -cE '档数|最早档起点'` 的落点。

    两行分开而不是并成一行：并成一行后 `grep -c` 只数到 1 行，读不出「两个字段都在」。
    """
    n_files, n_rot, earliest = log_coverage_watermark()
    if n_files == 0:
        return ["- 档数: 0（数据源为空目录——水印不可判定，②/⑤ 读数禁用）",
                "- 最早档起点: 无数据（无任何 agent.log* 档）"]
    if earliest is None:
        return ["- 档数: %d（agent.log* 档数，其中轮转档 %d 个）" % (n_files, n_rot),
                "- 最早档起点: 无数据（%d 档但无可解析时间戳行）" % n_files]
    return [
        "- 档数: %d（agent.log* 档数，其中轮转档 %d 个）" % (n_files, n_rot),
        "- 最早档起点: %s（本次读数覆盖边界——轮转档被清后同窗口 n 会回落，"
        "属口径变化，不是流量下降）" % earliest.strftime("%Y-%m-%d %H:%M:%S"),
    ]


def parse_log(days=7, anchor=None, hours=None):
    """解析滚动窗口内的 turn 行——返回 turn 记录列表 + 会话 turns 列表。

    D1（2026-11-08）：窗口 = 滚动小时窗（默认 168h），非日历日切点。
    D2（2026-11-08）：数据源 = `agent.log*`（含轮转档），与 ⑤ 同源。
    """
    turns = []   # (ts, api_s, n_tools, total_s)
    sessions = defaultdict(list)  # task_id -> [turn_num,...]
    anchor = anchor or datetime.now()
    cutoff = anchor - timedelta(hours=hours if hours is not None else window_hours(days))
    for line in _iter_log_lines():
        try:
            ts = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if ts < cutoff:
            continue
        m = TURN_RE.search(line)
        if m:
            tid, tnum, api, ntools, total = m.groups()
            turns.append((ts, float(api), int(ntools), float(total)))
            sessions[tid].append(int(tnum))
        m2 = EXIT_RE.search(line)
        if m2:
            tid, reason, tnum, hw = m2.groups()
            sessions.setdefault(tid, []).append(int(tnum))
    return turns, sessions


def parse_log_full():
    """解析全量 `agent.log*`（不按窗口截断）——用于 pre 基线回填（修复前数据）。"""
    turns = []
    for line in _iter_log_lines():
        try:
            ts = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        m = TURN_RE.search(line)
        if m:
            tid, tnum, api, ntools, total = m.groups()
            turns.append((ts, float(api), int(ntools), float(total)))
    return turns


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, int(len(sorted_vals) * p / 100))
    return sorted_vals[idx]

def stats_of(turns):
    """给定 turn 列表返回 (n, p50, p95, p99, mean) of total 延迟"""
    if not turns:
        return (0, 0.0, 0.0, 0.0, 0.0)
    totals = sorted(t[3] for t in turns)
    n = len(totals)
    return (n, percentile(totals, 50), percentile(totals, 95),
            percentile(totals, 99), sum(totals) / n)

def stat_cells(turns):
    """D1 全族（2026-09-30）：窗口无数据 ⇒ 统一印「无数据 / —」，禁印 0.0。

    D1（09-24）当年只补了「①」段，③ 段同族缺陷漏了 ⇒ 空窗口印 `0 | 0.0 | 0.0`，
    被下游读成「实测 0.0s」。同类风险全量扫 ⇒ 收敛成单一函数，各段一律调它。
    """
    n, p50, p95, p99, mean = stats_of(turns)
    if n == 0:
        return "无数据", ["—", "—", "—", "—"]
    return str(n), [f"{p50:.1f}", f"{p95:.1f}", f"{p99:.1f}", f"{mean:.1f}"]


BOOTSTRAP_SEED = 20260930
BOOTSTRAP_N = 1000
MIN_N_FOR_CI = 5


def bootstrap_ci(turns, p=95, n_boot=BOOTSTRAP_N, alpha=0.05, seed=BOOTSTRAP_SEED):
    """百分位 bootstrap 95% CI（默认 P95 区间）。无数据 ⇒ (None, None)。

    为什么必须真算：③ 段段名自称 bootstrap CI 却从未算过区间（2026-09-30 实证），
    而该段做的是**逐 commit 因果归因** —— 无区间时 commit 间 P95 差异
    与重采样噪声无法区分 ⇒ 归因结论不成立。
    seed 固定 ⇒ 同一份数据两次运行读数逐字一致（禁随机抖动被当成变化）。
    """
    vals = [t[3] for t in turns]
    if not vals:
        return (None, None)
    if len(vals) == 1:
        return (vals[0], vals[0])
    rnd = random.Random(seed)
    k = len(vals)
    draws = []
    for _ in range(n_boot):
        draws.append(percentile(sorted(vals[rnd.randrange(k)] for _ in range(k)), p))
    draws.sort()
    lo = draws[int(n_boot * alpha / 2)]
    hi = draws[min(n_boot - 1, int(n_boot * (1 - alpha / 2)))]
    return (lo, hi)


def _ci_cell(win):
    """③ 段 CI 单元：窗口不足 MIN_N_FOR_CI ⇒ 标不可靠，不印看着像结论的区间。"""
    if not win:
        return "—"
    if len(win) < MIN_N_FOR_CI:
        return f"—（n={len(win)}<{MIN_N_FOR_CI}）"
    lo, hi = bootstrap_ci(win)
    return f"[{lo:.1f}, {hi:.1f}]"


def git_perf_commits():
    """git log 拉性能相关 commit（时间戳 + subject），按时间升序"""
    try:
        out = subprocess.run(
            ["git", "-C", SRC_REPO, "log", "--format=%h|%ci|%s", "-100"],
            capture_output=True, text=True, timeout=10,
        )
        commits = []
        for line in out.stdout.splitlines():
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            h, ci, subject = parts[0], parts[1], parts[2]
            if any(kw in subject for kw in PERF_KEYWORDS):
                # %ci 格式: 2026-08-19 02:08:17 +0800 → 取前 19 字符为本地时间
                ts_str = ci[:19]
                try:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                commits.append((ts, h, subject[:70]))
        commits.sort(key=lambda x: x[0])
        return commits
    except Exception:
        return []

# ==================== 效率指标（2026-09-26 · 观测第 1 步） ====================
# 目的不是美化看板，而是让「单工具轮占比」「每轮 prompt token」两条
# 成为**可复算的回归指标** —— 此前无人量 ⇒ 钩子静默退化不可见。
LOG_GLOB = os.path.join(LOG_DIR, "agent.log*")
EFF_TURN_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) .*turn \d+: api=[\d.]+s, (\d+) tools, total=[\d.]+s"
)
CACHE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) .*\[S2-cache\] prompt=(\d+) ")


def _iter_log_lines():
    for path in sorted(glob.glob(LOG_GLOB)):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    yield line
        except OSError:
            continue


def _efficiency_stats(days=7, anchor=None, hours=None):
    """⑤ 效率统计 —— D1（2026-11-08）：窗口改滚动小时窗（与 ② 同界）。

    旧实现 `day >= (now-days).strftime('%Y-%m-%d')` 是**日历日切点**：窗口实际长度随钟点
    在 days*24h ~ (days+1)*24h 之间摆动，与 ② 的 168h 滚动不共界 ⇒ 两段读数天然不可比。
    """
    anchor = anchor or datetime.now()
    cutoff = anchor - timedelta(hours=hours if hours is not None else window_hours(days))
    turns, single, ptok = defaultdict(int), defaultdict(int), defaultdict(list)
    for line in _iter_log_lines():
        try:
            ts = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if ts < cutoff:
            continue
        day = ts.strftime("%Y-%m-%d")
        m = EFF_TURN_RE.match(line)
        if m:
            turns[day] += 1
            if int(m.group(2)) <= 1:
                single[day] += 1
            continue
        c = CACHE_RE.match(line)
        if c:
            ptok[day].append(int(c.group(2)))
    return turns, single, ptok


def efficiency_section(lines, days=7, hours=None, anchor=None):
    """⑤ 效率段（D1 2026-11-08：窗口 = 滚动小时窗，与 ② 同界）。"""
    hours = hours or window_hours(days)
    turns, single, ptok = _efficiency_stats(days, anchor=anchor, hours=hours)
    total, total_single = sum(turns.values()), sum(single.values())
    ratio = (total_single / total * 100) if total else None
    max_ratio = float(os.environ.get("MIMIR_SLO_SINGLE_TOOL_MAX", "50") or "50")

    lines.append("## ⑤ 效率指标（2026-09-26 观测第 1 步）")
    lines.append("")
    lines.append(f"### 单工具轮占比（近 {hours} 小时滚动窗口 · 目标 < {max_ratio:g}%）")
    lines.append("")
    if not total:
        lines.append("- **无数据**（窗口内无 turn 行）")
    else:
        verdict = "✅ 达标" if ratio < max_ratio else "❌ 未达标"
        lines.append(f"- 窗口: {total} 轮 · 单工具 {total_single} 轮 = **{ratio:.1f}%** ⇒ {verdict}")
        lines.append("")
        lines.append("| 日期 | 轮数 | 单工具轮 | 占比 |")
        lines.append("|:--|--:|--:|--:|")
        for day in sorted(turns):
            d = single.get(day, 0)
            lines.append(f"| {day} | {turns[day]} | {d} | {d / turns[day] * 100:.1f}% |")
    lines.append("")
    lines.append("### 每轮 prompt token（`[S2-cache] prompt=` 口径 · API 实测，非粗估）")
    lines.append("")
    ptok_flat = sorted(v for day in ptok for v in ptok[day])
    if not ptok_flat:
        lines.append("- **无数据**（窗口内无 S2-cache 行）")
    else:
        lines.append(
            f"- 窗口: {len(ptok_flat)} 个读数 · P50={percentile(ptok_flat,50)} · "
            f"P95={percentile(ptok_flat,95)} · mean={sum(ptok_flat)//len(ptok_flat)}"
        )
        lines.append("")
        lines.append("| 日期 | 读数 | P50 | P95 | mean |")
        lines.append("|:--|--:|--:|--:|--:|")
        for day in sorted(ptok):
            vals = sorted(ptok[day])
            lines.append(
                f"| {day} | {len(vals)} | {percentile(vals,50)} | "
                f"{percentile(vals,95)} | {sum(vals)//len(vals)} |"
            )
    lines.append("")


def hook_obs_section(lines):
    """钩子观测汇总（agent/hook_observe.py 落盘 · 2026-09-26 上线）。"""
    path = os.path.expanduser("~/.mimiraether/data/ops/hook_observations.jsonl")
    lines.append("## ⑥ 钩子观测（parallel-read nudge / PI delegate）")
    lines.append("")
    if not os.path.exists(path):
        lines.append(
            "- **无数据**（hook_observations.jsonl 不存在——该观测层自 2026-09-26 上线，"
            "只记录**新 run**；尚无事件 ≠ 钩子未生效）"
        )
        lines.append("")
        return
    counts, last_ts = Counter(), None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            counts[(rec.get("hook", "?"), rec.get("decision", "?"), rec.get("reason", "?"))] += 1
            last_ts = rec.get("ts") or last_ts
    if not counts:
        lines.append("- **无数据**（文件存在但无有效行）")
        lines.append("")
        return
    lines.append(f"- 累计 {sum(counts.values())} 条 · 末次 {last_ts or '不可解析'} · 数据源 {path}")
    lines.append("")
    lines.append("| 钩子 | 决策 | 原因 | 次数 |")
    lines.append("|:--|:--|:--|--:|")
    for (h, d, r), n in counts.most_common():
        lines.append(f"| {h} | {d} | {r} | {n} |")
    lines.append("")


def attribution_section(lines, commits, full_turns, pre_cutoff):
    """③ 逐 commit 归因（含真算的 bootstrap CI）。抽成函数 ⇒ 用例可喂合成数据。"""
    lines.append("## ③ bootstrap CI · 逐 commit 归因")
    lines.append("")
    lines.append(f"- 口径: P95 的 95% 百分位 bootstrap CI · {BOOTSTRAP_N} 次重采样 · "
                 f"seed={BOOTSTRAP_SEED} 固定（同数据两次运行读数逐字一致）")
    lines.append(f"- 窗口 = [该 commit 时间, 下一 commit 时间)；窗口 turns < {MIN_N_FOR_CI} ⇒ CI 不可靠，标 `—`")
    lines.append("")
    round_start = datetime(2026, 8, 19, 0, 0, 0)
    round_commits = [c for c in commits if c[0] >= round_start]
    if not round_commits:
        lines.append("- 本轮（2026-08-19 起）未发现性能相关 commit（git log 读取失败或关键词无命中）")
        lines.append("")
        return
    lines.append("| commit | 时间 | 窗口 turns | P50 | P95 | P95 95%CI | 说明 |")
    lines.append("|:--|:--|--:|--:|--:|:--|:--|")
    for i, (ts, h, subj) in enumerate(round_commits):
        end = round_commits[i + 1][0] if i + 1 < len(round_commits) else datetime.now()
        win = [t for t in full_turns if ts <= t[0] < end]
        n_disp, cells = stat_cells(win)
        lines.append(
            f"| `{h}` | {ts.strftime('%m-%d %H:%M')} | {n_disp} | {cells[0]} | {cells[1]} | "
            f"{_ci_cell(win)} | {subj} |"
        )
    pre_win = [t for t in full_turns if t[0] < pre_cutoff]
    n_disp, cells = stat_cells(pre_win)
    lines.append(
        f"| `pre` | < {pre_cutoff.strftime('%m-%d %H:%M')} | {n_disp} | {cells[0]} | {cells[1]} | "
        f"{_ci_cell(pre_win)} | 修复前基线 |"
    )
    lines.append("")


def _single_tool_ratio(days=7, hours=None, anchor=None):
    """⑤ 段与「对照」段共用同一读数与阈值 —— 两处各写一套 = 新造 D-1 同族（口径不一）。

    返回 (total, total_single, ratio_or_None, max_ratio)；ratio=None 表示窗口无数据。
    """
    hours = hours or window_hours(days)
    turns, single, _ptok = _efficiency_stats(days, anchor=anchor, hours=hours)
    total, total_single = sum(turns.values()), sum(single.values())
    ratio = (total_single / total * 100) if total else None
    max_ratio = float(os.environ.get("MIMIR_SLO_SINGLE_TOOL_MAX", "50") or "50")
    return total, total_single, ratio, max_ratio


def comparison_section(lines, days, session_turn_counts, hours=None, anchor=None):
    """对照（执行卡目标）—— D3（2026-09-30）：原为 3 行硬编码串，永不显示当前值。

    「402s/消息」**无对应量具**：本看板只按 turn 计时（秒/turn），而「消息」= 一次交互含 N 轮，
    单位不同 ⇒ 不做换算（换算 = 发明口径，正是 D-2 同族罪），显式标「无读数」。
    """
    lines.append("## 对照（执行卡目标）")
    lines.append("")
    hours = hours or window_hours(days)
    # 调用面保持 (days) 单位参数——既有用例以 lambda(days) 打桩，加 kwarg 会打断其契约；
    # 窗口小时数由 _single_tool_ratio 内部按同一 window_hours(days) 复算（同界，无需外传）。
    total, total_single, ratio, max_ratio = _single_tool_ratio(days)
    if ratio is None:
        lines.append(f"- 目标: 每轮工具数 1 → 2+ —— **无数据**（近 {hours} 小时内无 turn 行）")
    else:
        verdict = "✅ 达标" if ratio < max_ratio else "❌ 未达标"
        lines.append(f"- 目标: 每轮工具数 1 → 2+ —— 当前 单工具轮 **{ratio:.1f}%**"
                     f"（{total_single}/{total} 轮 · 阈值 < {max_ratio:g}%）⇒ {verdict}")
    over100 = sum(1 for t in session_turn_counts if t > 100)
    lines.append(f"- 目标: 无 >100 turns 失控会话 —— 当前 **{over100} 个** ⇒ "
                 + ("✅ 达标" if over100 == 0 else "❌ 未达标"))
    lines.append("- 目标: 402s/消息 → <150s（-63%）—— **无读数**（本看板无「消息」级量具："
                 "只有秒/turn；402s 为执行卡历史观测值，单位不同 ⇒ 禁直接换算）")
    lines.append("")


def main():
    days = int(os.environ.get("SLO_DAYS", "7"))
    hours = window_hours(days)          # D1（2026-11-08）：窗口 = 滚动 168h
    anchor = datetime.now()             # 窗口锚点（生成时刻）——全报告共用同一锚点
    window_start = anchor - timedelta(hours=hours)
    turns, sessions = parse_log(days, anchor=anchor, hours=hours)
    full_turns = parse_log_full()

    os.makedirs(OUT_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(OUT_DIR, f"{today}.md")

    # --- pre 基线（修复前）回填 ---
    # pre 基线 = P0-1 并行执行上线前（commit 8118353 @ 2026-08-19 02:08）的全部 turn
    # 精确定位：subject 同时含 "P0-1" 和 "并行"（避免命中旧 commit 的 "P0-1收敛审计" 等）
    pre_cutoff = None
    commits = git_perf_commits()
    for ts, h, subj in commits:
        if "P0-1" in subj and "并行" in subj:
            pre_cutoff = ts
            break
    if pre_cutoff is None:
        pre_cutoff = datetime(2026, 8, 19, 2, 8, 0)  # 兜底：8118353 P0-1 时间
    pre_turns = [t for t in full_turns if t[0] < pre_cutoff]

    api_sorted = sorted(t[1] for t in turns)
    total_sorted = sorted(t[3] for t in turns)
    tool_counts = Counter(t[2] for t in turns)
    session_turn_counts = [max(v) if v else 0 for v in sessions.values()]

    lines = []
    lines.append(f"# Mimir SLO 看板 v2 · {today}（近 {hours} 小时滚动窗口）")
    # D2（2026-09-24）：门禁状态位——供脚本/巡检按行解析，不靠肉眼
    lines.append(f"context_baseline_fresh={str(_context_baseline_freshness()[0]).lower()}")
    lines.append("")
    lines.append(f"- 窗口锚点（生成时刻）: {anchor.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 窗口区间: [{window_start.strftime('%Y-%m-%d %H:%M:%S')}, "
                 f"{anchor.strftime('%Y-%m-%d %H:%M:%S')}] = 滚动 {hours} 小时（非日历日切点）")
    lines.append(f"- 数据源: {LOG_GLOB}（D2 收档：含轮转档；滚动窗 turn 日志 {len(turns)} 条 / "
                 f"全量 {len(full_turns)} 条 / 会话 {len(sessions)} 个）")
    for _wm in log_coverage_watermark_lines():
        lines.append(_wm)
    lines.append("")

    # --- ① pre 基线回填段 ---
    lines.append("## ① pre 基线（修复前回填）")
    lines.append("")
    lines.append(f"- 定义: P0-1 并行执行上线前（< {pre_cutoff.strftime('%Y-%m-%d %H:%M')}）全部 turn——全量日志回填，非滚动窗截断")
    lines.append(f"- 首条日志: {full_turns[0][0].strftime('%Y-%m-%d %H:%M:%S') if full_turns else 'N/A'}（agent.log 最早可用）")
    lines.append("")
    n_pre, p50_pre, p95_pre, p99_pre, mean_pre = stats_of(pre_turns)
    n_now, p50_now, p95_now, p99_now, mean_now = stats_of(turns)
    lines.append("| 窗口 | turns | P50 | P95 | P99 | mean |")
    lines.append("|:--|--:|--:|--:|--:|--:|")
    # D1（2026-09-24）：无数据 ⇒ 印「无数据/—」，禁印 0.0（0.0 是有效读数，不是缺数据）
    n_disp, cells = stat_cells(pre_turns)
    lines.append(f"| pre（修复前） | {n_disp} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |")
    n_disp, cells = stat_cells(turns)
    lines.append(f"| 近 {hours} 小时滚动 | {n_disp} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |")
    if p50_pre > 0 and p50_now > 0:
        delta = (p50_now - p50_pre) / p50_pre * 100
        lines.append("")
        lines.append(f"- P50 变化: {p50_pre:.1f}s → {p50_now:.1f}s（{delta:+.1f}%）")
    lines.append("")

    # --- ② 近 168 小时滚动窗口段（D1/D2 2026-11-08：滚动小时窗 + 与 ⑤ 同源 glob）---
    lines.append(f"## ② 近 {hours} 小时滚动窗口（按天 · 数据源 agent.log*）")
    lines.append("")
    lines.append(f"- 窗口: 滚动 {hours} 小时 · 锚点 {anchor.strftime('%Y-%m-%d %H:%M:%S')} − {hours}h "
                 f"= {window_start.strftime('%Y-%m-%d %H:%M:%S')}（非日历日切点）")
    for _note in data_source_switch_note():
        lines.append(_note)
    lines.append("- n 跳变说明: 本段 n 自数据源切至 `agent.log*` 起**包含轮转档历史行** ⇒ "
                 "收档起点处 n 出现跳变；这是**口径变化不是流量突变**，跳变点前后 n 不可直接比较")
    _earliest = min((t[0] for t in turns), default=None)
    lines.append(f"- 实际最早计入行: {_earliest.strftime('%Y-%m-%d %H:%M:%S') if _earliest else '无数据'}"
                 f"（校验：≥ 窗口起点 ⇒ 确认按 {hours}h 滚动切窗，不是整日切点）")
    lines.append("")
    lines.append("| 日期 | turns | P50 | P95 | P99 | mean |")
    lines.append("|:--|--:|--:|--:|--:|--:|")
    day_groups = defaultdict(list)
    for t in turns:
        day_groups[t[0].strftime("%Y-%m-%d")].append(t)
    for d in sorted(day_groups):
        n_disp, cells = stat_cells(day_groups[d])
        lines.append(f"| {d} | {n_disp} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |")
    lines.append("")

    # --- ③ 逐 commit 归因（D-2 2026-09-30：真算 CI，抽成 attribution_section）---
    attribution_section(lines, commits, full_turns, pre_cutoff)

    # --- 每轮工具数分布 ---
    lines.append("## 每轮工具数分布")
    lines.append("")
    lines.append("| 工具数 | 次数 | 占比 |")
    lines.append("|--:|--:|--:|")
    total_turns = sum(tool_counts.values()) or 1
    for k in sorted(tool_counts):
        lines.append(f"| {k} | {tool_counts[k]} | {tool_counts[k]/total_turns*100:.1f}% |")
    lines.append("")

    # --- 会话 turns 分布 ---
    lines.append("## 会话 turns 分布")
    lines.append("")
    if session_turn_counts:
        st_sorted = sorted(session_turn_counts)
        lines.append(f"- 会话数: {len(st_sorted)}")
        lines.append(f"- turns/会话: P50={percentile(st_sorted,50)} P95={percentile(st_sorted,95)} P99={percentile(st_sorted,99)} max={max(st_sorted)}")
        lines.append(f"- 超 50 turns 会话: {sum(1 for t in st_sorted if t > 50)} 个")
        lines.append(f"- 超 80 turns 会话: {sum(1 for t in st_sorted if t > 80)} 个")
        lines.append(f"- 超 100 turns 会话: {sum(1 for t in st_sorted if t > 100)} 个")
    lines.append("")

    # --- ⑤⑥ 效率与钩子观测（2026-09-26 观测第 1 步） ---
    try:
        efficiency_section(lines, days=days, hours=hours, anchor=anchor)
        hook_obs_section(lines)
    except Exception as _exc:  # 观测段自身失败不得拖垮主报告
        lines.append("## ⑤ 效率指标（2026-09-26 观测第 1 步）")
        lines.append("")
        lines.append(f"- **段失败**（{type(_exc).__name__}: {_exc}）——读数不可用，勿当 0")
        lines.append("")

    # --- ④ Context Budget 维度（E4 治理——baseline 报告——每会话 token 基线） ---
    lines.append("## ④ Context Budget（E4 · always-loaded token 基线）")
    lines.append("")
    budget_rows = []
    if os.path.exists(BASELINE_LOG):
        with open(BASELINE_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    budget_rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if budget_rows:
        latest = budget_rows[-1]
        alert_th = int(os.environ.get("MIMIR_CONTEXT_BUDGET_ALERT", "150000"))
        over = alert_th > 0 and latest["total_tokens"] > alert_th
        # D2（2026-09-24）：新鲜度标注——陈旧 ⇒ 显式「数据陈旧」，不再静默当现值
        _fresh, _age_h, _ts_disp = _context_baseline_freshness()
        _age_disp = f"{_age_h:.1f} 小时前" if _age_h is not None else "时点不可解析"
        if _fresh:
            lines.append(f"- 最新测量: {latest['ts']}（距今 {_age_disp}）——always-loaded 基线 **{latest['total_tokens']} tokens**"
                         f"（{latest['total_chars']} bytes, bytes//4 粗口径·非 tokenizer 计数）")
        else:
            lines.append(f"- **⚠ 数据陈旧**: 最后测量 {latest['ts']}（距今 {_age_disp} > STALE_HOURS={STALE_HOURS:g}h）"
                         f"——数值 **不可当现值**：{latest['total_tokens']} tokens（{latest['total_chars']} bytes, bytes//4 粗口径·非 tokenizer 计数）")
        for label, v in latest["sources"].items():
            lines.append(f"  - {label}: {v['tokens']} tokens")
        lines.append(f"- 告警阈值: MIMIR_CONTEXT_BUDGET_ALERT={alert_th}"
                     + (" **⚠ 超阈值**" if over else "（未超）" if alert_th > 0 else "（关闭）"))
        if len(budget_rows) > 1:
            first = budget_rows[0]["total_tokens"]
            delta = (latest["total_tokens"] - first) / first * 100 if first else 0.0
            lines.append(f"- 基线漂移: 首测 {first} → 最新 {latest['total_tokens']}（{delta:+.1f}%"
                         f"——共 {len(budget_rows)} 次测量）")
        lines.append(f"- 数据源: {BASELINE_LOG}")
    else:
        lines.append("- **无数据**（context_baseline.jsonl 缺失或空——`scripts/context_baseline.py` 尚未运行）")
    lines.append("")

    # --- 对照（执行卡目标）（D-3 2026-09-30：改逐项实测读数）---
    comparison_section(lines, days, session_turn_counts, hours=hours, anchor=anchor)

    report = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\n报告已落盘: {out_path} ({os.path.getsize(out_path)} bytes)")

if __name__ == "__main__":
    main()
