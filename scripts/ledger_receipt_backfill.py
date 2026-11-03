#!/usr/bin/env python3
"""给台账「C 类」（无可跑判据）行**自动生成**判据，输出「可补 / 需降级」两类。

为什么是生成器而不是手写 34 条（2026-11-03）：
  C 类 34 行的症结不是「表述不全」，是**当年落盘时没有留下可复跑的钩子**。
  手写判据 = 事后造钩子，容易写成「看起来能跑、实际不校验任何东西」的假判据
  （本席同族事故：验收查字段存在性，而字段在降级路径上恒存在）。
  ⇒ 只从行内**已有字样**（commit sha / 文件路径）生成判据，且必须实测通过才收。

判定口径（每条都要实测，不猜）：
  sha   ：行内 `[0-9a-f]{7,40}` → 在 KNOWN_REPOS 里逐个 `git cat-file -e <sha>^{commit}`
  路径  ：行内 `~/...` 或 `/home/<user>/...` → `Path.exists()`
  产出 ：
    BACKFILLABLE  至少一条证据实测存在 → 生成 `重跑命令:` + `复算数字:` 两字段
    DOWNGRADE     零证据存在 → 建议降级为「已完成（无 L2 通道）」（按 AGENTS §8.6 状态四态）

两向自检（--selftest）：
  正控：人造行含「真 sha（HEAD）」→ 必须 BACKFILLABLE
  负控：人造行含「假 sha + 假路径」→ 必须 DOWNGRADE
  两控样本不同、期望不同、互不兼作（AGENTS §8.5 三条硬约束）

用法：
  python3 ledger_receipt_backfill.py --selftest
  python3 ledger_receipt_backfill.py            # 全 34 行
  python3 ledger_receipt_backfill.py --limit 10 # 只前 10 行（试点）
  python3 ledger_receipt_backfill.py --emit     # 输出可直接粘进台账的判据块
"""
import argparse
import os
import pwd
import re
import subprocess
import sys
from pathlib import Path

REAL_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)

LEDGER = REAL_HOME / "wiki/concepts/四方任务总台账.md"
SCAN = REAL_HOME / ".mimiraether/scripts/ledger_c_class_scan.py"
KNOWN_REPOS = [
    str(REAL_HOME / "src/MimirAether"),
    str(REAL_HOME / "wiki"),
    str(REAL_HOME / ".mimiraether"),
]
PY = str(REAL_HOME / "src/MimirAether/.venv/bin/python3")

SHA_RE = re.compile(r"\b([0-9a-f]{7,40})\b")
PATH_RE = re.compile(r"(~/[A-Za-z0-9_./\-]+|/home/[A-Za-z0-9_]+/[A-Za-z0-9_./\-]+)")


def c_rows(limit=0):
    """复用已锁口径的扫描器取**行号**，正文一律回台账原文按行号取。

    为什么不能直接用扫描器的文本输出（2026-11-03 踩坑）：
      扫描器为显示把每行截到 110 字符 ⇒ 生成器只看到半行 ⇒ commit/路径
      落在后半段时证据恒为 0 ⇒ 全部误判成「降级候选」。这是**假阴性**，
      同族事故：拿别人截断的输出当真相。
    """
    out = subprocess.run(
        [PY, str(SCAN), "--c-only"],
        capture_output=True, text=True, timeout=180,
    ).stdout
    ledger_lines = LEDGER.read_text(encoding="utf-8").splitlines()
    rows = []
    for ln in out.splitlines():
        m = re.match(r"^([AC]) L(\d+)\s+(\d{4}-\d{2}-\d{2})", ln)
        if m and m.group(1) == "C":
            n = int(m.group(2))
            rows.append({
                "line": n,
                "date": m.group(3),
                "text": ledger_lines[n - 1] if 0 < n <= len(ledger_lines) else "",
            })
    return rows[:limit] if limit else rows


