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
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state_event_log import append_event, line_count, replay  # noqa: E402


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
    if val not in ALL_STATES:
        return {"card_id": card_id, "rc": RC_INVALID_STATE, "hits": 1,
                "line_no": ln, "line": line, "value": val,
                "block_head_line": block_head_line,
                "reason": "invalid state value %r (P-1 whitelist: %s)"
                          % (val, "|".join(ALL_STATES))}
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
            "has_depends_on": "depends_on" in kv,
            "has_blocked_by": "blocked_by" in kv,
            "gate": kv.get("gate", ""),
            "state_value_ok": loc["rc"] == 0 and state_value_ok(loc["value"]),
            "state_hits": loc["hits"],   # N13 段3 · G2：块内 state 行数（!=1 出声）
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
    ln, line = hits[0]
    val = line.split(":", 1)[1].strip().strip("'\"")
    if val not in ALL_STATES:      # N13 段3 · G1：整文件口径补值白名单
        return {"card_id": None, "rc": RC_INVALID_STATE, "hits": 1,
                "line_no": ln, "line": line, "value": val,
                "block_head_line": None,
                "reason": "invalid state value %r (P-1 whitelist: %s)"
                          % (val, "|".join(ALL_STATES))}
    return {"card_id": None, "rc": 0, "hits": 1, "line_no": ln,
            "line": line, "value": val,
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
    if not card.get("state_value_ok", True):
        return "blocked", ("blocked: card=%s reason=invalid_state_%r "
                           "(P-1 value whitelist)" % (cid, st))
    if st == "closed":
        return "NOOP", "NOOP: card=%s state=closed (terminal)" % cid
    if st == "frozen":
        return "NOOP", ("NOOP: card=%s state=frozen (FROZEN_REJECT: 自动转移全跳过)"
                        % cid)
    if st == "stalled":
        return "NOOP", ("NOOP: card=%s state=stalled (等 ack_received 回前态 · "
                        "段2 第二批)" % cid)
    if st == "pending":
        if (card.get("gate") or "").strip():
            return "blocked", ("blocked: card=%s reason=gate_open "
                               "(P-2: gate 非空 = 人工挂起, fail-closed)" % cid)
        if not card.get("has_depends_on", False):
            return "blocked", ("blocked: card=%s reason=depends_on_missing "
                               "(P-2: 字段缺失 != 显式空依赖, fail-closed)" % cid)
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
        return 2
    text = open(args.registry, encoding="utf-8").read()
    cards = parse_cards(text)
    rc_pf, msg = preflight_registry(args.registry, cards)
    if rc_pf != 0:
        print(msg)
        return rc_pf
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
    text = open(args.registry, encoding="utf-8").read()
    cards = parse_cards(text)
    rc_pf, msg = preflight_registry(args.registry, cards)
    if rc_pf != 0:
        print(msg)
        return rc_pf
    for c in cards:
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

    print("== 段2 批2 追加臂（P-1 值白名单 / P-2 外域出声 / P-3 真写+演练） ==")
    ok = _selftest_batch2(reg) and ok

    print("== 段3 追加臂（G1 值白名单全路径 / G2 出声 / G3 停止令验签 / G4 可撤+留痕） ==")
    ok = _selftest_seg3(reg) and ok

    print("[selftest] rc=%d" % (0 if ok else 1))
    return 0 if ok else 1


# ===== N13 段2 批2 注入块（BEGIN） =====
# -*- coding: utf-8 -*-
"""N13 段2 批2 · 真转移引擎 —— 注入块（由 state_patch_apply.py 追加进 state_engine.py）

内容 = P-1 值白名单 / P-2 外域出声 / P-3 preflight + 真 apply_transition（原子写 /
写后双校 / 失败回滚 / 幂等 / CAS / frozen 拒写 / T 表白名单）/ 真回滚 / CLI。
零新依赖（stdlib）· 零删除 · 只替换 apply_transition 空壳 + main() 路由。
"""

# ===== 段2 批2 追加常量 =====

RC_TABLE_DENY = 9          # 转移不在 T 表白名单内（GUARD_DENY）
RC_INVALID_STATE = 6       # 值不在九态白名单（P-1）

# T 表（真源：预置卡 L738-751）—— 本引擎管「写 state 行」的子集。
T_TRANSITIONS = {
    ("pending", "deps_all_closed"): "in_progress",            # T2
    ("in_progress", "produces_persisted"): "awaiting_verify",  # T3
    ("awaiting_verify", "L2_passed"): "closed",                # T4
    ("awaiting_verify", "L2_failed"): "in_progress",           # T5
    ("awaiting_orchestrator", "orchestrator_no_reply"): "awaiting_human",  # T7
}
# 任意 from 态的事件（T8/T11：超时沉默 / 舵手停令）
ANY_FROM_EVENTS = {
    "deadline_exceeded": "stalled",   # T8
    "liuge.says.stop": "frozen",      # T11（停）
    "freeze": "frozen",               # T11 别名
}
# 目标由调用方给定（回前态语境），但目标值仍须过九态白名单
FREE_FROM_EVENTS = ("ack_received", "liuge.says.start", "unfreeze")  # T9/T12


# ===== P-1 · state 值白名单（Loki 10-10 实证：malicious_value 曾 rc=0） =====

class StateValueError(ValueError):
    """非法 state 值（不在九态白名单内）。"""


def validate_state_value(value):
    """值合法性闸（P-1）。返回归一化值；非法 ⇒ raise StateValueError。

    与「位置闸」正交：locate_state_line 管「哪一行」，本函数管「值合不合法」。
    """
    v = (value or "").strip().strip("'\"")
    if v not in ALL_STATES:
        raise StateValueError(
            "illegal state value %r (allowed: %s)"
            % (value, "|".join(ALL_STATES)))
    return v


def state_value_ok(value):
    try:
        validate_state_value(value)
        return True
    except StateValueError:
        return False


def resolve_transition(cur, event, to_state):
    """T 表白名单闸。返回 (ok, reason)。

    白名单外（T3→T99 之类）⇒ ok=False ⇒ 调用方 rc=9 拒改 + GUARD_DENY 报警。
    """
    if event in FREE_FROM_EVENTS:
        if cur == "frozen" and event == "ack_received":
            return False, "ack_received not allowed on frozen card"
        return True, "free"
    want = ANY_FROM_EVENTS.get(event) or T_TRANSITIONS.get((cur, event))
    if want is None:
        return False, "transition not in whitelist: from=%s event=%s" % (cur, event)
    if to_state != want:
        return False, "target mismatch: event=%s wants=%s got=%s" % (event, want,
                                                                    to_state)
    return True, "ok"


# ===== P-2 · 外域 / 空扫出门（与 watchdog preflight_guard 对称） =====

def preflight_registry(registry, cards):
    """前置闸（出声）：registry 不存在 / 扫到 0 张卡 / 卡与 state 行数不等 ⇒ rc!=0。

    防的事故（Mimir 10-10 自曝 · 审计会裁定采纳）：把引擎指向别的 registry 或
    格式漂移时，它报 scanned=0 且 rc=0 —— 静默 0，无人知道它什么都没扫到。
    """
    if not os.path.exists(registry):
        return 2, "ERROR: registry not found: %s" % registry
    if not cards:
        return 3, ("ERROR: scanned=0 cards (registry=%s) - 路径/格式错，"
                   "拒绝静默报绿" % registry)
    n_state = _count_state_lines(open(registry, encoding="utf-8").read())
    if n_state != len(cards):
        return 4, ("ERROR: cards=%d but top-level state lines=%d "
                   "(registry=%s) - 格式漂移，出声拒绝"
                   % (len(cards), n_state, registry))
    off_spec = [c["card_id"] for c in cards if c.get("state_hits", 1) != 1]
    if off_spec:                    # N13 段3 · G2：块内 state!=1 而全局相等
        return 5, ("ERROR: cards with !=1 top-level state: line = %s "
                   "(registry=%s) - 块内 state 数异常，出声拒绝"
                   % (",".join(off_spec), registry))
    return 0, "preflight ok: cards=%d" % len(cards)


# ===== P-3 · 真写路径（单行替换 + tmp/fsync/replace + 写后双校 + 失败回滚） =====

def _atomic_write_text(path, text):
    """tmp -> flush -> fsync -> os.replace（读者永不见半份卡）。"""
    d = os.path.dirname(os.path.abspath(path))
    tmp = os.path.join(d, ".%s.tmp-state.%d"
                       % (os.path.basename(path), os.getpid()))
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def append_alert(alerts_path, rec):
    """报警行（append-only 逐行 JSON · 可 grep）。alerts_path 为 None ⇒ 不写。"""
    if not alerts_path:
        return None
    rec = dict(rec)
    rec.setdefault("ts", time.time())
    d = os.path.dirname(alerts_path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(alerts_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return alerts_path


def _rollback(card_path, backup_path, alerts=None, card_id=None, trace_id=None):
    """回滚 = 把备份镜像原样写回生产卡（走同一原子路径）。"""
    with open(backup_path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    _atomic_write_text(card_path, text)
    append_alert(alerts, {"kind": "STATE_WRITE_FAIL", "card_id": card_id,
                          "event": "rollback", "to": "restored",
                          "actor": "state_engine", "trace_id": trace_id,
                          "backup": backup_path})


def apply_transition(card_id, event, actor, trace_id, guard_passed,
                     *, to_state=None, card_path=None, backup_dir=None,
                     events_path=None, alerts_path=None, dry_run=False,
                     expect_from=None):
    """唯一写卡入口（段2 批2 真实现 · 段3 也走这里）。

    写序（Q5）：锁 -> 备份 -> 卡(tmp/fsync/replace) -> 事件 append -> 写后双校。
    任一步失败 ⇒ 从备份回滚再退，不留中间态。

    rc 语义：
      0 ok（或 duplicate / would_write） / 1 卡文件不存在 / 2 块内 state 命中 !=1 /
      3 写后双校失败（已回滚） / 4 CAS 不匹配（态已变，未动卡） / 5 guard 未过 /
      6 值不在九态白名单（P-1） / 7 frozen 卡拒写（FROZEN_DENY） /
      8 备份失败（fail-closed，未动卡） / 9 转移不在 T 表白名单（GUARD_DENY）
    """
    card_path = card_path or DEFAULT_REGISTRY
    backup_dir = backup_dir or DEFAULT_BACKUP_DIR
    events_path = events_path or DEFAULT_EVENTS
    alerts_path = alerts_path if alerts_path is not None else DEFAULT_ALERTS

    def _ret(rc, verdict, **kw):
        out = {"rc": rc, "verdict": verdict, "card_id": card_id,
               "event": event, "actor": actor, "trace_id": trace_id}
        out.update(kw)
        return out

    if not guard_passed:
        return _ret(5, "refused", reason="guard not passed")

    # P-1 值白名单：目标值非法 ⇒ 拒改，绝不落盘
    try:
        to_state = validate_state_value(to_state)
    except StateValueError as e:
        append_alert(alerts_path, {"kind": "GUARD_DENY", "card_id": card_id,
                                   "event": event, "actor": actor,
                                   "trace_id": trace_id, "reason": str(e)})
        return _ret(6, "refused", reason=str(e))

    if not os.path.exists(card_path):
        return _ret(1, "error", reason="card file not found: %s" % card_path)

    lock_path = card_path + ".lock"
    with open(lock_path, "a+") as lockfh:
        fcntl.flock(lockfh, fcntl.LOCK_EX)
        try:
            with open(card_path, encoding="utf-8", newline="") as fh:
                text = fh.read()
            loc = locate_state_line(text, card_id)
            if loc["rc"] != 0:
                return _ret(loc["rc"], "refused", reason=loc["reason"])
            cur = loc["value"]

            # 现值本身必须合法（防「卡已被写坏」被继续推进）
            if not state_value_ok(cur):
                append_alert(alerts_path,
                             {"kind": "STATE_INVALID", "card_id": card_id,
                              "event": event, "from": cur, "actor": actor,
                              "trace_id": trace_id})
                return _ret(7, "refused",
                            reason="current state illegal: %r" % cur)

            # frozen 卡拒绝一切自动转移（段3 接口 · 本引擎只读此态）
            if cur == "frozen":
                append_alert(alerts_path,
                             {"kind": "FROZEN_REJECT", "card_id": card_id,
                              "event": event, "from": cur, "actor": actor,
                              "trace_id": trace_id, "skip_reason": "frozen"})
                return _ret(7, "refused", **{"from": cur, "to": to_state,
                                             "reason": "FROZEN_DENY"})

            if cur == to_state:
                return _ret(0, "noop", **{"from": cur, "to": to_state,
                                          "reason": "already in target state"})

            # 乐观 CAS（副）：锁内比对「读到的现值」与调用方声明
            # 先于表闸——陈旧写者该得 state_mismatch（J3），不是 GUARD_DENY
            if expect_from is not None and expect_from != cur:
                append_alert(alerts_path,
                             {"kind": "STATE_MISMATCH", "card_id": card_id,
                              "event": event, "from": cur, "to": to_state,
                              "expect_from": expect_from, "actor": actor,
                              "trace_id": trace_id})
                return _ret(4, "refused", **{"from": cur, "to": to_state,
                                             "reason": "state_mismatch"})

            # T 表白名单（J8：白名单外拒 ⇒ GUARD_DENY）
            ok_t, why_t = resolve_transition(cur, event, to_state)
            if not ok_t:
                append_alert(alerts_path,
                             {"kind": "GUARD_DENY", "card_id": card_id,
                              "event": event, "from": cur, "to": to_state,
                              "actor": actor, "trace_id": trace_id,
                              "reason": why_t})
                return _ret(RC_TABLE_DENY, "refused",
                            **{"from": cur, "to": to_state, "reason": why_t})

            base_sha = sha256_without_state_line(card_path, card_id)[0]

            if dry_run:
                return _ret(0, "would_write", **{"from": cur, "to": to_state,
                                                 "dry_run": True})

            # ① 备份（fail-closed）
            bk = backup_card(card_path, card_id, backup_dir=backup_dir,
                             reason="pre_write:%s:%s->%s"
                                    % (event, cur, to_state), actor=actor)
            if bk.get("rc") != 0:
                return _ret(8, "refused",
                            reason="backup failed: %s" % bk.get("error"),
                            fail_closed=True)

            # ② 单行替换 + 原子写
            lines = text.split("\n")
            lines[loc["line_no"] - 1] = "state: %s" % to_state
            _atomic_write_text(card_path, "\n".join(lines))

            # ③ 写后双校（值校 + 非目标行字节校）
            after = open(card_path, encoding="utf-8", newline="").read()
            loc2 = locate_state_line(after, card_id)
            after_sha = sha256_without_state_line(card_path, card_id)[0]
            ok_val = loc2["rc"] == 0 and loc2["value"] == to_state
            ok_bytes = after_sha == base_sha
            if not (ok_val and ok_bytes):
                _rollback(card_path, bk["path"], alerts=alerts_path,
                          card_id=card_id, trace_id=trace_id)
                return _ret(3, "rolled_back", **{
                    "from": cur, "to": to_state, "value_ok": ok_val,
                    "bytes_ok": ok_bytes, "reason": "post-write verify failed"})

            # ④ 事件流（卡先、事件后；卡=权威）
            verdict = append_event({"card_id": card_id, "from": cur,
                                    "to": to_state, "event": event,
                                    "actor": actor, "trace_id": trace_id},
                                   path=events_path)
            return _ret(0, "ok", **{"from": cur, "to": to_state,
                                    "event_log": verdict,
                                    "backup": bk["path"],
                                    "sha_before": base_sha,
                                    "sha_after": after_sha})
        finally:
            fcntl.flock(lockfh, fcntl.LOCK_UN)


def restore_card(card_id, backup_path, *, card_path=None, alerts_path=None):
    """真回滚：把备份镜像写回生产卡（走原子路径 + 写后 sha 校）。"""
    card_path = card_path or DEFAULT_REGISTRY
    if not os.path.exists(backup_path):
        return {"rc": 1, "error": "backup not found: %s" % backup_path}
    want = sha256_file(backup_path)
    _rollback(card_path, backup_path, alerts=alerts_path, card_id=card_id)
    got = sha256_file(card_path)
    return {"rc": 0 if got == want else 3, "card_id": card_id,
            "sha256_want": want, "sha256_got": got, "match": got == want}

# -*- coding: utf-8 -*-
"""N13 段2 批2 · CLI 子命令块（注入 state_engine.py 的 main() 之前）"""

def _load_cards(registry):
    if not os.path.exists(registry):
        return None, None
    text = open(registry, encoding="utf-8").read()
    return text, parse_cards(text)


def cmd_apply(args):
    """真转移（唯一写口）。--dry-run 只算不写。"""
    text, cards = _load_cards(args.registry)
    if text is None:
        print("ERROR: registry not found: %s" % args.registry)
        return 2
    rc_pf, msg = preflight_registry(args.registry, cards)
    if rc_pf != 0:
        print(msg)
        return rc_pf
    if args.card not in [c["card_id"] for c in cards]:
        print("ERROR: card not found: %s" % args.card)
        return 1
    if args.event not in ANY_FROM_EVENTS and args.event not in FREE_FROM_EVENTS \
            and not any(k[1] == args.event for k in T_TRANSITIONS):
        print("ERROR: unknown event: %s" % args.event)
        return 1
    r = apply_transition(args.card, args.event, args.actor, args.trace_id, True,
                         to_state=args.to, card_path=args.registry,
                         backup_dir=args.backup_dir, events_path=args.events,
                         alerts_path=args.alerts, dry_run=args.dry_run,
                         expect_from=args.expect_from)
    print(json.dumps(r, ensure_ascii=False))
    if r["rc"] == 0 and r["verdict"] == "ok":
        print("APPLIED card=%s %s -> %s event=%s backup=%s"
              % (args.card, r["from"], r["to"], args.event, r.get("backup")))
    elif r["rc"] == 0 and r["verdict"] == "would_write":
        print("DRY-RUN card=%s %s -> %s (未落盘)" % (args.card, r["from"], r["to"]))
    return r["rc"]


def cmd_restore_real(args):
    r = restore_card(args.card, args.backup, card_path=args.registry,
                     alerts_path=args.alerts)
    print(json.dumps(r, ensure_ascii=False))
    return r["rc"]


def cmd_preflight(args):
    text, cards = _load_cards(args.registry)
    if text is None:
        print("ERROR: registry not found: %s" % args.registry)
        return 2
    rc_pf, msg = preflight_registry(args.registry, cards)
    print(msg)
    return rc_pf
# ===== N13 段2 批2 注入块（END） =====


def reconcile_check(registry, events_path=None, alerts_path=None,
                    card_ids=None):
    """撕裂检测（J7 · 只读）：卡 state（权威） vs 事件流末条 `to`。

    卡为权威（真源唯一）= 卡内 `state` 字段 ⇒ 不一致时**不改卡**，只出声：
      · 有事件但末态 != 卡态 ⇒ `STATE_SPLIT`（写报警行）
      · 卡无事件基线 ⇒ 不计（unbaselined，看门狗同口径）
    返回 {"rc", "splits": [...], "unbaselined": [...], "lines": [...]}
    """
    text = open(registry, encoding="utf-8").read()
    cards = parse_cards(text)
    rc_pf, msg = preflight_registry(registry, cards)
    if rc_pf != 0:
        return {"rc": rc_pf, "error": msg, "splits": [], "unbaselined": [],
                "lines": [msg]}
    last = {}
    for rec in replay(events_path):
        last[rec.get("card_id")] = rec.get("to")
    splits, unbase, lines = [], [], []
    for c in cards:
        cid = c["card_id"]
        if card_ids and cid not in card_ids:
            continue
        want = last.get(cid)
        if want is None:
            unbase.append(cid)
            continue
        if want != c["state"]:
            splits.append((cid, c["state"], want))
            line = ("STATE_SPLIT card=%s card_state=%s log_state=%s"
                    % (cid, c["state"], want))
            lines.append(line)
            append_alert(alerts_path,
                         {"kind": "STATE_SPLIT", "card_id": cid,
                          "event": "state.reconciled", "from": want,
                          "to": c["state"], "actor": "state_engine",
                          "trace_id": "reconcile", "reason": "card_is_truth"})
    return {"rc": 0, "splits": splits, "unbaselined": unbase, "lines": lines}


def cmd_reconcile(args):
    r = reconcile_check(args.registry, events_path=args.events,
                        alerts_path=args.alerts)
    for ln in r["lines"]:
        print(ln)
    print("reconcile: cards=%d splits=%d unbaselined=%d"
          % (_count_state_lines(open(args.registry, encoding="utf-8").read()),
             len(r["splits"]), len(r["unbaselined"])))
    return r["rc"]


def _selftest_batch2(reg):
    """段2 批2 追加臂 —— 全部在 tmp 副本上跑（生产卡零改）。"""
    import tempfile

    ok = True
    text = open(reg, encoding="utf-8").read()
    with tempfile.TemporaryDirectory() as td:
        card = os.path.join(td, "registry.md")
        with open(card, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        env = dict(backup_dir=os.path.join(td, "backups"),
                   events_path=os.path.join(td, "events.jsonl"),
                   alerts_path=os.path.join(td, "alerts.jsonl"))

        loc = locate_state_line(text, "N3")
        good = loc["rc"] == 0 and loc["value"] == "awaiting_decision"
        print("[P-1 正控] locate N3 rc=%d value=%s -> %s"
              % (loc["rc"], loc["value"], "PASS" if good else "FAIL"))
        ok = ok and good

        lines = text.split("\n")
        lines[loc["line_no"] - 1] = "state: malicious_value"
        with open(card, "w", encoding="utf-8", newline="") as fh:
            fh.write("\n".join(lines))
        loc2 = locate_state_line(open(card, encoding="utf-8").read(), "N3")
        good = loc2["rc"] == RC_INVALID_STATE
        print("[P-1 负控] state=malicious_value -> rc=%d (期望 %d) -> %s"
              % (loc2["rc"], RC_INVALID_STATE, "PASS" if good else "FAIL"))
        ok = ok and good
        with open(card, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

        foreign = os.path.join(td, "foreign.md")
        with open(foreign, "w", encoding="utf-8") as fh:
            fh.write("# no cards here\n")
        rc = cmd_plan(argparse.Namespace(registry=foreign, card=None,
                                         events=env["events_path"]))
        good = rc != 0
        print("[P-2 负控/外域] plan rc=%d (期望 !=0) -> %s"
              % (rc, "PASS" if good else "FAIL"))
        ok = ok and good

        rc = cmd_plan(argparse.Namespace(registry=reg, card=None,
                                         events=env["events_path"]))
        good = rc == 0
        print("[P-2 正控] plan --all rc=%d -> %s"
              % (rc, "PASS" if good else "FAIL"))
        ok = ok and good

        b4 = sha256_file(card)
        r = apply_transition("N12", "deps_all_closed", "mimir", "selftest", True,
                             to_state="in_progress", card_path=card,
                             dry_run=True, **env)
        zero = sha256_file(card) == b4
        good = r["rc"] == 0 and r["verdict"] == "would_write" and zero
        print("[P-3 正控/dry-run] rc=%d verdict=%s 零落盘=%s -> %s"
              % (r["rc"], r["verdict"], zero, "PASS" if good else "FAIL"))
        ok = ok and good

        r = apply_transition("N12", "deps_all_closed", "mimir", "selftest", True,
                             to_state="in_progress", card_path=card, **env)
        same = r["sha_before"] == r["sha_after"]
        good = (r["rc"] == 0 and r["verdict"] == "ok" and same
                and line_count(env["events_path"]) == 1)
        print("[P-3 正控/真写] rc=%d %s->%s 单行=%s events=%d -> %s"
              % (r["rc"], r.get("from"), r.get("to"), same,
                 line_count(env["events_path"]), "PASS" if good else "FAIL"))
        ok = ok and good

        d = restore_drill(r["backup"], card_id="N12", expect_state="pending",
                          tmp_dir=os.path.join(td, "drill"))
        good = bool(d["rc"] == 0 and d["sha_match"] and d["state_match"])
        print("[P-3 正控/DRILL] rc=%d sha_match=%s state_match=%s -> %s"
              % (d["rc"], d["sha_match"], d["state_match"],
                 "PASS" if good else "FAIL"))
        ok = ok and good

        r2 = apply_transition("N12", "deps_all_closed", "mimir", "selftest", True,
                              to_state="in_progress", card_path=card, **env)
        good = r2["verdict"] == "noop" and line_count(env["events_path"]) == 1
        print("[P-3 幂等] 重放 verdict=%s events=%d -> %s"
              % (r2["verdict"], line_count(env["events_path"]),
                 "PASS" if good else "FAIL"))
        ok = ok and good

        b4 = sha256_file(card)
        r3 = apply_transition("N12", "produces_persisted", "mimir", "selftest",
                              True, to_state="awaiting_verify", card_path=card,
                              expect_from="pending", **env)
        zero = sha256_file(card) == b4
        good = r3["rc"] == 4 and zero
        print("[P-3 负控/CAS] rc=%d 零改=%s -> %s"
              % (r3["rc"], zero, "PASS" if good else "FAIL"))
        ok = ok and good

        r4 = apply_transition("N12", "produces_persisted", "mimir", "selftest",
                              True, to_state="T99", card_path=card, **env)
        good = r4["rc"] == 6
        print("[P-1 负控/目标值] to=T99 rc=%d -> %s"
              % (r4["rc"], "PASS" if good else "FAIL"))
        ok = ok and good

        ltext = open(card, encoding="utf-8").read()
        fl = locate_state_line(ltext, "N12")
        ln2 = ltext.split("\n")
        ln2[fl["line_no"] - 1] = "state: frozen"
        with open(card, "w", encoding="utf-8", newline="") as fh:
            fh.write("\n".join(ln2))
        b4 = sha256_file(card)
        r5 = apply_transition("N12", "deadline_exceeded", "watchdog", "selftest",
                              True, to_state="stalled", card_path=card, **env)
        good = r5["rc"] == 7 and "FROZEN" in r5["reason"] \
            and sha256_file(card) == b4
        print("[P-3 负控/frozen] rc=%d reason=%s 零改=%s -> %s"
              % (r5["rc"], r5["reason"], sha256_file(card) == b4,
                 "PASS" if good else "FAIL"))
        ok = ok and good

        print("[selftest/batch2] rc=%d" % (0 if ok else 1))
    return ok


# ===== N13 段3 guard 注入块（BEGIN） =====
# -*- coding: utf-8 -*-
"""N13 段3 · 4 道 guard 刹车 + 停止令验签

G1 值白名单（全路径加严）· G2 外域/格式错出声 · G3 停止令渠道指纹（白名单）· G4 可撤+留痕

真源（段3 规格 §二 段3 行 + 预置卡 L932 舵手定案 2026-10-09）：
  「采纳『渠道白名单』—— 停止令只认『舵手的飞书私聊』（平台身份认证）
    ＋ 每次停止留审计行（谁/何时/何范围）＋ 停止可撤；**不新增秘密存储**。」

零新依赖（stdlib）· 零删除 · 零改生产卡（演练全走副本）。
"""


# ===== G1 · 值白名单（全路径加严） =====
# 段2 批2 只覆盖「块内」口径（locate_state_line 已校验值）；
# 整文件口径命中 1 条时**不校验值** ⇒ 非法值静默放行。

def whole_file_value_guard(text):
    """整文件口径的值白名单闸（与块内口径同常量 / 同 rc）。

    返回 dict：{rc, value, line_no, reason}
      · rc=0                  唯一命中且值合法
      · rc=2                  命中 != 1（位置闸）
      · rc=RC_INVALID_STATE   唯一命中但值非法（**段3 新增**）
    """
    loc = locate_state_line_whole_file(text)
    if loc["rc"] != 0:
        return {"rc": loc["rc"], "value": None, "line_no": None,
                "reason": loc["reason"]}
    val = validate_state_value(loc["value"])   # 非法 ⇒ StateValueError
    return {"rc": 0, "value": val, "line_no": loc["line_no"],
            "reason": "ok (whole-file value whitelist)"}


def whole_file_guard_result(text):
    """统一出口：把 StateValueError 转成 rc，供 selftest / CLI 复用（不抛异常）。"""
    try:
        return whole_file_value_guard(text)
    except StateValueError as e:
        return {"rc": RC_INVALID_STATE, "value": None, "line_no": None,
                "reason": str(e)}


# ===== G3 · 停止令渠道指纹（白名单）· T11/T12 =====

# 白名单 = **单一渠道**（舵手 2026-10-09 定案）。精确匹配，不做前缀/子串匹配。
STOP_ORDER_CHANNEL = "feishu:dm"
RC_STOP_REFUSED = 8        # 停止令被拒（渠道非白名单 / 验签不过）；7 已属 FROZEN_REJECT

# 渠道标识真源 = 运行时配置（**不新增秘密存储** · 舵手定案）。
# 只读 config.yaml 的 FEISHU_HOME_CHANNEL；读不到 ⇒ fail-closed（拒一切停止令）。
CONFIG_FILE = os.path.join(_home(), "config.yaml")
STOP_LOG_DEFAULT = os.path.join(DATA_DIR, "stop-orders.jsonl")


def _read_home_channel(config_file=None):
    """从 config.yaml 读 FEISHU_HOME_CHANNEL（真源）。读不到 ⇒ None（fail-closed）。"""
    p = config_file or CONFIG_FILE
    if not os.path.exists(p):
        return None
    for ln in open(p, encoding="utf-8", errors="replace"):
        ln = ln.strip()
        if ln.startswith("FEISHU_HOME_CHANNEL:"):
            v = ln.split(":", 1)[1].strip().strip("'\"")
            return v or None
    return None


def derive_sender_fingerprint(channel, chat_id, config_file=None):
    """**服务端派生**指纹（不采信报文自称字段 · 角色卡 §Rules 2）。

    指纹 = "feishu:dm:<chat_id>" —— chat_id 必须**精确等于** config.yaml 的
    FEISHU_HOME_CHANNEL（舵手主 chat）。派生失败 ⇒ None。
    """
    if channel != STOP_ORDER_CHANNEL:
        return None
    cid = chat_id or ""                    # 精确匹配：不 strip（防尾随空格绕过）
    if not cid:
        return None
    home = _read_home_channel(config_file)
    if not home:
        return None
    if cid != home:          # 精确匹配（非前缀 / 非子串）
        return None
    return "%s:%s" % (STOP_ORDER_CHANNEL, cid)


def verify_stop_order(order, config_file=None):
    """T11/T12 停止令验签（唯一判据入口）。

    order = {channel, chat_id, sender_fingerprint(自称), scope, action, order_id}
    返回 {ok, fingerprint, reason, decision}（decision ∈ {accepted, refused}）

    规则（fail-closed）：
      1. 渠道必须 == feishu:dm（白名单唯一项）
      2. 服务端派生指纹必须成功（chat_id 精确等于 config 的 FEISHU_HOME_CHANNEL）
      3. 自称 sender_fingerprint 必须**存在且等于**派生值（防伪造 / 防缺字段）
      4. scope ∈ {all, card_id}；action ∈ {stop, start}
    """
    order = order or {}
    ch = order.get("channel") or ""        # 精确匹配：不 strip（防尾随空格绕过）
    if ch != STOP_ORDER_CHANNEL:
        return {"ok": False, "fingerprint": None, "decision": "refused",
                "reason": "channel not in whitelist: %r (only %r allowed)"
                          % (ch, STOP_ORDER_CHANNEL)}
    derived = derive_sender_fingerprint(ch, order.get("chat_id"), config_file)
    if not derived:
        return {"ok": False, "fingerprint": None, "decision": "refused",
                "reason": "fingerprint derive failed (chat_id != "
                          "FEISHU_HOME_CHANNEL in config, or config unreadable)"}
    claimed = order.get("sender_fingerprint") or ""   # 精确匹配：不 strip
    if not claimed:
        return {"ok": False, "fingerprint": derived, "decision": "refused",
                "reason": "sender_fingerprint missing (T11 guard: 无指纹 => 拦住)"}
    if claimed != derived:
        return {"ok": False, "fingerprint": derived, "decision": "refused",
                "reason": "sender_fingerprint mismatch: claimed=%r derived=%r"
                          % (claimed, derived)}
    scope = (order.get("scope") or "").strip()
    if scope not in ("all", "card_id"):
        return {"ok": False, "fingerprint": derived, "decision": "refused",
                "reason": "scope not in {all, card_id}: %r" % scope}
    action = (order.get("action") or "stop").strip()
    if action not in ("stop", "start"):
        return {"ok": False, "fingerprint": derived, "decision": "refused",
                "reason": "action not in {stop, start}: %r" % action}
    return {"ok": True, "fingerprint": derived, "decision": "accepted",
            "reason": "ok"}


# ===== G4 · 可撤 + 留痕 =====

STOP_EVENT_FIELDS = ("ts", "order_id", "card_id", "event", "actor",
                     "sender_fingerprint", "channel", "scope", "decision",
                     "reason", "revokes")


def stop_order_event(order, verdict, *, card_id="", actor="state_engine",
                     event="liuge.says.stop", revokes=""):
    """构造停止令事件行（append-only · 含指纹与判定依据 · G4 留痕）。"""
    return {
        "ts": time.time(),
        "order_id": order.get("order_id") or "",
        "card_id": card_id or order.get("card_id") or "",
        "event": event,
        "actor": actor,
        "sender_fingerprint": verdict.get("fingerprint") or "",
        "channel": order.get("channel") or "",
        "scope": order.get("scope") or "",
        "decision": verdict.get("decision") or "",
        "reason": verdict.get("reason") or "",
        "revokes": revokes,
    }


def append_stop_event(rec, path):
    """停止令事件落盘（append-only · flock 单写窗口 · fsync）。

    与 state_event_log 同族（同 flock/fsync 语义），但**独立文件** ——
    不污染 state-events.jsonl 的 7 字段契约（watchdog/replay 消费面）。
    """
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    line = json.dumps({k: rec.get(k, "") for k in STOP_EVENT_FIELDS},
                      ensure_ascii=False)
    with open(path + ".lock", "a+") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)
    return line


def stop_order_seen(order_id, path):
    """幂等：同 order_id 已落 ⇒ True（防重放停止令）。"""
    if not order_id or not os.path.exists(path):
        return False
    for ln in open(path, encoding="utf-8", errors="replace"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if rec.get("order_id") == order_id:
            return True
    return False


def revoke_stop_order(order_id, *, path, actor="state_engine", reason="revoked"):
    """撤销停止令（可逆 · G4）：**追加** revoked 行（不改历史行 · append-only）。"""
    rec = {"ts": time.time(), "order_id": order_id, "card_id": "",
           "event": "liuge.says.start", "actor": actor,
           "sender_fingerprint": "", "channel": STOP_ORDER_CHANNEL,
           "scope": "", "decision": "revoked", "reason": reason,
           "revokes": order_id}
    return append_stop_event(rec, path)


def cmd_stop(args):
    """CLI：停止令验签 + 留痕（**段3 只做 guard 与验签 · 不真写生产卡**）。"""
    order = {"order_id": args.order_id, "channel": args.channel,
             "chat_id": args.chat_id,
             "sender_fingerprint": args.sender_fingerprint,
             "scope": args.scope, "action": args.action,
             "card_id": args.card}
    v = verify_stop_order(order, config_file=args.config)
    if not v["ok"]:
        print("ERROR: stop order refused: %s" % v["reason"])
    else:
        print("STOP ORDER ACCEPTED fingerprint=%s scope=%s"
              % (v["fingerprint"], args.scope))
    rec = stop_order_event(order, v, card_id=args.card)
    if args.record:
        if stop_order_seen(args.order_id, args.stop_log):
            print("audit: duplicate order_id=%s -> 不重复落行（幂等）"
                  % args.order_id)
        else:
            append_stop_event(rec, args.stop_log)
            print("audit: appended to %s" % args.stop_log)
    print(json.dumps(rec, ensure_ascii=False))
    return 0 if v["ok"] else RC_STOP_REFUSED


def cmd_unstop(args):
    """CLI：撤销停止令（可逆 · G4 留痕）。"""
    if not stop_order_seen(args.order_id, args.stop_log):
        print("ERROR: order_id not found in stop log: %s" % args.order_id)
        return 1
    revoke_stop_order(args.order_id, path=args.stop_log, actor=args.actor)
    print("REVOKED order_id=%s (audit line appended)" % args.order_id)
    return 0


# ===== N13 段3 · selftest 追加臂 =====

def _selftest_seg3(reg, tmpdir=None):
    """N13 段3 · G1-G4 两向判据（真实调用路径 + 副本受控差分 · 零改生产卡）。

    返回 bool（全臂 PASS）。钻取目录 = DATA_DIR/state-seg3-drill（自有 scratch）。
    """
    ok = True
    tmp = tmpdir or os.path.join(DATA_DIR, "state-seg3-drill")
    os.makedirs(tmp, exist_ok=True)
    cfg = os.path.join(tmp, "config.yaml")
    with open(cfg, "w", encoding="utf-8") as fh:
        fh.write("FEISHU_HOME_CHANNEL: oc_selftest_home\n")
    stoplog = os.path.join(tmp, "stop-orders.jsonl")
    open(stoplog, "w").close()          # 自有 scratch 置空（幂等 · 不删任何文件）

    def _arm(arm, good, detail):
        nonlocal ok
        ok = ok and good
        print("%s %s -> %s" % (arm, detail, "PASS" if good else "FAIL"))

    reg_sha_in = sha256_file(reg)
    text = open(reg, encoding="utf-8").read()

    # ---------- G1 值白名单（全路径加严） ----------
    print("== G1 值白名单（全路径）：块内 + 整文件两口径 ==")
    r = whole_file_guard_result(text)
    _arm("[G1 正控/真 registry]", r["rc"] == 2,
         "whole-file 真实 registry rc=%d (期望 2 位置闸)" % r["rc"])

    one = os.path.join(tmp, "one-good.md")
    with open(one, "w", encoding="utf-8") as fh:
        fh.write("### N1 · x\nstate: pending\n")
    r = whole_file_guard_result(open(one, encoding="utf-8").read())
    _arm("[G1 正控/整文件合法值]", r["rc"] == 0 and r["value"] == "pending",
         "rc=%d value=%s" % (r["rc"], r["value"]))

    bad = os.path.join(tmp, "one-bad.md")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("### N1 · x\nstate: malicious_value\n")
    r = whole_file_guard_result(open(bad, encoding="utf-8").read())
    _arm("[G1 负控/整文件非法值]", r["rc"] == RC_INVALID_STATE,
         "state=malicious_value rc=%d (期望 %d)" % (r["rc"], RC_INVALID_STATE))

    loc = locate_state_line(open(bad, encoding="utf-8").read(), "N1")
    _arm("[G1 负控/块内非法值]", loc["rc"] == RC_INVALID_STATE,
         "locate --card N1 rc=%d (期望 %d)" % (loc["rc"], RC_INVALID_STATE))

    # ---------- G2 外域 / 格式错出声 ----------
    print("== G2 外域/格式错出声（不静默） ==")
    rc_pf, msg = preflight_registry(os.path.join(tmp, "nonexistent.md"), [])
    _arm("[G2 负控/路径错]", rc_pf != 0 and msg.startswith("ERROR"),
         "rc=%d msg=%r" % (rc_pf, msg[:52]))

    empty = os.path.join(tmp, "no-cards.md")
    with open(empty, "w", encoding="utf-8") as fh:
        fh.write("# 无卡\n正文\n")
    rc_pf, msg = preflight_registry(
        empty, parse_cards(open(empty, encoding="utf-8").read()))
    _arm("[G2 负控/无 N 卡块]", rc_pf != 0 and msg.startswith("ERROR"),
         "rc=%d msg=%r" % (rc_pf, msg[:52]))

    nostate = os.path.join(tmp, "no-state.md")
    with open(nostate, "w", encoding="utf-8") as fh:
        fh.write("### N1 · x\nowner: mimir\n")
    rc_pf, msg = preflight_registry(
        nostate, parse_cards(open(nostate, encoding="utf-8").read()))
    _arm("[G2 负控/块内无顶格 state]", rc_pf != 0 and msg.startswith("ERROR"),
         "rc=%d msg=%r" % (rc_pf, msg[:52]))

    drift = os.path.join(tmp, "sub-block-drift.md")
    with open(drift, "w", encoding="utf-8") as fh:
        fh.write("### N1 · a\nstate: pending\nstate: pending\n### N2 · b\nowner: x\n")
    rc_pf, msg = preflight_registry(
        drift, parse_cards(open(drift, encoding="utf-8").read()))
    _arm("[G2 负控/块内 state!=1 而全局相等]",
         rc_pf != 0 and msg.startswith("ERROR") and "!=1" in msg,
         "rc=%d msg=%r" % (rc_pf, msg[:52]))

    rc_pf, msg = preflight_registry(reg, parse_cards(text))
    _arm("[G2 正控/真 registry]", rc_pf == 0, "rc=%d msg=%r" % (rc_pf, msg[:52]))

    # ---------- G3 停止令渠道指纹（白名单） ----------
    print("== G3 停止令渠道指纹（白名单）· T11/T12 ==")
    home = _read_home_channel(cfg)
    _arm("[G3 前置/config 真源]", home == "oc_selftest_home",
         "FEISHU_HOME_CHANNEL=%r" % home)

    fp = derive_sender_fingerprint(STOP_ORDER_CHANNEL, home, cfg)
    _arm("[G3 正控/服务端派生]", fp == "feishu:dm:oc_selftest_home",
         "fingerprint=%r" % fp)

    v = verify_stop_order({"channel": STOP_ORDER_CHANNEL, "chat_id": home,
                           "sender_fingerprint": fp, "scope": "all",
                           "action": "stop", "order_id": "SELF-OK"}, cfg)
    _arm("[G3 正控/舵手飞书私聊]", v["ok"] and v["decision"] == "accepted",
         "ok=%s decision=%s" % (v["ok"], v["decision"]))

    v = verify_stop_order({"channel": "discussion", "chat_id": home,
                           "sender_fingerprint": fp, "scope": "all",
                           "order_id": "SELF-2"}, cfg)
    _arm("[G3 负控/讨论卡渠道]",
         (not v["ok"]) and "not in whitelist" in v["reason"],
         "ok=%s reason=%r" % (v["ok"], v["reason"][:46]))

    v = verify_stop_order({"channel": "feishu:dm", "chat_id": "oc_attacker",
                           "sender_fingerprint": "feishu:dm:oc_attacker",
                           "scope": "all", "order_id": "SELF-3"}, cfg)
    _arm("[G3 负控/非白名单 chat_id]", not v["ok"],
         "ok=%s reason=%r" % (v["ok"], v["reason"][:46]))

    v = verify_stop_order({"channel": "feishu:dm", "chat_id": home + "x",
                           "sender_fingerprint": "feishu:dm:" + home + "x",
                           "scope": "all", "order_id": "SELF-3b"}, cfg)
    _arm("[G3 负控/前缀扩展 chat_id（精确匹配）]", not v["ok"],
         "ok=%s reason=%r" % (v["ok"], v["reason"][:46]))

    v = verify_stop_order({"channel": "feishu:dm", "chat_id": home,
                           "scope": "all", "order_id": "SELF-4"}, cfg)
    _arm("[G3 负控/无 sender_fingerprint]",
         (not v["ok"]) and "missing" in v["reason"],
         "ok=%s reason=%r" % (v["ok"], v["reason"][:46]))

    v = verify_stop_order({"channel": "feishu:dm", "chat_id": home,
                           "sender_fingerprint": fp + ":forged",
                           "scope": "all", "order_id": "SELF-5"}, cfg)
    _arm("[G3 负控/伪造验签字段]", (not v["ok"]) and "mismatch" in v["reason"],
         "ok=%s reason=%r" % (v["ok"], v["reason"][:46]))

    v = verify_stop_order({"channel": "feishu:dm", "chat_id": home,
                           "sender_fingerprint": fp, "scope": "all",
                           "order_id": "SELF-6"},
                          os.path.join(tmp, "absent.yaml"))
    _arm("[G3 负控/config 读不到 fail-closed]", not v["ok"],
         "ok=%s reason=%r" % (v["ok"], v["reason"][:46]))

    v = verify_stop_order({"channel": STOP_ORDER_CHANNEL, "chat_id": home,
                           "sender_fingerprint": fp, "scope": "bogus",
                           "order_id": "SELF-7"}, cfg)
    _arm("[G3 负控/scope 非法]", (not v["ok"]) and "scope" in v["reason"],
         "ok=%s reason=%r" % (v["ok"], v["reason"][:46]))

    # ---------- G4 可撤 + 留痕 ----------
    print("== G4 可撤 + 留痕（append-only） ==")
    ord_ok = {"order_id": "SELF-OK", "channel": STOP_ORDER_CHANNEL,
              "chat_id": home, "sender_fingerprint": fp, "scope": "all",
              "action": "stop"}
    v_ok = verify_stop_order(ord_ok, cfg)
    append_stop_event(stop_order_event(ord_ok, v_ok, card_id="N12"), stoplog)

    ord_bad = {"order_id": "SELF-BAD", "channel": "discussion",
               "chat_id": home, "sender_fingerprint": fp, "scope": "all"}
    v_bad = verify_stop_order(ord_bad, cfg)
    append_stop_event(stop_order_event(ord_bad, v_bad), stoplog)

    _arm("[G4 正控/触发留痕（接受+拒绝各 1 行）]", line_count(stoplog) == 2,
         "stop-orders.jsonl 行数=%d (期望 2)" % line_count(stoplog))

    first = json.loads(open(stoplog, encoding="utf-8").readline())
    _arm("[G4 正控/行含指纹与判定依据]",
         first.get("sender_fingerprint") == fp
         and first.get("decision") == "accepted"
         and first.get("reason") == "ok"
         and first.get("order_id") == "SELF-OK",
         "fp=%s decision=%s reason=%s"
         % (first.get("sender_fingerprint"), first.get("decision"),
            first.get("reason")))

    _arm("[G4 正控/幂等探针]", stop_order_seen("SELF-BAD", stoplog)
         and not stop_order_seen("NOPE", stoplog),
         "SELF-BAD seen=%s NOPE seen=%s"
         % (stop_order_seen("SELF-BAD", stoplog),
            stop_order_seen("NOPE", stoplog)))

    revoke_stop_order("SELF-OK", path=stoplog)
    last = json.loads(
        open(stoplog, encoding="utf-8").read().strip().split("\n")[-1])
    _arm("[G4 正控/撤销留痕（不改历史行）]",
         line_count(stoplog) == 3 and last.get("decision") == "revoked"
         and last.get("revokes") == "SELF-OK",
         "行数=%d decision=%s revokes=%s"
         % (line_count(stoplog), last.get("decision"), last.get("revokes")))

    _arm("[G4 正控/首行未被改写]",
         json.loads(open(stoplog, encoding="utf-8").readline())
         .get("decision") == "accepted",
         "首行 decision=%s"
         % json.loads(open(stoplog, encoding="utf-8").readline())
         .get("decision"))

    rc_un = cmd_unstop(argparse.Namespace(order_id="NOPE", stop_log=stoplog,
                                          actor="state_engine"))
    _arm("[G4 负控/撤销不存在的单号]", rc_un == 1,
         "cmd_unstop(NOPE) rc=%d (期望 1)" % rc_un)

    print("== 段3 边界：生产 registry 字节零变 ==")
    _arm("[段3 边控/零改生产卡]", sha256_file(reg) == reg_sha_in,
         "sha256 前=%s 后=%s" % (reg_sha_in[:12], sha256_file(reg)[:12]))

    return ok


# ===== N13 段3 guard 注入块（END） =====


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
    a = sub.add_parser("apply")
    a.add_argument("--card", required=True)
    a.add_argument("--event", required=True)
    a.add_argument("--to", required=True)
    a.add_argument("--actor", default="mimir")
    a.add_argument("--trace-id", default="")
    a.add_argument("--expect-from")
    a.add_argument("--alerts", default=DEFAULT_ALERTS)
    a.add_argument("--dry-run", action="store_true")
    rr = sub.add_parser("restore-real")
    rr.add_argument("--card", required=True)
    rr.add_argument("--backup", required=True)
    rr.add_argument("--alerts", default=DEFAULT_ALERTS)
    sub.add_parser("preflight")
    st = sub.add_parser("stop")          # N13 段3 · G3/G4
    st.add_argument("--order-id", required=True)
    st.add_argument("--channel", default="feishu:dm")
    st.add_argument("--chat-id", default=None)
    st.add_argument("--sender-fingerprint", default=None)
    st.add_argument("--scope", default="all")
    st.add_argument("--action", default="stop")
    st.add_argument("--card", default="")
    st.add_argument("--config", default=None)
    st.add_argument("--stop-log", default=STOP_LOG_DEFAULT)
    st.add_argument("--record", action="store_true")
    us = sub.add_parser("unstop")        # N13 段3 · G4 可撤
    us.add_argument("--order-id", required=True)
    us.add_argument("--stop-log", default=STOP_LOG_DEFAULT)
    us.add_argument("--actor", default="state_engine")
    rc_ = sub.add_parser("reconcile")
    rc_.add_argument("--alerts", default=DEFAULT_ALERTS)
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
    if args.cmd == "apply":
        return cmd_apply(args)
    if args.cmd == "restore-real":
        return cmd_restore_real(args)
    if args.cmd == "preflight":
        return cmd_preflight(args)
    if args.cmd == "reconcile":
        return cmd_reconcile(args)
    if args.cmd == "stop":
        return cmd_stop(args)
    if args.cmd == "unstop":
        return cmd_unstop(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
