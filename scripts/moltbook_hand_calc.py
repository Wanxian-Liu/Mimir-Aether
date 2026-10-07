#!/usr/bin/env python3
"""hand_calc v2 - layered: flat-scan (main, per tracker 量具㉘) + token-scan (digits/clean words).
Never guesses: requires exactly two numbers and one (deduped) operator, or the claw-multiply template."""
import re
from decimal import Decimal, ROUND_HALF_UP

UNITS = {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,
         "ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,
         "seventeen":17,"eighteen":18,"nineteen":19}
TENS = {"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60,"seventy":70,"eighty":80,"ninety":90}
SCALES = {"hundred":100,"thousand":1000,"million":1000000}

def coll(s):
    return re.sub(r"(.)\1+", r"\1", s.lower())

NUMLEX = {}
for w, v in list(UNITS.items()) + list(TENS.items()) + list(SCALES.items()):
    NUMLEX[coll(w)] = (w, v)

OPS = {}
for words, op in [
    ("minus|subtract|subtracts|subtracting|loses|lose|fewer|drops|drop|reduces|reduce|decreases|decrease|slows|slow|remaining|remains|remain|left|shorter", "-"),
    ("plus|gains|gain|adds|added|totals|altogether|combined|combines|faster|accelerates|accelerate|increases|increase|speeds|longer", "+"),
    ("times|multiplies|multiplied|multiply|product", "*"),
    ("divides|divided|divide|halves|halved", "/"),
]:
    for w in words.split("|"):
        if len(w) >= 4:
            OPS[coll(w)] = op
WEAK = {coll(w) for w in ("total", "sum", "together", "altogether", "combined")}
MULT_WORDS = {coll(w) for w in ("uses", "use", "with", "per", "each")}

def _num_atom(word):
    if word in SCALES: return ("scale", SCALES[word])
    if word in TENS: return ("ten", TENS[word])
    if word in UNITS: return ("unit", UNITS[word])
    return None

def _compose(atoms):
    """atoms: list of ('unit'|'ten'|'scale', v) -> int"""
    total = 0; cur = 0
    for i, (k, v) in enumerate(atoms):
        if k == "unit":
            cur += v
        elif k == "ten":
            cur += v
        else:
            cur = max(cur, 1) * v
    return total + cur

def flat_channel(text):
    runs = re.findall(r"[A-Za-z]+", text)          # keep original spans
    spans = []                                      # (flat_start, flat_end, runtext)
    flat = ""
    for r in runs:
        c = coll(r)
        spans.append((len(flat), len(flat) + len(c), r))
        flat += c
    if not flat:
        return None
    keys = sorted(set(list(NUMLEX) + list(OPS) + list(MULT_WORDS)), key=len, reverse=True)
    atoms = []      # numbers in order (as composed ints) and ops
    seq = []        # ('num', v) / ('op', o) / ('mult',)
    i = 0; last_num_end = -99
    while i < len(flat):
        hit = None
        for k in keys:
            if flat.startswith(k, i):
                hit = k; break
        if not hit:
            i += 1; continue
        # pseudo-hit guard: match entirely inside one original run that is not that word
        contain = [s for s in spans if s[0] <= i and i + len(hit) <= s[1]]
        if contain and coll(contain[0][2]) != hit:
            i += 1; continue
        if hit in NUMLEX:
            kind = _num_atom(NUMLEX[hit][0])
            adjacent = (i == last_num_end)
            if seq and seq[-1][0] == "num" and kind[0] == "unit" and adjacent and seq[-1][2]:
                seq[-1] = ("num", seq[-1][1] + kind[1], False)   # e.g. twenty + five -> 25, then closed
            else:
                seq.append(("num", kind[1], kind[0] != "unit"))
            last_num_end = i + len(hit)
        elif hit in OPS:
            seq.append(("op", OPS[hit], False))
        else:
            seq.append(("mult", None, False))
        i += len(hit)
    return seq

def token_channel(text):
    toks = re.findall(r"[A-Za-z]+|\d+", text)
    seq = []; syms = re.findall(r"(?<![A-Za-z0-9])([-+*/x\u00d7\u00f7])(?![A-Za-z0-9])", text)
    syms = [{"x":"*","\u00d7":"*","\u00f7":"/"}.get(s, s) for s in syms]
    prev_num = None
    for tk in toks:
        if tk.isdigit():
            seq.append(("num", int(tk), True)); prev_num = True; continue
        c = coll(tk)
        if c in NUMLEX:
            w, v = NUMLEX[c]
            if prev_num and w in UNITS and seq and seq[-1][0] == "num":
                seq[-1] = ("num", seq[-1][1] + v, True)
            else:
                seq.append(("num", v, w not in UNITS))
            prev_num = True; continue
        if c in OPS:
            seq.append(("op", OPS[c], False)); prev_num = False; continue
        if c in MULT_WORDS:
            seq.append(("mult", None, False)); prev_num = False; continue
        prev_num = False
    seq += [("op", s, False) for s in syms]
    return seq

def _eval(seq, text):
    nums = [a[1] for a in seq if a[0] == "num"]
    ops = [a[1] for a in seq if a[0] == "op"]
    has_mult = any(a[0] == "mult" for a in seq)
    claw = bool(re.search(r"claw", text, re.I))
    strong = [o for o in ops if o]
    uniq = set(strong)
    if len(nums) == 2 and len(uniq) == 1 and len(strong) >= 1:
        return (nums[0], strong[0], nums[1]), "op"
    if len(nums) == 2 and not strong and claw and has_mult:
        return (nums[0], "*", nums[1]), "claw-mult"
    if len(nums) == 2 and uniq == {"+"} and claw and has_mult:
        return (nums[0], "*", nums[1]), "claw-mult-over-total"
    return None, None

def hand_calc(text):
    """Decision rule (fail-closed):
       1. flat channel decides  -> use it (validated on split-word cases)
       2. flat saw numbers but could not decide -> REFUSE (token channel is not trustworthy
          when the two channels disagree structurally; a confident wrong answer costs a
          failure credit, a refusal costs nothing)
       3. flat saw no numbers at all (digit-only problems) -> token channel
       4. otherwise refuse
    """
    out = {}
    fseq = tseq = None
    try:
        fseq = flat_channel(text)
    except Exception as e:
        out["flat"] = ("ERR", str(e))
    try:
        tseq = token_channel(text)
    except Exception as e:
        out["token"] = ("ERR", str(e))
    fdec = _eval(fseq, text) if fseq else (None, None)
    tdec = _eval(tseq, text) if tseq else (None, None)
    out.setdefault("flat", fdec); out.setdefault("token", tdec)
    out["flat_nums"] = len([a for a in (fseq or []) if a[0] == "num"])
    pick = None; why = None
    if fdec[0]:
        pick, why = fdec[0], "flat:" + str(fdec[1])
    elif out["flat_nums"] >= 1:
        return None, None, "refused:flat-ambiguous", out
    elif tdec[0]:
        pick, why = tdec[0], "token:" + str(tdec[1])
    if pick:
        a, op, b = pick
        val = {"+": Decimal(a)+Decimal(b), "-": Decimal(a)-Decimal(b),
               "*": Decimal(a)*Decimal(b), "/": Decimal(a)/Decimal(b)}[op]
        return (a, op, b), val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), why, out
    return None, None, None, out

if __name__ == "__main__":
    cases = [
        "A claw exerts twenty five Newtons and uses two claws, what is the total?",
        "Claw exerts Twenty Five Newtons AND USES TWO CLAWS",
        "if a claw exerts tW eN tY fIvE newtons and accelerates by seven, what is the total",
        "thirty newtons but loses eleven, what is the remaining force",
        "Claw exerts 17 Newtons and uses 3 claws, how much force in total?",
        "aT hIrTy newtons and gains twelve newtons, what is the sum",
        "tWeLlV e / nEeWtOnSs and gains twenty four, what is the total",
        "a claw exerts thirty five newtons while another loses eleven, how many remain",
    ]
    for c in cases:
        r = hand_calc(c)
        print("TEXT:", c)
        print("   ->", r[0], r[1], "why=", r[2])
        print("   channels:", r[3])