def sha_exists(sha):
    for repo in KNOWN_REPOS:
        if not Path(repo, ".git").exists():
            continue
        r = subprocess.run(
            ["git", "-C", repo, "cat-file", "-e", f"{sha}^{{commit}}"],
            capture_output=True, timeout=30,
        )
        if r.returncode == 0:
            return repo
    return None


def path_exists(p):
    q = Path(p.replace("~", str(REAL_HOME), 1)) if p.startswith("~/") else Path(p)
    return q if q.exists() else None


def evaluate(text):
    """返回 (verdict, evidence) —— evidence = 实测存在的证据清单。"""
    ev = []
    for sha in dict.fromkeys(SHA_RE.findall(text)):
        repo = sha_exists(sha)
        if repo:
            ev.append(("sha", sha, repo))
    for p in dict.fromkeys(PATH_RE.findall(text)):
        hit = path_exists(p.rstrip(".,)`"))
        if hit:
            ev.append(("path", p, str(hit)))
    return ("BACKFILLABLE" if ev else "DOWNGRADE"), ev


def render(row, ev):
    """生成可粘台账的判据块（§8.4 两字段逐字）。"""
    cmds, nums = [], []
    for kind, val, where in ev[:3]:
        if kind == "sha":
            cmds.append(f"git -C {where} cat-file -t {val}")
            nums.append(f"{val} 应为 commit（rc=0）")
        else:
            cmds.append(f"test -e {val} && echo 1 || echo 0")
            nums.append("1")
    return (
        f"- L{row['line']}（{row['date']}）补判据：\n"
        f"  重跑命令: {' && '.join(cmds)}\n"
        f"  复算数字: {' / '.join(nums)}（证据 {len(ev)} 条实测存在）\n"
    )


def selftest():
    head = subprocess.run(
        ["git", "-C", str(REAL_HOME / "src/MimirAether"), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=30,
    ).stdout.strip()

    # 正控：含真 sha + 真路径
    pos_text = f"| 900 | 正控样本 | Mimir | L1 已自证 · 待复核 | 见 {head} 与 ~/src/MimirAether/AGENTS.md |"
    v_pos, ev_pos = evaluate(pos_text)

    # 负控：假 sha + 假路径（与正控样本不同）
    neg_text = "| 901 | 负控样本 | Mimir | L1 已自证 · 待复核 | 见 deadbeefcafe 与 ~/no/such/file-xyz.md |"
    v_neg, ev_neg = evaluate(neg_text)

    ok = (v_pos == "BACKFILLABLE" and v_neg == "DOWNGRADE")
    print(f"正控（真 sha {head[:7]} + 真路径）: {v_pos}  证据={len(ev_pos)}")
    print(f"负控（假 sha deadbeefcafe + 假路径）: {v_neg}  证据={len(ev_neg)}")
    print("VERDICT:", "PASS" if ok else "FAIL",
          "（两控样本不同/期望不同/互不兼作）" if ok else "")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--emit", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    rows = c_rows(a.limit)
    if not rows:
        print("C 类行数为 0（扫描器口径变化？先跑 ledger_c_class_scan.py --breakdown）")
        return 1

    n_ok = n_dg = 0
    emit = []
    for r in rows:
        verdict, ev = evaluate(r["text"])
        if verdict == "BACKFILLABLE":
            n_ok += 1
            mark = "✅可补"
            if a.emit:
                emit.append(render(r, ev))
        else:
            n_dg += 1
            mark = "⬇降级候选"
            if a.emit:
                emit.append(
                    f"- L{r['line']}（{r['date']}）**降级候选**：行内零证据实测存在"
                    f" ⇒ 建议状态改「已完成（无 L2 通道）」（AGENTS §8.6 弃权/降级语义，非免责）\n"
                )
        print(f"{mark}  L{r['line']:<5} {r['date']}  证据{len(ev)}  {r['text'][:70]}")

    print("-" * 70)
    print(f"total={len(rows)} BACKFILLABLE={n_ok} DOWNGRADE={n_dg}")
    if a.emit:
        sys.stdout.write("\n" + "".join(emit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
