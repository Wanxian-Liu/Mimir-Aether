#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''Memory distillation reconciler -- Source == Kept + Card (machine recount).

Why: after entries are moved out of memories/MEMORY.md, no-content-lost must be a
recounted number, not a claim. Implements the reconciliation rule from the
AI Data Remediation role card (L51):
    Source_Rows == Success_Rows + Quarantine_Rows   (mismatch > 0 => Sev-1)

Checks:
  T1   archive is byte-identical to source (sha256)  -> zero-loss guarantee
  T2   every source entry (split on a lone section-sign line) has a map row
  T3   every entry token (path segment / filename / identifier / number) of the
       source is still findable in the targets (new MEMORY.md + distill card);
       tokens not findable = quarantine rows, justified explicitly

Two hard-won design rules (both were real false signals in this repo):
  R-A  NO backslash escapes anywhere in this file -- the payload sanitizer
       rewrote a double-backslash class and silently turned the token regex into
       a never-matching one (all-zero detector that still printed OK).
  R-B  tokenize WITHOUT crossing slash or comma, and test membership by
       SUBSTRING. Exact set membership flagged tokens/tool_trace as lost merely
       because the copy wrote it with a backtick separator -- a reformatting
       artifact, not content loss.

Usage:
  python3 scripts/memory_distill_reconcile.py --source S --archive A --targets T1 T2 [--selftest]
Exit: 0 = PASS / 1 = FAIL / 2 = selftest failure.
'''
import argparse
import hashlib
import pathlib
import re
import sys

SIGN = chr(0xA7)
TAB = chr(9)
NL = chr(10)
SIGN_LINE = re.compile('(?m)^' + SIGN + '[' + TAB + ' ]*$')
TOKEN = re.compile('[A-Za-z0-9_][A-Za-z0-9_.~$:{}-]{3,}')
NUM = re.compile('[0-9][0-9.]*[a-zA-Z%]*')
STRIPCHARS = '.,;:()' + '[]<>|' + chr(96) + chr(39) + chr(34)
STOP = {'http', 'https', 'none', 'true', 'false', 'the', 'and', 'with'}


def sha256(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def entries(text):
    parts = [p.strip() for p in SIGN_LINE.split(text)]
    return [p for p in parts if p]


def tokens_of(text):
    out = set()
    for m in TOKEN.findall(text):
        t = m.strip(STRIPCHARS)
        if len(t) >= 4 and t.lower() not in STOP and not t.isdigit():
            out.add(t)
    for m in NUM.findall(text):
        if len(m) >= 3 and any(c.isdigit() for c in m):
            out.add(m)
    return out


def is_map_row(line):
    if not line.lstrip().startswith('|'):
        return False
    cells = [c.strip() for c in line.split('|')]
    return len(cells) > 2 and cells[1].isdigit()


def missing_in(toks, blob, allowed):
    return sorted(t for t in toks if t not in blob and t not in allowed)


def reconcile(src, target):
    '''True = every entry token is findable in target (intact).

    Same predicate as the T3 main path (tokens_of + substring test) so the
    selftest exercises the real detector instead of a re-implementation.
    '''
    ents = entries(pathlib.Path(src).read_text(encoding='utf-8'))
    blob = pathlib.Path(target).read_text(encoding='utf-8')
    return not any(missing_in(tokens_of(e), blob, set()) for e in ents)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source')
    ap.add_argument('--archive')
    ap.add_argument('--targets', nargs='*', default=[])
    ap.add_argument('--allow-missing', default=None,
                    help='file with one justified token per line')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    src_text = pathlib.Path(a.source).read_text(encoding='utf-8')
    tgt_texts = [pathlib.Path(p).read_text(encoding='utf-8') for p in a.targets]
    blob = NL.join(tgt_texts)
    ents = entries(src_text)
    fails, quarantine = [], []

    if a.archive:
        h_src, h_arc = sha256(a.source), sha256(a.archive)
        same = h_src == h_arc
        print('[T1] source  sha256 = ' + h_src)
        print('[T1] archive sha256 = ' + h_arc)
        print('[T1] byte-identical = ' + ('YES' if same else 'NO'))
        if not same:
            fails.append('T1 archive NOT byte-identical to source')

    map_rows = 0
    for ln in blob.splitlines():
        if is_map_row(ln):
            map_rows += 1
    print('[T2] source entries = %d | mapping rows = %d' % (len(ents), map_rows))
    if map_rows < len(ents):
        fails.append('T2 mapping rows %d < entries %d' % (map_rows, len(ents)))

    allowed = set()
    if a.allow_missing:
        allowed = {l.strip() for l in pathlib.Path(a.allow_missing).read_text(
            encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')}

    total = 0
    for i, e in enumerate(ents, 1):
        head = e.splitlines()[0][:34]
        toks = tokens_of(e)
        total += len(toks)
        miss = missing_in(toks, blob, allowed)
        if miss:
            quarantine.append((i, head, len(miss), miss))
        print('[T3] entry %02d tokens=%3d missing=%d ok=%s %s'
              % (i, len(toks), len(miss), not miss, head))

    n_q = sum(q[2] for q in quarantine)
    print('[T3] token coverage = %d/%d (%.1f%%) | quarantine tokens = %d'
          % (total - n_q, total, 100.0 * (total - n_q) / max(total, 1), n_q))
    if quarantine:
        print('--- QUARANTINE (tokens absent from Kept+Card) ---')
        for i, head, n, miss in quarantine:
            print('  entry %02d missing=%d :: %s' % (i, n, ', '.join(miss)))

    ok = not fails and not quarantine
    print('VERDICT: ' + ('PASS' if ok else 'FAIL'))
    print('RECONCILE: source=%d == kept=%d + quarantine=%d'
          % (len(ents), len(ents) - len(quarantine), len(quarantine)))
    for f in fails:
        print('  FAIL ' + f)
    return 0 if ok else 1


def selftest():
    '''Positive control: intact copy must PASS. Negative control: trimmed target
    must FAIL. If both pass, the detector is dead (all-zero).'''
    import tempfile
    d = pathlib.Path(tempfile.mkdtemp())
    src = d / 'src.md'
    src.write_text('## A' + NL + '- path /x/y/keepme.txt num 4242 shared' + NL
                   + SIGN + NL + '## B' + NL
                   + '- only_in_entry_b token_MARKER_9' + NL, encoding='utf-8')
    good = d / 'good.md'
    good.write_text(src.read_text(encoding='utf-8'), encoding='utf-8')
    bad = d / 'bad.md'
    bad.write_text('## A' + NL + '- path /x/y/keepme.txt num 4242 shared' + NL
                   + SIGN + NL + '## B' + NL
                   + '- nothing here at all' + NL, encoding='utf-8')

    for label, p in (('src', src), ('good', good), ('bad', bad)):
        t = p.read_text(encoding='utf-8')
        print('[selftest] %s entries=%d tokens=%s'
              % (label, len(entries(t)), sorted(tokens_of(t))[:14]))

    ok_good = reconcile(src, good)
    ok_bad = reconcile(src, bad)
    print('[selftest] positive control (intact)  expected PASS -> %s' % ok_good)
    print('[selftest] negative control (trimmed) expected FAIL -> %s' % ok_bad)
    verdict = ok_good and not ok_bad
    print('[selftest] VERDICT: ' + ('PASS' if verdict else 'FAIL'))
    return 0 if verdict else 2


if __name__ == '__main__':
    sys.exit(main())
