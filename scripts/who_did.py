#!/usr/bin/env python3
"""A5 (ф2) — attribution self-check entry: declaration + corroboration, or 不可判.

Ruling (Hermes receipt, 2026-09-13, Q3): ф2 adopted, three entry points
(commit / file / card). "不可判" is the soul of the design — it continues the
X2-c line from Q3 section 6: a time approximation must never masquerade as an
attribution.

Every answer prints TWO independent things:

  声明 (declaration)    what someone wrote down — commit trailer ``Agent: <id>``
                        (git 2.43 ``%(trailers:key=Agent)``) or card frontmatter
                        ``author: <id>``.
  旁证 (corroboration)  what the machine recorded — the hook-level stream
                        ``logs/git-commit-audit.jsonl`` joined by ``repo`` +
                        ``head == <commit>^`` (exact, no clock guessing), and
                        the tool-level stream ``logs/git-audit.jsonl``
                        (``classes`` containing ``commit``) joined by ``repo``
                        plus a narrow time window.

Verdicts
  consistent     both sides present and equal              -> exit 0
  mismatch       both sides present and different          -> exit 3
  undetermined   不可判: a side is missing, or the evidence is ambiguous
                 (multiple trace_ids in the same window / same-parent records
                 from more than one run)                     -> exit 2

The Identity & Trust Architect's addition (2026-09-13) lives here too: the
trailer value domain is checked against the closed set
{mimir, hermes, openclaw, loki} and an out-of-set id is FLAGGED here, never
rejected — the hooks stay non-blocking recorders.

Boundary (docs/AGENT_REPO_OWNERSHIP.md section 8): commits dated before
2026-09-13 carry no attribution value in their git signature — that is an
explainable gap, not a claim. Those are reported with a boundary note, and a
signature-only answer on them is NOT accepted as an attribution.

Usage
  python3 scripts/who_did.py --commit HEAD
  python3 scripts/who_did.py --commit 42e8baf
  python3 scripts/who_did.py --file agent/run_context.py
  python3 scripts/who_did.py --card ~/wiki/discussions/<name>.md
  python3 scripts/who_did.py <path-or-rev>          # auto-detect the entry
  python3 scripts/who_did.py --commit HEAD --json
  python3 scripts/who_did.py --commit HEAD --quiet   # verdict line only

Streams can be redirected for testing with the same env vars the writers use:
  MIMIR_GIT_COMMIT_AUDIT_LOG   hook-level, default ~/.mimiraether/logs/git-commit-audit.jsonl
  MIMIR_GIT_AUDIT_LOG          tool-level, default ~/.mimiraether/logs/git-audit.jsonl
  MIMIR_AETHER_HOME            data root, default ~/.mimiraether
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ALLOWED_IDS = ("mimir", "hermes", "openclaw", "loki")

# Commits dated before this day carry no attribution in their git signature
# (docs/AGENT_REPO_OWNERSHIP.md section 8).
BOUNDARY_DATE = "2026-09-13"

CONSISTENT = "consistent"
MISMATCH = "mismatch"
UNDETERMINED = "undetermined"

EXIT_CONSISTENT = 0
EXIT_ERROR = 1
EXIT_UNDETERMINED = 2
EXIT_MISMATCH = 3

# The tool-level stream is wall-clock joined; a commit record is written a few
# seconds before the commit object exists, and a chained command may have
# started earlier. Wide enough to find the record, narrow enough that a second
# commit shows up as ambiguity instead of being silently picked.
TOOL_WINDOW_BACK = 3600
TOOL_WINDOW_FORWARD = 10


# --------------------------------------------------------------------------- io


def home_root() -> Path:
    override = os.getenv("MIMIR_AETHER_HOME")
    return Path(override).expanduser() if override else Path("~/.mimiraether").expanduser()


def hook_stream_path() -> Path:
    override = os.getenv("MIMIR_GIT_COMMIT_AUDIT_LOG")
    return Path(override).expanduser() if override else home_root() / "logs" / "git-commit-audit.jsonl"


def tool_stream_path() -> Path:
    override = os.getenv("MIMIR_GIT_AUDIT_LOG")
    return Path(override).expanduser() if override else home_root() / "logs" / "git-audit.jsonl"


def load_stream(path: Path) -> tuple[list[dict], str]:
    """Read a JSONL audit stream. A missing stream is a state, not a crash."""
    if not path.exists():
        return [], "missing"
    records: list[dict] = []
    bad = 0
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if isinstance(obj, dict):
                records.append(obj)
    except OSError as exc:
        return [], "unreadable: %s" % exc
    return records, ("ok" if not bad else "ok (%d malformed line(s) skipped)" % bad)


def norm_repo(path: str) -> str:
    if not path:
        return ""
    try:
        return os.path.realpath(os.path.expanduser(path))
    except OSError:
        return path


def _run(cmd: list) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _git(repo: str, *args: str):
    result = _run(["git", "-C", repo, *args])
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def repo_root(path: str):
    out = _git(path, "rev-parse", "--show-toplevel")
    return out or None


# ------------------------------------------------------------------ commit side


def commit_facts(repo: str, rev: str):
    fmt = "%H%x1f%P%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%ct%x1f%cI%x1f%s"
    raw = _git(repo, "log", "-1", "--format=" + fmt, rev)
    if not raw:
        return None
    parts = raw.split("\x1f")
    if len(parts) < 9:
        return None
    sha, parents, an, ae, cn, ce, ct, ciso, subject = parts[:9]
    parent_list = [p for p in parents.split() if p]
    trailer_raw = _git(repo, "log", "-1", "--format=%(trailers:key=Agent,valueonly)", rev) or ""
    trailers = [t.strip() for t in trailer_raw.splitlines() if t.strip()]
    return {
        "sha": sha,
        "short": sha[:7],
        "parents": parent_list,
        "parent": parent_list[0] if parent_list else "",
        "author_name": an,
        "author_email": ae,
        "committer_name": cn,
        "committer_email": ce,
        "commit_ts": int(ct) if ct.isdigit() else 0,
        "committed_iso": ciso,
        "subject": subject,
        "trailers": trailers,
    }


def id_flags(value: str) -> dict:
    known = value.lower() in ALLOWED_IDS
    return {"value": value, "known": known, "flagged": bool(value) and not known}


def corroborate(repo_real: str, facts: dict, hooks: list, tools: list) -> dict:
    """Machinery evidence for one commit. Ambiguity is reported, never resolved."""
    result = {
        "hook_records": [],
        "tool_records": [],
        "hook_ids": [],
        "tool_ids": [],
        "hook_pairs": [],
        "tool_pairs": [],
        "notes": [],
        "ambiguous": False,
        "authoritative": None,
    }

    # --- hook level: exact join, repo + head == the commit's parent -----------
    parent = facts["parent"]
    for rec in hooks:
        if norm_repo(str(rec.get("repo", ""))) != repo_real:
            continue
        if parent and str(rec.get("head", "")) == parent:
            result["hook_records"].append(rec)
    if not parent:
        result["notes"].append("root commit: no parent, the hook stream cannot join by head")

    hook_pairs = sorted(
        {
            (str(r.get("agent_id", "")), str(r.get("trace_id", "")))
            for r in result["hook_records"]
        }
    )
    result["hook_pairs"] = ["%s|%s" % (a, t or "<empty-trace>") for a, t in hook_pairs]
    result["hook_ids"] = sorted({a for a, _ in hook_pairs if a})
    if len(hook_pairs) > 1:
        result["ambiguous"] = True
        result["notes"].append(
            "hook-level records from more than one run share this parent (%s) "
            "-> the run cannot be picked" % ", ".join(result["hook_pairs"])
        )
    elif len(hook_pairs) == 1 and not hook_pairs[0][1]:
        result["ambiguous"] = True
        result["notes"].append(
            "hook-level record carries an EMPTY trace_id (--no-verify bypass or a commit "
            "without run context) -> undecidable by the X2-c rule; a time approximation "
            "will not be used as an attribution"
        )

    # --- tool level: wall-clock window, only when unambiguous -----------------
    ts = facts["commit_ts"]
    for rec in tools:
        if norm_repo(str(rec.get("repo", ""))) != repo_real:
            continue
        classes = rec.get("classes") or ([rec.get("class")] if rec.get("class") else [])
        if "commit" not in classes:
            continue
        try:
            rts = float(rec.get("ts", 0))
        except (TypeError, ValueError):
            continue
        if ts and not (ts - TOOL_WINDOW_BACK <= rts <= ts + TOOL_WINDOW_FORWARD):
            continue
        result["tool_records"].append(rec)

    tool_pairs = sorted(
        {
            (str(r.get("agent_id", "")), str(r.get("trace_id", "")))
            for r in result["tool_records"]
        }
    )
    result["tool_pairs"] = ["%s|%s" % (a, t or "<empty-trace>") for a, t in tool_pairs]
    result["tool_ids"] = sorted({a for a, _ in tool_pairs if a})
    if len(tool_pairs) > 1:
        if hook_pairs:
            # The hook-level join already fired exactly. A crowded time window is
            # not proof of ambiguity, it is proof that the tool stream is a coarse
            # instrument. Recorded, not escalated.
            result["notes"].append(
                "tool-level records from more than one run fall in the join window (%s) "
                "-> the tool stream is not used as evidence here (X2-c); the hook-level "
                "join is exact (head == the commit parent)" % ", ".join(result["tool_pairs"])
            )
        else:
            result["ambiguous"] = True
            result["notes"].append(
                "tool-level records from more than one run fall in the join window (%s) "
                "-> the join is a time approximation, so it is NOT used as evidence (X2-c)"
                % ", ".join(result["tool_pairs"])
            )

    # Authoritative-source hierarchy (2026-09-13): the hook-level join is exact
    # (repo + head == the commit parent), so it decides on its own; the tool-level
    # stream is a wall-clock approximation and is only consulted when the hook
    # stream is silent. Both streams still get printed -- the reader sees the
    # disagreement, the verdict does not pretend to resolve it.
    if len(hook_pairs) > 1 or (len(hook_pairs) == 1 and not hook_pairs[0][1]):
        result["authoritative"] = None
        result["corroborated_ids"] = []
    elif len(hook_pairs) == 1:
        result["authoritative"] = "hook"
        result["corroborated_ids"] = [hook_pairs[0][0]] if hook_pairs[0][0] else []
        if result["tool_ids"] and hook_pairs[0][0] not in result["tool_ids"]:
            result["notes"].append(
                "the tool-level stream names a different id (%s) than the exact hook-level "
                "join (%s) -> the exact join wins, and the difference is recorded"
                % (", ".join(result["tool_ids"]), hook_pairs[0][0])
            )
    elif len(tool_pairs) == 1 and tool_pairs[0][1]:
        result["authoritative"] = "tool"
        result["corroborated_ids"] = [tool_pairs[0][0]] if tool_pairs[0][0] else []
        result["notes"].append("hook-level stream silent: corroboration rests on the tool-level join")
    else:
        result["authoritative"] = None
        result["corroborated_ids"] = []

    if not result["hook_records"] and not result["tool_records"]:
        result["notes"].append(
            "no hook-level and no tool-level record for this commit (pre-hook history, "
            "--no-verify, or a commit made outside a run)"
        )
    elif not result["hook_records"]:
        result["notes"].append(
            "hook-level record absent: corroboration rests on the tool-level stream only"
        )
    return result


def evaluate(facts: dict, corroboration: dict, declarations: list) -> dict:
    """Combine declarations and machinery evidence into one verdict."""
    declared = sorted({d["value"] for d in declarations if d.get("value")})
    corroborated = corroboration["corroborated_ids"]
    reasons = []
    ciso = facts.get("committed_iso") or ""
    boundary_note = bool(ciso) and ciso[:10] < BOUNDARY_DATE

    if corroboration["ambiguous"]:
        verdict = UNDETERMINED
        reasons.append("evidence is ambiguous -- 不可判 (no approximation used)")
    elif not corroborated:
        verdict = UNDETERMINED
        if not declared:
            reasons.append("no declaration and no corroboration -> 不可判")
        elif boundary_note:
            reasons.append(
                "pre-boundary commit: the git signature has no attribution value "
                "(section 8) and there is no machine evidence -> 不可判"
            )
        else:
            reasons.append(
                "declaration present but corroboration missing -> 不可判 "
                "(the declaration is visible, not corroborated)"
            )
    elif not declared:
        verdict = UNDETERMINED
        reasons.append(
            "machine evidence names %s but no declaration exists -> 不可判" % "/".join(corroborated)
        )
    else:
        extra = [d for d in declared if d not in corroborated]
        if extra:
            verdict = MISMATCH
            reasons.append(
                "declaration %s != corroboration %s" % ("/".join(extra), "/".join(corroborated))
            )
        else:
            verdict = CONSISTENT
            reasons.append("declaration and corroboration agree on %s" % "/".join(corroborated))

    flagged = [d["value"] for d in declarations if d.get("flagged")] + [
        i for i in corroborated if i.lower() not in ALLOWED_IDS
    ]
    return {
        "verdict": verdict,
        "declared_ids": declared,
        "corroborated_ids": corroborated,
        "reasons": reasons,
        "boundary": boundary_note,
        "flagged_ids": sorted(set(flagged)),
    }


# --------------------------------------------------------------------- entries


def check_commit(repo: str, rev: str, hooks: list, tools: list) -> dict:
    repo_real = norm_repo(repo)
    facts = commit_facts(repo, rev)
    if facts is None:
        return {"entry": "commit", "error": "cannot resolve revision: %s" % rev}
    declarations = [
        {
            "kind": "trailer",
            "value": t,
            "source": "git %(trailers:key=Agent)",
            "id_flags": id_flags(t),
        }
        for t in facts["trailers"]
    ]
    corroboration = corroborate(repo_real, facts, hooks, tools)
    verdict = evaluate(facts, corroboration, declarations)
    return {
        "entry": "commit",
        "repo": repo_real,
        "target": rev,
        "commit": facts,
        "declarations": declarations,
        "corroboration": corroboration,
        "verdict": verdict,
    }


def _card_classify(path: Path) -> dict:
    """Reuse the A2 checker so both entry points read cards identically."""
    spec = importlib.util.spec_from_file_location(
        "check_card_author", str(Path(__file__).resolve().parent / "check_card_author.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.classify(path)


def check_file(repo: str, path: str, hooks: list, tools: list) -> dict:
    repo_real = norm_repo(repo)
    # a relative path is relative to the REPOSITORY, not to whatever directory the
    # caller happened to run from -- otherwise `--file a.txt` silently resolves
    # against the shell's cwd and reports "path does not exist"
    given = Path(path).expanduser()
    abs_path = given if given.is_absolute() else Path(repo_real) / given
    try:
        rel = str(abs_path.resolve().relative_to(Path(repo_real)))
    except ValueError:
        rel = str(abs_path)
    sha = _git(repo, "log", "-1", "--format=%H", "--", rel)
    if not sha:
        if not abs_path.exists():
            return {
                "entry": "file",
                "repo": repo_real,
                "path": rel,
                "error": "path does not exist: %s" % rel,
            }
        # Untracked / never committed: there is no history, so there is nothing to
        # attribute. That is an answer ("不可判"), not a crash.
        return {
            "entry": "file",
            "repo": repo_real,
            "path": rel,
            "target": None,
            "commit": None,
            "declarations": [],
            "corroboration": {
                "hook_records": [],
                "tool_records": [],
                "notes": ["no commit touches this path yet (untracked or never committed)"],
                "ambiguous": False,
                "authoritative": None,
                "corroborated_ids": [],
            },
            "verdict": {
                "verdict": UNDETERMINED,
                "declared_ids": [],
                "corroborated_ids": [],
                "reasons": ["the path has no commit history -> 不可判"],
                "boundary": False,
                "flagged_ids": [],
            },
        }
    base = check_commit(repo, sha, hooks, tools)
    return {
        "entry": "file",
        "repo": repo_real,
        "path": rel,
        "target": sha,
        "commit": base.get("commit"),
        "declarations": base.get("declarations", []),
        "corroboration": base.get("corroboration", {}),
        "verdict": base.get("verdict", {}),
    }


def check_card(repo: str, path: str, hooks: list, tools: list) -> dict:
    repo_real = norm_repo(repo)
    p = Path(path).expanduser()
    card = _card_classify(p)
    declarations = []
    value = card.get("value")
    if card.get("status") in ("ok", "legacy", "unknown-id") and value:
        declarations.append(
            {
                "kind": "card-author",
                "value": value,
                "source": "frontmatter (%s)" % card.get("status"),
                "id_flags": id_flags(value),
            }
        )
    try:
        card_rel = str(p.resolve().relative_to(Path(repo_real)))
    except ValueError:
        card_rel = str(p)
    base = check_file(repo, card_rel, hooks, tools)
    declarations.extend(base.get("declarations", []))
    corroboration = base.get("corroboration", {})
    facts = base.get("commit") or {"committed_iso": "", "commit_ts": 0}
    verdict = evaluate(facts, corroboration, declarations)
    return {
        "entry": "card",
        "repo": repo_real,
        "path": card_rel,
        "card_status": card.get("status"),
        "target": base.get("target"),
        "commit": facts,
        "declarations": declarations,
        "corroboration": corroboration,
        "verdict": verdict,
    }


# -------------------------------------------------------------------- rendering


def _short(rec: dict) -> str:
    ts = rec.get("ts")
    if isinstance(ts, (int, float)):
        ts = "%.0f" % ts
    return "ts=%s action=%s agent=%s trace=%s head=%s" % (
        ts,
        rec.get("action", rec.get("class", "")),
        rec.get("agent_id", ""),
        rec.get("trace_id", "") or "<empty>",
        str(rec.get("head", ""))[:7],
    )


VERDICT_MARK = {
    CONSISTENT: "[OK]   一致",
    MISMATCH: "[DIFF] 不一致",
    UNDETERMINED: "[??]   不可判",
}


def render(result: dict, quiet: bool = False) -> int:
    if result.get("error"):
        print("ERROR: %s" % result["error"])
        return EXIT_ERROR

    verdict = result["verdict"]
    v = verdict["verdict"]

    if quiet:
        print("%s: %s" % (v, "; ".join(verdict["reasons"])))
        return {CONSISTENT: EXIT_CONSISTENT, MISMATCH: EXIT_MISMATCH}.get(v, EXIT_UNDETERMINED)

    facts = result.get("commit") or {}
    print("=== A5 归因自查 (ф2) ===")
    print("entry      : %s" % result.get("entry"))
    print("target     : %s%s" % (result.get("target") or "(no commit)",
                                 "  (path: %s)" % result.get("path", "") if result.get("path") else ""))
    print("repo       : %s" % result.get("repo"))
    if facts.get("sha"):
        print("commit     : %s  %s  %s" % (facts["sha"][:7], facts.get("committed_iso", ""),
                                           facts.get("subject", "")[:60]))
    if result.get("card_status"):
        print("card status: %s" % result["card_status"])
    print("boundary   : %s (section 8: before %s the git signature is not evidence)" % (
        "before boundary" if verdict.get("boundary") else "at/after boundary", BOUNDARY_DATE))

    print("--- 声明 (declaration) ---")
    if result.get("declarations"):
        for d in result["declarations"]:
            flag = "  [FLAG] 值域外 id (flagged, not rejected)" if d.get("flagged") else ""
            print("  %-12s : %-10s [%s]%s" % (d["kind"], d["value"], d["source"], flag))
    else:
        print("  (none)       : no trailer and no card author field")

    print("--- 旁证 (corroboration) ---")
    corr = result.get("corroboration") or {}
    for label in ("hook", "tool"):
        recs = corr.get(label + "_records", [])
        if recs:
            print("  %s-level  : %d record(s)" % (label, len(recs)))
            for rec in recs[:4]:
                print("      %s" % _short(rec))
        else:
            print("  %s-level  : (none)" % label)
    for note in corr.get("notes", []):
        print("  note      : %s" % note)

    print("--- 判定 (verdict) ---")
    print("  %s : %s" % (VERDICT_MARK[v], v))
    for reason in verdict["reasons"]:
        print("  reason    : %s" % reason)
    if verdict.get("flagged_ids"):
        print("  flagged   : %s (out of the agreed set %s -- recorded, not rejected)"
              % (", ".join(verdict["flagged_ids"]), "/".join(ALLOWED_IDS)))
    return {CONSISTENT: EXIT_CONSISTENT, MISMATCH: EXIT_MISMATCH}.get(v, EXIT_UNDETERMINED)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="A5 (ф2) attribution self-check: declaration + corroboration, or 不可判"
    )
    parser.add_argument("target", nargs="?", help="commit-ish, file path, or card path")
    parser.add_argument("--commit", metavar="REV", help="entry: one commit")
    parser.add_argument("--file", metavar="PATH", help="entry: last commit touching a file")
    parser.add_argument("--card", metavar="PATH", help="entry: a four-party wiki card")
    parser.add_argument("--repo", metavar="PATH", help="repository root (default: derived from the target)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--quiet", action="store_true", help="verdict line only")
    args = parser.parse_args(argv)

    given = [bool(args.commit), bool(args.file), bool(args.card)]
    if sum(given) > 1:
        print("ERROR: pick ONE entry (--commit / --file / --card)", file=sys.stderr)
        return EXIT_ERROR
    if not any(given) and not args.target:
        print("ERROR: give a target, or --commit / --file / --card", file=sys.stderr)
        return EXIT_ERROR

    target = args.target or args.commit or args.file or args.card
    mode = "commit" if args.commit else ("file" if args.file else ("card" if args.card else None))

    if mode is None:
        looks_like_path = os.path.sep in target or target.startswith("~") or os.path.exists(
            os.path.expanduser(target)
        )
        if looks_like_path or target.endswith(".md"):
            mode = "card" if target.endswith(".md") else "file"
        else:
            mode = "commit"

    if mode == "commit":
        repo = args.repo or repo_root(os.getcwd())
    else:
        p = Path(target).expanduser()
        parent = p.parent if str(p.parent) not in ("", ".") else Path(".")
        repo = args.repo or repo_root(str(parent))
    if not repo:
        print("ERROR: %r is not inside a git repository" % target, file=sys.stderr)
        return EXIT_ERROR

    hook_path = hook_stream_path()
    tool_path = tool_stream_path()
    hooks, hook_state = load_stream(hook_path)
    tools, tool_state = load_stream(tool_path)

    if mode == "commit":
        result = check_commit(repo, target, hooks, tools)
    elif mode == "file":
        result = check_file(repo, target, hooks, tools)
    else:
        result = check_card(repo, target, hooks, tools)

    if result.get("error"):
        print("ERROR: %s" % result["error"], file=sys.stderr)
        return EXIT_ERROR

    result["streams"] = {
        "hook": {"path": str(hook_path), "records": len(hooks), "state": hook_state},
        "tool": {"path": str(tool_path), "records": len(tools), "state": tool_state},
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        v = result["verdict"]["verdict"]
        return {CONSISTENT: EXIT_CONSISTENT, MISMATCH: EXIT_MISMATCH}.get(v, EXIT_UNDETERMINED)

    if not args.quiet:
        print("# streams    : hook=%s (%d records, %s) | tool=%s (%d records, %s)" % (
            hook_path, len(hooks), hook_state, tool_path, len(tools), tool_state))
    return render(result, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
