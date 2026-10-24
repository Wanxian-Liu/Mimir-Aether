#!/usr/bin/env python3
"""信箱 state=unknown 的三类反查器（S3 回填后的可复算判据）。

用途
----
`buzz-inbox-mimir.jsonl` 在 2026-10-24 S3 回填后，76 条历史件全部落成 ``state: unknown``
（原因：claim.log 行号纪元不可判定 ⇒ 不猜 processed）。本工具**不猜**，只做一件事：
对每条 unknown 件去**盘上证据面**找可机检的完成凭证，判成三类：

- ``DONE``      — 在 [ts, ts+WINDOW] 内找到**同主题**产出凭证（回执/卡片/commit），
                  ``evidence`` 给出 ``kind:path``（commit 给 sha）
- ``NOT-DONE``  — 该时间窗内**全盘零活动**（无回执、无卡片、无 commit）⇒ 明确没做
- ``UNKNOWN``   — 窗内有活动但主题不匹配 / 证据链断裂 ⇒ ``missing`` 写明缺哪一项证据

设计纪律（工程规范：幂等 / 显式契约 / 空值显式）
------------------------------------------------
- **证据按「内容日期」而非 mtime**：卡/回执的 mtime 会被整仓 checkout 刷新（2026-10-24 12:57
  全仓 mtime 同刻 = 实测假证据源）⇒ 证件时间取 文件名 `YYYY-MM-DD` 前缀 > 该文件首次 commit
  时间 > mtime（最后一档在输出里显式标 ``mtime:``，提示弱证据）。
- **主题词按 DF 过滤**：在 76 条件里出现率 > DF_MAX 的词（派单/回执/Mimir…）不参与匹配，
  否则「Mimir」一词就能把任一件判成 DONE（实测：漏筛时 DONE=73/76 = 假绿）。
- **幂等**：输出只依赖输入文件内容与日期，不含运行时刻；``--check-idempotent`` 跑两次比对指纹。
- **空值显式**：判不出的**绝不**塞 DONE，一律 UNKNOWN + missing 说明（防「假装处置干净」）。
- **只读**：绝不写收件箱。

用法
----
    python3 scripts/inbox_state_audit.py                 # 三类计数 + 每条一行
    python3 scripts/inbox_state_audit.py --json          # 机器读
    python3 scripts/inbox_state_audit.py --check-idempotent   # 跑两次比对指纹
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
INBOX = HOME / ".openclaw/data/buzz-inbox-mimir.jsonl"
RECEIPTS = HOME / ".hermes/inbox"
CARDS = HOME / "wiki/discussions"
LEDGER = HOME / "wiki/concepts/四方任务总台账.md"
REPOS = [HOME / "wiki", HOME / "src/MimirAether"]

WINDOW_S = 48 * 3600          # 件到达后 48h 内算「同一响应窗口」
MIN_HITS = 2                  # 主题命中阈值（去重后的有效词交集 ≥2）
DF_MAX = 0.20                 # 出现率 >20% 的词视为泛词，不参与匹配

STOP = set("""请 的 了 与 和 及 或 在 是 不 要 你 我 他 本 单 件 后 前 先 再 一 二 三 四 五
任务 派单 回执 非 新 政 续 做 修正 卡 页 席 轮 条 项 已 未 从 到 为 按 此 该 并 且 就 都 也
mimir hermes loki openclaw 文曲星 只读 口径 判据 落盘 追加 同一 不重
the a an of to in for on and or is are be with by at as it this that""".split())

CJK = re.compile(r"[\u4e00-\u9fff]{2,}")
LAT = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{2,}")
NUM = re.compile(r"\b\d{2,}\b")
DATE_PREFIX = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def keywords(text: str, cap: int = 24):
    """抽取主题词：CJK 2+ 字片段（长段切 3 字窗）、拉丁 3+ 词、数字串；保序去重。"""
    toks = []
    for m in CJK.findall(text):
        if len(m) <= 4:
            toks.append(m)
        else:
            toks.extend(m[i:i + 3] for i in range(0, len(m) - 2, 2))
    toks.extend(LAT.findall(text))
    toks.extend(NUM.findall(text))
    out, seen = [], set()
    for t in toks:
        t = t.strip("-—·")
        if len(t) < 2 or t.lower() in STOP or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= cap:
            break
    return out


def _git_first_commit_ts(repo: Path, rel: str):
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "--diff-filter=A", "--pretty=%ct", "--", rel, "-n", "1"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        return float(out.splitlines()[-1]) if out else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def content_ts(p: Path):
    """证件时间 + 粒度。返回 (t_lo, t_hi, how)。

    粒度纪律：文件名只有 ``YYYY-MM-DD`` ⇒ 该件覆盖**整日** ``[day0, day0+86400)``，
    否则同日 12:59 到达的单会被 12:05 落盘的回执判成「不在窗内」（实测假阴性）。
    """
    m = DATE_PREFIX.match(p.name)
    if m:
        try:
            day0 = _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).timestamp()
            return day0, day0 + 86400.0, "name-date"
        except ValueError:
            pass
    ts = _git_first_commit_ts(HOME / "wiki", str(p.relative_to(HOME / "wiki"))) if str(p).startswith(str(HOME / "wiki")) else None
    if ts:
        return ts, ts, "git-first-commit"
    mt = p.stat().st_mtime
    return mt, mt, "mtime"


def load_corpus():
    """产出 [(kind, ref, ts, dating, text)] —— 只读、确定性排序。"""
    items = []
    for p in sorted(RECEIPTS.glob("*.md")):
        try:
            lo, hi, how = content_ts(p)
            items.append(("receipt", str(p), lo, hi, how, p.read_text(errors="replace")))
        except OSError:
            pass
    for p in sorted(CARDS.rglob("*.md")):
        try:
            lo, hi, how = content_ts(p)
            items.append(("card", str(p), lo, hi, how, p.read_text(errors="replace")[:20000]))
        except OSError:
            pass
    if LEDGER.exists():
        # 台账按**行**喂证据面：整篇喂会把任一主题词撞进无关行（实测假绿源）
        for ln_no, ln in enumerate(LEDGER.read_text(errors="replace").splitlines(), 1):
            if not ln.strip():
                continue
            mt = LEDGER.stat().st_mtime
            items.append(("ledger", f"{LEDGER}:{ln_no}", mt, mt, "mtime", ln))
    for repo in REPOS:
        if not (repo / ".git").exists():
            continue
        try:
            out = subprocess.run(
                ["git", "-C", str(repo), "log", "--pretty=%h\t%ct\t%s", "-n", "500"],
                capture_output=True, text=True, timeout=60,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        for ln in out.splitlines():
            parts = ln.split("\t", 2)
            if len(parts) == 3:
                sha, ct, subject = parts
                ctt = float(ct)
                items.append(("commit", f"{repo.name}:{sha}", ctt, ctt, "commit-date", subject))
    items.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    return items


def read_inbox(inbox: Path):
    rows = []
    for i, line in enumerate(inbox.read_text(errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = rec.get("ts")
        ts = float(ts) / 1000.0 if isinstance(ts, (int, float)) and ts > 1e11 else float(ts or 0)
        rows.append((i, rec, ts))
    return rows


def audit(inbox: Path = INBOX, corpus=None, window_s: int = WINDOW_S):
    corpus = corpus if corpus is not None else load_corpus()
    entries = read_inbox(inbox)
    # --- DF 过滤：泛词不参与匹配 ---
    kw_list = [keywords((rec.get("content") or "")[:400]) for _, rec, _ in entries]
    df = {}
    for kws in kw_list:
        for k in set(kws):
            df[k] = df.get(k, 0) + 1
    n = max(len(entries), 1)
    generic = {k for k, c in df.items() if c / n > DF_MAX}

    rows = []
    for (i, rec, ts), kws_all in zip(entries, kw_list):
        if rec.get("state") != "unknown":
            continue
        kws = [k for k in kws_all if k not in generic]
        # 短内容件（内容只是一个文件名，如 m4 status 推送）主题词天然少 ⇒ 阈值按可用词数收缩，
        # 否则「内容 1 个词」的件永远够不到 MIN_HITS=2（实测假阴性 3 条）
        need = min(MIN_HITS, max(len(kws), 1)) if kws else 99
        content = rec.get("content") or ""
        title = content.split("\n", 1)[0][:60]
        best, best_hits, activity = None, 0, 0
        for kind, ref, lo, hi, how, text in corpus:
            if hi < ts or lo > ts + window_s:      # 区间不重叠 ⇒ 不在同一响应窗
                continue
            activity += 1
            # 证据面 = 正文 + 件名/路径：交付件命名本身即主题声明（卡名含「小修三件」就是凭证）
            hay = text + " " + ref
            hits = sum(1 for k in kws if k in hay)
            if hits > best_hits:
                best, best_hits = (kind, ref, lo, how), hits
        if best and kws and best_hits >= need:
            verdict = "DONE"
            evidence = f"{best[0]}:{best[1]}" + (" (mtime)" if best[3] == "mtime" else "")
            missing = ""
        elif activity == 0:
            verdict = "NOT-DONE"
            evidence = ""
            missing = "窗内零活动（无回执/卡片/commit）"
        else:
            verdict = "UNKNOWN"
            evidence = f"weak:{best[0]}:{best[1]}" if best else ""
            missing = (f"窗内有 {activity} 条活动但主题命中 <{need}"
                       f"（best_hits={best_hits}，可用主题词 {len(kws)} 个）⇒ 缺「本单产出件」这一项证据")
        rows.append({
            "line": i, "id": rec.get("id", ""), "ts": int(ts), "title": title,
            "verdict": verdict, "evidence": evidence, "missing": missing,
            "score": best_hits, "kws": kws[:8],
        })
    counts = {k: sum(1 for r in rows if r["verdict"] == k) for k in ("DONE", "NOT-DONE", "UNKNOWN")}
    return rows, counts, {"generic_dropped": sorted(generic)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="信箱 unknown 三类反查（只读）")
    ap.add_argument("--inbox", default=str(INBOX))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check-idempotent", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)

    inbox = Path(a.inbox)
    if not inbox.exists():
        print(f"rc=2 收件箱不存在: {inbox}", file=sys.stderr)
        return 2
    rows, counts, meta = audit(inbox)

    if a.check_idempotent:
        h1 = hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        rows2, _, _ = audit(inbox)
        h2 = hashlib.sha256(json.dumps(rows2, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        print(f"IDEMPOTENT run1={h1[:12]} run2={h2[:12]} equal={h1 == h2}")
        return 0 if h1 == h2 else 1

    if a.json:
        print(json.dumps({"counts": counts, "rows": rows, "meta": meta}, ensure_ascii=False, indent=1))
        return 0

    print(f"# 信箱 unknown 三类反查  inbox={inbox}")
    print(f"# 口径: 窗={WINDOW_S // 3600}h · 命中阈值={MIN_HITS} · DF>{DF_MAX:.0%} 词已剔 "
          f"({len(meta['generic_dropped'])} 个) · 不猜 processed")
    for r in rows:
        tail = r["evidence"] or r["missing"]
        line = f"L{r['line']:>3} {r['verdict']:<8} score={r['score']} | {r['title'][:32]:<32} | {tail[:88]}"
        if a.verbose:
            line += f"\n      kws={r['kws']}"
        print(line)
    print(f"\nDONE={counts['DONE']} NOT-DONE={counts['NOT-DONE']} UNKNOWN={counts['UNKNOWN']} "
          f"SUM={sum(counts.values())}")
    print("重跑命令: ~/src/MimirAether/.venv/bin/python3 ~/src/MimirAether/scripts/inbox_state_audit.py")
    print(f"复算数字: DONE={counts['DONE']} NOT-DONE={counts['NOT-DONE']} "
          f"UNKNOWN={counts['UNKNOWN']} SUM={sum(counts.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
