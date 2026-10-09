#!/usr/bin/env python3
"""N13 段 2 · 八态转移引擎（第一批 = 只读：寻址 / plan 干跑 / 备份 / 恢复演练）

真源（唯一权威）：registry 卡内 `### N<x>` 块中的顶格 `state:` 行。
  · 块 = `### ` 行 → 下一个 `### ` 行（或 EOF）之间（F1 裁决 · 会卡 L908-910）
  · 块内顶格 `state:` 命中数 != 1 ⇒ 拒改 rc=2
  · 整文件匹配是错的：registry 卡有 11 条 state: ⇒「整文件唯一」永远拒改

第一批零写入生产卡：plan 只读 · backup 只写数据根备份目录 ·
restore --drill 恢复到临时副本核对（不写回生产卡）。
真写逻辑（Q1-Q6 / J1-J4 / J6-J8 / J10）属第二批。
零新依赖（json/hashlib/fcntl/os.replace 全 stdlib）· 零对外 · 零删除。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state_event_log import append_event, line_count  # noqa: E402


def _home():
    """与 state_watchdog.py / mimir_constants.get_mimir_home 同源。"""
    v = os.environ.get("MIMIR_AETHER_HOME") or os.environ.get("MIMIRAETHER_HOME")
    return v.strip() if v and v.strip() else os.path.expanduser("~/.mimiraether")


def _wiki():
    v = os.environ.get("MIMIR_WIKI_HOME")
    return v.strip() if v and v.strip() else os.path.expanduser("~/wiki")


DATA_DIR = os.path.join(_home(), "data")
DEFAULT_REGISTRY = os.path.join(
    _wiki(), "discussions/2026-10-08-NEW阶段-活卡状态机.md")
DEFAULT_EVENTS = os.path.join(DATA_DIR, "state-events.jsonl")
DEFAULT_BACKUP_DIR = os.path.join(DATA_DIR, "state-card-backups")
DEFAULT_ALERTS = os.path.join(DATA_DIR, "state-alerts.jsonl")

LIVE_STATES = (
    "pending", "in_progress", "awaiting_verify", "awaiting_decision",
    "awaiting_orchestrator", "awaiting_human", "stalled",
)
ALL_STATES = LIVE_STATES + ("closed", "frozen")

_BLOCK_RE = re.compile(r"^### ", re.M)
_STATE_RE = re.compile(r"^state:\s*(.*)$")
_HEAD_RE = re.compile(r"^###\s+(\S.*)$")
_NID_RE = re.compile(r"^###\s+(N\d+\w*)\b")


def _header_matches(head_text, card_id):
    """按「header 前缀 + 非字母数字边界」定位块。

    `--card N1` 命中 `### N1 ·` 但不命中 `### N10 ·`（下一个字符是数字）；
    `--card 分支区` 命中 `### 分支区（挂账…）`（下一个字符是「（」）。
    """
    m = _HEAD_RE.match(head_text)
    if not m:
        return False
    body = m.group(1)
    if not body.startswith(card_id):
        return False
    rest = body[len(card_id):]
    return rest == "" or not (rest[0].isalnum() or rest[0] == "_")


def split_blocks(text):
    """→ [(head_line_no(1-based), head_text, body_text, body_start_line_no)]"""
    heads = list(_BLOCK_RE.finditer(text))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        head_ln = text[:m.start()].count("\n") + 1
        nl = text.find("\n", m.start())
        head_text = text[m.start():nl if nl != -1 else len(text)]
        out.append((head_ln, head_text, text[m.end():end],
                    text[:m.end()].count("\n") + 1))
    return out


def locate_state_line(text, card_id):
    """块内唯一定位 ^state:。

    rc=0 唯一命中 · rc=2 块内 0 处或 >=2 处（拒改）· rc=1 卡不在册
    """
    block_head_line = None
    hits = []
    for head_ln, head_text, body, body_ln in split_blocks(text):
        if not _header_matches(head_text, card_id):
            continue
        block_head_line = head_ln
        for off, ln in enumerate(body.split("\n")):
            sm = _STATE_RE.match(ln)
            if sm:
                hits.append((body_ln + off, ln,
                             sm.group(1).strip().strip("'\"")))
        break
    if block_head_line is None:
        return {"card_id": card_id, "rc": 1, "hits": 0, "line_no": None,
                "line": None, "value": None, "block_head_line": None,
                "reason": "card not found"}
    if len(hits) != 1:
        return {"card_id": card_id, "rc": 2, "hits": len(hits),
                "line_no": None, "line": None, "value": None,
                "block_head_line": block_head_line,
                "reason": "block state hits=%d (need exactly 1) -> refuse"
                          % len(hits)}
    ln, line, val = hits[0]
    return {"card_id": card_id, "rc": 0, "hits": 1, "line_no": ln,
            "line": line, "value": val, "block_head_line": block_head_line,
            "reason": "ok"}


def _kv_of(body):
    kv = {}
    for ln in body.split("\n"):
        if not ln or ln[0] in " \t#-":
            continue
        if ":" not in ln:
            continue
        k, _, v = ln.partition(":")
        kv[k.strip()] = v.strip().strip("'\"")
    return kv


def parse_cards(text):
    """引擎管辖的 N 卡 → [{card_id, state, line_no, hits, depends_on, ...}]"""
    cards = []
    for head_ln, head_text, body, body_ln in split_blocks(text):
        m = _NID_RE.match(head_text)
        if not m:
            continue
        cid = m.group(1)
        loc = locate_state_line(text, cid)
        kv = _kv_of(body)
        cards.append({
            "card_id": cid, "state": loc["value"], "line_no": loc["line_no"],
            "block_head_line": head_ln, "hits": loc["hits"],
            "owner": kv.get("owner", ""), "deadline_raw": kv.get("deadline", ""),
            "title": kv.get("title", ""),
            "depends_on": kv.get("depends_on", ""),
            "blocked_by": kv.get("blocked_by", ""),
        })
    return cards


def _as_ids(v):
    """`[N1]     # 依赖 N1 的口径` / `[]` / `N1, N2` → ['N1'] / [] / ['N1','N2']。

    卡内真实写法带**行内注释**（会卡 L64）⇒ 先取 `[...]` 组，无组再按 `#` 截断；
    否则注释词会被当成卡 id（假 blocked）。
    """
    v = (v or "").strip()
    m = re.search(r"\[([^\]]*)\]", v)
    items = m.group(1) if m else v.split("#", 1)[0]
    return [x.strip().strip("'\"")
            for x in re.split(r"[,\s]+", items) if x.strip()]


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    with open(p, "rb") as fh:
        return sha256_bytes(fh.read())


def sha256_without_state_line(path, card_id):
    """「去掉本卡 state 行」后的 sha256（J1「只改一行」的同口径基线）。

    按行读 → 删掉该卡块内那条 state 行 → 其余字节原样拼接（不 strip/不重排）。
    """
    with open(path, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    loc = locate_state_line(raw, card_id)
    if loc["rc"] != 0:
        return None, loc
    lines = raw.split("\n")
    keep = [ln for i, ln in enumerate(lines, start=1) if i != loc["line_no"]]
    return sha256_bytes("\n".join(keep).encode("utf-8")), loc


def backup_card(card_path, card_id, *, backup_dir=None, reason="pre_write",
                actor="state_engine", dry_run=False):
    """先备份后写（fail-closed）：pre 镜像 + .manifest.jsonl 一行。只增。"""
    backup_dir = backup_dir or DEFAULT_BACKUP_DIR
    src = os.path.abspath(card_path)
    if not os.path.exists(src):
        return {"rc": 1, "error": "card file not found: %s" % src}
    sha = sha256_file(src)
    iso = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    d = os.path.join(backup_dir, card_id)
    dst = os.path.join(d, "%s.%s.%s.md" % (card_id, iso, sha[:8]))
    rec = {"ts": time.time(), "card_id": card_id, "src": src, "path": dst,
           "sha256": sha, "sha8": sha[:8], "reason": reason, "actor": actor,
           "bytes": os.path.getsize(src)}
    if dry_run:
        return {"rc": 0, "dry_run": True, "would_write": dst, "manifest": rec}
    try:
        os.makedirs(d, exist_ok=True)
        shutil.copyfile(src, dst)
        with open(os.path.join(d, ".manifest.jsonl"), "a",
                  encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as e:
        return {"rc": 1, "error": "backup failed: %r" % (e,),
                "fail_closed": True}
    return {"rc": 0, "path": dst, "sha256": sha, "manifest": rec}


def read_manifest(backup_dir, card_id):
    p = os.path.join(backup_dir, card_id, ".manifest.jsonl")
    out = []
    if not os.path.exists(p):
        return out
    for ln in open(p, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def restore_drill(backup_path, *, expect_sha=None, expect_state=None,
                  tmp_dir=None, card_id=None):
    """恢复演练：恢复到临时副本核对 —— 不写回生产卡。

    判据：sha256(restored) == manifest.sha256 ∧ state: == 改前值
    """
    if not os.path.exists(backup_path):
        return {"rc": 1, "error": "backup not found: %s" % backup_path}
    tmp_dir = tmp_dir or os.path.join(DEFAULT_BACKUP_DIR, ".drill")
    os.makedirs(tmp_dir, exist_ok=True)
    restored = os.path.join(tmp_dir, os.path.basename(backup_path) + ".restored")
    shutil.copyfile(backup_path, restored)
    got = sha256_file(restored)
    exp = expect_sha
    if exp is None:
        bdir = os.path.dirname(os.path.dirname(os.path.abspath(backup_path)))
        for rec in read_manifest(bdir, card_id or ""):
            if os.path.abspath(rec.get("path", "")) == os.path.abspath(backup_path):
                exp = rec.get("sha256")
                break
    sta = None
    if card_id:
        loc = locate_state_line(open(restored, encoding="utf-8").read(), card_id)
        sta = loc["value"]
    ok_sha = exp is not None and got == exp
    ok_state = expect_state is None or sta == expect_state
    os.remove(restored)
    return {"rc": 0 if (ok_sha and ok_state) else 1, "sha256_restored": got,
            "sha256_manifest": exp, "sha_match": ok_sha, "state": sta,
            "state_match": ok_state}


def locate_state_line_whole_file(text):
    """整文件口径（反例臂 · F1 会卡 L909 的失败模式）：命中 != 1 ⇒ rc=2。"""
    hits = [(i, ln) for i, ln in enumerate(text.split("\n"), 1)
            if _STATE_RE.match(ln)]
    if len(hits) != 1:
        return {"card_id": None, "rc": 2, "hits": len(hits), "line_no": None,
                "line": None, "value": None, "block_head_line": None,
                "reason": "whole-file state hits=%d (need exactly 1) -> refuse"
                          % len(hits)}
    return {"card_id": None, "rc": 0, "hits": 1, "line_no": hits[0][0],
            "line": hits[0][1], "value": hits[0][1].split(":", 1)[1].strip(),
            "block_head_line": None, "reason": "ok"}


def _count_state_lines(text):
    return sum(1 for ln in text.split("\n") if _STATE_RE.match(ln))


def plan_card(card, by_id, events_path):
    """逐卡算「将发生什么」（T1-T12 的可判子集）——只读。返回 (verdict, line)。

    verdict ∈ {WOULD（guard 过 ⇒ 第二批将推进）, NOOP（无自动转移）,
               blocked（被 guard / 前置拦住）}
    注意：段 2 的**真写**属第二批 ⇒ 本批所有 WOULD 都只是「清单」，
    零落盘（判据 J5）。
    """
    cid = card["card_id"]
    st = card["state"]
    if card["hits"] != 1:
        return "blocked", ("blocked: card=%s reason=block_state_hits_%d (need 1)"
                           % (cid, card["hits"]))
    if not st:
        return "blocked", ("blocked: card=%s reason=no_state_value" % cid)
    if st == "closed":
        return "NOOP", "NOOP: card=%s state=closed (terminal)" % cid
    if st == "frozen":
        return "NOOP", ("NOOP: card=%s state=frozen (FROZEN_REJECT: 自动转移全跳过)"
                        % cid)
    if st == "stalled":
        return "NOOP", ("NOOP: card=%s state=stalled (等 ack_received 回前态 · "
                        "段2 第二批)" % cid)
    if st == "pending":
        deps = _as_ids(card.get("depends_on"))
        open_deps = [d for d in deps
                     if by_id.get(d, {}).get("state") != "closed"]
        if open_deps:
            return "blocked", ("blocked: card=%s reason=deps_open=%s "
                               "(T2 guard 依赖全 closed · 未过)"
                               % (cid, ",".join(open_deps)))
        if (card.get("blocked_by") or "").strip():
            return "blocked", ("blocked: card=%s reason=blocked_by=%s"
                               % (cid, card["blocked_by"][:60]))
        return "WOULD", ("WOULD: card=%s from=pending --deps_all_closed--> "
                         "in_progress (guard: 依赖全 closed ∧ 无 blocked_by · "
                         "段2 第二批)" % cid)
    if st == "in_progress":
        return "NOOP", ("NOOP: card=%s state=in_progress (等 produces_persisted · "
                        "无自动转移)" % cid)
    if st in ("awaiting_verify", "awaiting_decision", "awaiting_orchestrator",
              "awaiting_human"):
        return "NOOP", ("NOOP: card=%s state=%s (等人/等证态 · 无自动转移)"
                        % (cid, st))
    return "blocked", ("blocked: card=%s reason=unknown_state_%r" % (cid, st))


def cmd_plan(args):
    if not os.path.exists(args.registry):
        print("ERROR: registry not found: %s" % args.registry)
        return 1
    text = open(args.registry, encoding="utf-8").read()
    cards = parse_cards(text)
    if args.card:
        if args.card not in [c["card_id"] for c in cards]:
            print("ERROR: card not found: %s" % args.card)
            return 1
        cards = [c for c in cards if c["card_id"] == args.card]
    by_id = {c["card_id"]: c for c in cards}
    n_w = n_n = n_b = 0
    for c in cards:
        v, line = plan_card(c, by_id, args.events)
        print(line)
        n_w += v == "WOULD"
        n_n += v == "NOOP"
        n_b += v == "blocked"
    print("plan: scanned=%d would_move=%d noop=%d blocked=%d"
          % (len(cards), n_w, n_n, n_b))
    return 0


def cmd_locate(args):
    text = open(args.registry, encoding="utf-8").read()
    loc = (locate_state_line_whole_file(text) if args.whole_file
           else locate_state_line(text, args.card))
    print(json.dumps(loc, ensure_ascii=False))
    return loc["rc"]


def cmd_list(args):
    for c in parse_cards(open(args.registry, encoding="utf-8").read()):
        print("%-4s line=%-4s state=%-20s owner=%s"
              % (c["card_id"], c["line_no"], c["state"], c["owner"]))
    return 0


def cmd_backup(args):
    r = backup_card(args.card_file, args.card, backup_dir=args.backup_dir,
                    reason=args.reason, actor=args.actor, dry_run=args.dry_run)
    print(json.dumps(r, ensure_ascii=False))
    return r["rc"]


def cmd_restore(args):
    if not args.drill:
        print("ERROR: 第一批只实现 --drill（真回滚属第二批）")
        return 1
    r = restore_drill(args.backup, expect_sha=args.expect_sha,
                      expect_state=args.expect_state, card_id=args.card)
    print(json.dumps(r, ensure_ascii=False))
    if r["rc"] == 0:
        print("DRILL OK card=%s sha=%s state=%s"
              % (args.card, r["sha256_restored"][:8], r.get("state")))
    else:
        print("DRILL FAIL card=%s sha_match=%s state_match=%s"
              % (args.card, r.get("sha_match"), r.get("state_match")))
    return r["rc"]


def apply_transition(card_id, event, actor, trace_id, guard_passed):
    """唯一写卡入口（**第二批** · 段 3 也走这里）。本批不接真写路径。"""
    if not guard_passed:
        return {"verdict": "refused", "rc": 5, "reason": "guard not passed"}
    return {"verdict": "not_implemented", "rc": 90,
            "reason": "第一批为只读 · 真写逻辑属第二批"}


def selftest(registry=None, events=None):
    """J5 / J9 两向判据 —— **全部走真实调用路径**（真实 registry 卡 · 不构造输入）。

    负控臂：
      · 块内 0 处 —— 真实 registry 里的两个真实块 `### 分支区（…）` /
        `### 【挂起 …】`（无 state 行）
      · 命中 >1 —— 真实 registry 整文件（11 条 state:）
      · 卡不在册 —— N99
    """
    reg = registry or DEFAULT_REGISTRY
    ok = True
    text = open(reg, encoding="utf-8").read()

    print("== J9 寻址正确（正控：块内唯一 ⇒ 能定位） ==")
    loc = locate_state_line(text, "N3")
    good = (loc["rc"] == 0 and loc["hits"] == 1
            and loc["value"] == "awaiting_decision")
    print("[J9 正控] locate --card N3 -> rc=%d hits=%d line_no=%s value=%s -> %s"
          % (loc["rc"], loc["hits"], loc["line_no"], loc["value"],
             "PASS" if good else "FAIL"))
    ok = ok and good

    print("== J9 寻址正确（负控 1：真实块内 0 处 ⇒ 拒改 rc=2） ==")
    for cid, tag in (("分支区", "分支区块"), ("【挂起", "挂起块")):
        loc = locate_state_line(text, cid)
        good = loc["rc"] == 2 and loc["hits"] == 0
        print("[J9 负控1/%s] locate --card %r -> rc=%d hits=%d "
              "block_head_line=%s reason=%s -> %s"
              % (tag, cid, loc["rc"], loc["hits"], loc["block_head_line"],
                 loc["reason"], "PASS" if good else "FAIL"))
        ok = ok and good

    print("== J9 寻址正确（负控 2：命中 >1 ⇒ 拒改 rc=2） ==")
    loc = locate_state_line_whole_file(text)
    good = loc["rc"] == 2 and loc["hits"] == _count_state_lines(text)
    print("[J9 负控2] locate --whole-file -> rc=%d hits=%d reason=%s -> %s"
          % (loc["rc"], loc["hits"], loc["reason"], "PASS" if good else "FAIL"))
    ok = ok and good

    print("== J9 寻址正确（负控 3：卡不在册 ⇒ rc=1） ==")
    loc = locate_state_line(text, "N99")
    good = loc["rc"] == 1
    print("[J9 负控3] locate --card N99 -> rc=%d reason=%s -> %s"
          % (loc["rc"], loc["reason"], "PASS" if good else "FAIL"))
    ok = ok and good

    print("== 边界：块前缀不误撞（N1 不得命中 N10/N11/N12） ==")
    loc = locate_state_line(text, "N1")
    good = loc["rc"] == 0 and loc["line_no"] == 46
    print("[J9 边界] locate --card N1 -> rc=%d line_no=%s (期望 46) -> %s"
          % (loc["rc"], loc["line_no"], "PASS" if good else "FAIL"))
    ok = ok and good

    print("== 自洽不变量：卡数 == 顶格 state 行数（寻址无遗漏/无重复） ==")
    cards = parse_cards(text)
    n = _count_state_lines(text)
    good = len(cards) == n and n > 0 and all(c["hits"] == 1 for c in cards)
    print("[不变量] cards=%d state_lines=%d all_hits==1=%s -> %s"
          % (len(cards), n, all(c["hits"] == 1 for c in cards),
             "PASS" if good else "FAIL"))
    ok = ok and good

    print("== J5 dry-run 零落盘（正控：plan --all 出清单） ==")
    rc = cmd_plan(argparse.Namespace(registry=reg, card=None,
                                    events=events or DEFAULT_EVENTS))
    print("[J5 正控] plan --all rc=%d -> %s" % (rc, "PASS" if rc == 0 else "FAIL"))
    ok = ok and rc == 0

    print("== J5 dry-run（负控：真实不存在的卡 ⇒ rc=1 + ERROR: card not found） ==")
    rc = cmd_plan(argparse.Namespace(registry=reg, card="N99",
                                     events=events or DEFAULT_EVENTS))
    good = rc == 1
    print("[J5 负控] plan --card N99 rc=%d -> %s"
          % (rc, "PASS" if good else "FAIL"))
    ok = ok and good

    print("[selftest] rc=%d" % (0 if ok else 1))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="N13 段2 八态转移引擎（第一批=只读）")
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    ap.add_argument("--events", default=DEFAULT_EVENTS)
    ap.add_argument("--backup-dir", default=DEFAULT_BACKUP_DIR)
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("plan")
    p.add_argument("--all", action="store_true")
    p.add_argument("--card")
    l = sub.add_parser("locate")
    l.add_argument("--card")
    l.add_argument("--whole-file", action="store_true")
    sub.add_parser("list")
    b = sub.add_parser("backup")
    b.add_argument("--card", required=True)
    b.add_argument("--card-file", required=True)
    b.add_argument("--reason", default="pre_write")
    b.add_argument("--actor", default="state_engine")
    b.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("restore")
    r.add_argument("--card", required=True)
    r.add_argument("--backup", required=True)
    r.add_argument("--drill", action="store_true")
    r.add_argument("--expect-sha")
    r.add_argument("--expect-state")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest(args.registry, args.events)
    if args.cmd == "plan":
        return cmd_plan(args)
    if args.cmd == "locate":
        return cmd_locate(args)
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "backup":
        return cmd_backup(args)
    if args.cmd == "restore":
        return cmd_restore(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
