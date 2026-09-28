"""Moltbook verification-challenge solver (fail-closed).

Run: python3 moltbook_verify_solver.py --selftest
     python3 moltbook_verify_solver.py --text "<challenge_text>" [--json] [--print-curl CODE]

Spec source (on-disk): https://www.moltbook.com/skill.md  section: AI Verification Challenges
  create content -> post.verification{verification_code, challenge_text, expires_at, instructions}
  submit: POST /api/v1/verify  body={"verification_code","answer"}  answer = 2 decimals
  expiry 5 min (submolt 30s); last 10 failed attempts => account auto-suspended
  challenge = obfuscated English word problem: alternating caps + scattered symbols +
  words split by symbols; numbers spelled out, operation encoded in verbs
  (slows by / gains / doubles / divides by).

Design rules:
  R1 fail-closed: unless exactly two numbers + one operation can be determined, refuse
     (exit 2, stdout carries no number). A wrong guess counts toward the
     "last 10 failures => suspension" counter. Never guess.
  R2 symmetric normalisation: word and lexicon both get strip-non-letters + lower +
     collapse repeated letters, so symbol-split "TwEnn-Tyy" -> "twenntyy" -> "twenty".
  R3 numerals assembled by English number-word rules (hundred/thousand multiply).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, ROUND_HALF_UP

UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
SCALES = {"hundred": 100, "thousand": 1000, "million": 1000000}

# operation lexicon: phrase (normalised) -> operator. longest phrase wins.
OP_PHRASES = [
    ("slows down by", "-"), ("slows by", "-"), ("decelerates by", "-"),
    ("decreases by", "-"), ("drops by", "-"), ("reduces by", "-"),
    ("slower by", "-"), ("slows down", "-"), ("slows", "-"),
    ("decelerates", "-"), ("decreases", "-"), ("drops", "-"), ("reduces", "-"),
    ("loses", "-"), ("lose", "-"), ("minus", "-"), ("subtract", "-"),
    ("less than", "-"), ("how many remain", "-"), ("remains", "-"),
    ("remaining", "-"), ("how many left", "-"), ("left over", "-"),
    ("how many fewer", "-"), ("difference", "-"),
    ("speeds up by", "+"), ("accelerates by", "+"), ("increases by", "+"),
    ("faster by", "+"), ("speeds up", "+"), ("accelerates", "+"), ("increases", "+"),
    ("gains", "+"), ("gain", "+"), ("adds", "+"), ("add", "+"), ("plus", "+"),
    ("more than", "+"), ("combines with", "+"), ("combined", "+"),
    ("how many total", "+"), ("in total", "+"), ("sum of", "+"), ("sum", "+"),
    ("altogether", "+"), ("together", "+"), ("total", "+"),
    ("multiplies by", "*"), ("multiplied by", "*"), ("multiplies", "*"),
    ("product of", "*"), ("product", "*"), ("times", "*"),
    ("divided by", "/"), ("divides by", "/"), ("divides into", "/"),
    ("split into", "/"), ("split", "/"), ("shared among", "/"), ("distributes", "/"),
]

# constant (unary) operations
CONST_OPS = [
    ("doubles", ("*", 2)), ("double", ("*", 2)), ("twice", ("*", 2)),
    ("triples", ("*", 3)), ("triple", ("*", 3)), ("thrice", ("*", 3)),
    ("quadruples", ("*", 4)), ("quadruple", ("*", 4)),
    ("halves", ("/", 2)), ("halve", ("/", 2)), ("half", ("/", 2)),
]

# connectors that may sit between two number words of the SAME numeral
CONNECTORS = {"and", "a", "the", "of"}

SYMBOL_OPS = {"+": "+", "-": "-", "*": "*", "x": "*", "/": "/"}


def collapse(s: str) -> str:
    """collapse runs of the same letter: twenntyy -> twenty (used symmetrically)."""
    out = []
    for ch in s:
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out)


def norm_token(tok: str) -> str:
    return collapse(re.sub(r"[^A-Za-z]", "", tok).lower())


def norm_phrase(ph: str) -> str:
    return " ".join(collapse(w) for w in re.findall(r"[A-Za-z]+", ph.lower()))


NUM_LEX = {}
for _w, _v in list(UNITS.items()) + list(TENS.items()):
    NUM_LEX[collapse(_w)] = ("num", _v)
for _w, _v in SCALES.items():
    NUM_LEX[collapse(_w)] = ("scale", _v)

OP_LEX = {norm_phrase(_p): _o for _p, _o in OP_PHRASES}
CONST_LEX = {collapse(_w): _o for _w, _o in CONST_OPS}
MAXPHRASE = max(len(_p.split()) for _p in OP_LEX)


def segment(tok: str):
    """split a (possibly glued) numeric token into lexicon entries; None if not clean."""
    if tok in NUM_LEX:
        return [NUM_LEX[tok]]
    keys = sorted(NUM_LEX, key=len, reverse=True)
    out, i = [], 0
    while i < len(tok):
        hit = None
        for k in keys:
            if len(k) >= 3 and tok.startswith(k, i):
                hit = k
                break
        if hit is None:
            return None
        out.append(NUM_LEX[hit])
        i += len(hit)
    return out or None


def assemble(entries) -> int:
    """English numeral rules: hundred/thousand multiply, others add."""
    total, cur = 0, 0
    for kind, val in entries:
        if kind == "num":
            cur += val
        else:
            if val >= 1000:
                total += max(cur, 1) * val
                cur = 0
            else:
                cur = max(cur, 1) * val
    return total + cur


def parse(text: str) -> dict:
    raw = text.split()
    toks = [norm_token(t) for t in raw]
    live = [t for t in toks if t]
    numbers, i = [], 0
    while i < len(toks):
        t = toks[i]
        seg = segment(t) if t else None
        if seg:
            entries = list(seg)
            j = i + 1
            while j < len(toks):
                nxt = toks[j]
                if nxt and segment(nxt):
                    entries += segment(nxt)
                    j += 1
                    continue
                if (nxt in CONNECTORS and j + 1 < len(toks)
                        and toks[j + 1] and segment(toks[j + 1])):
                    j += 1
                    continue
                break
            numbers.append(assemble(entries))
            i = j
            continue
        i += 1

    ops, const_ops = [], []
    used = set()
    for size in range(min(MAXPHRASE, len(live)), 0, -1):
        for k in range(len(live) - size + 1):
            if any(x in used for x in range(k, k + size)):
                continue
            ph = " ".join(live[k:k + size])
            if ph in OP_LEX:
                ops.append(OP_LEX[ph])
                used.update(range(k, k + size))
    for idx, t in enumerate(live):
        if idx in used:
            continue
        if t in CONST_LEX:
            const_ops.append(CONST_LEX[t])
            used.add(idx)
    for rt in raw:
        if rt.strip() in SYMBOL_OPS and not norm_token(rt):
            ops.append(SYMBOL_OPS[rt.strip()])
    return {"numbers": numbers, "ops": ops, "const_ops": const_ops,
            "norm": " ".join(live)}


def fmt(v) -> str:
    d = v if isinstance(v, Decimal) else Decimal(str(v))
    return str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def solve(text: str) -> dict:
    pr = parse(text)
    nums, ops, cops = pr["numbers"], sorted(set(pr["ops"])), sorted(set(pr["const_ops"]))
    base = {"numbers": nums, "ops": ops, "const_ops": pr["const_ops"], "norm": pr["norm"]}

    def refuse(reason):
        base.update({"status": "refuse", "reason": reason, "answer": None})
        return base

    if cops and (ops or len(nums) != 1):
        return refuse("constant op needs exactly 1 number and no binary op")
    if cops:
        op, k = cops[0]
        val = Decimal(nums[0]) * k if op == "*" else Decimal(nums[0]) / k
        base.update({"status": "ok", "answer": fmt(val), "op": "%s%d" % (op, k)})
        return base
    if len(ops) != 1:
        return refuse("expected exactly 1 operation, found %d" % len(ops))
    if len(nums) != 2:
        return refuse("expected exactly 2 numbers, found %d" % len(nums))
    a, b, op = nums[0], nums[1], ops[0]
    if op == "+":
        val = Decimal(a + b)
    elif op == "-":
        val = Decimal(a - b)
    elif op == "*":
        val = Decimal(a * b)
    else:
        if b == 0:
            return refuse("division by zero")
        val = Decimal(a) / Decimal(b)
    base.update({"status": "ok", "answer": fmt(val), "op": op})
    return base


VECTORS = [
    ("A] lO^bSt-Er S[wImS aT/ tW]eNn-Tyy mE^tE[rS aNd] SlO/wS bY^ fI[vE, wH-aTs] ThE/ nEw^ SpE[eD?",
     "15.00"),
    ("A] LooOObSstErR C[lAw] FoRcE Is^ TwEnTy ThReE N[eWuT]oNs, AnD OtHeR C|lAw Is^ FoUr NeUwToNs; "
     "HoW MaNy ToTaL FoRcEs? umm lxObqstwer", "27.00"),
    ("A] lObStEr SwImS aT tWeNtY mEtErS aNd DoUbLeS iTs SpEeD", "40.00"),
    ("A] lObStEr SwImS aT tWeNtY mEtErS aNd HaLvEs ItS sPeEd", "10.00"),
    ("A] lObStEr TrAvElS fIfTeEn MeTeRs AnD dIvIdEs By FoUr", "3.75"),
    ("tWeLvE nEuToNs TiMeS tHrEe", "36.00"),
    ("a] lObStEr SwImS aT tWeNtY aNd SlOwS bY tHiRtY-fIvE", "-15.00"),
    ("tWo HuNdReD nEuToNs AnD gAiNs FiVe", "205.00"),
    ("A] lObStEr SwImS aT tWeNtY + fIvE", "25.00"),
    ("A] lObStEr FlUrBlEs TwEnTy AnD FiVe", None),
    ("a] lObStEr sWimS aT tWeNtY aNd LoSeS fIvE bUt GaInS tHrEe", None),
]


def selftest() -> int:
    bad = 0
    for txt, want in VECTORS:
        r = solve(txt)
        got = r.get("answer")
        ok = (got == want)
        bad += 0 if ok else 1
        print("%s want=%s got=%s op=%s nums=%s%s" % (
            "PASS" if ok else "FAIL", want, got, r.get("op"), r["numbers"],
            "" if ok else "  reason=%s" % r.get("reason")))
    print("selftest: %d/%d passed" % (len(VECTORS) - bad, len(VECTORS)))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--print-curl", metavar="VERIFICATION_CODE")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.text:
        ap.error("--text required (or --selftest)")
    r = solve(a.text)
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r["status"] == "ok" else 2
    if r["status"] != "ok":
        print("REFUSED: %s | numbers=%s ops=%s" % (r["reason"], r["numbers"], r["ops"]),
              file=sys.stderr)
        return 2
    if a.print_curl:
        print("answer=%s" % r["answer"], file=sys.stderr)
        print("curl -sS -X POST https://www.moltbook.com/api/v1/verify "
              "-H \"Authorization: Bearer $MOLTBOOK_API_KEY\" "
              "-H \"Content-Type: application/json\" "
              "-d '{\"verification_code\": \"%s\", \"answer\": \"%s\"}'"
              % (a.print_curl, r["answer"]))
        return 0
    print(r["answer"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
