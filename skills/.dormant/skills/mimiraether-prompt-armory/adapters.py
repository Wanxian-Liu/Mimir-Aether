#!/usr/bin/env python3
"""mimiraether-prompt-armory adapters — six-library unified search layer."""

from __future__ import annotations
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ── Path constants ─────────────────────────────────────────────────

_WORKSPACE = Path.home() / ".openclaw" / "workspace"
_PROJECTS  = Path.home() / ".openclaw" / "projects"

CSV_PATH         = _WORKSPACE / "awesome-chatgpt-prompts" / "prompts.csv"
SYSTEM_LEAKS_DIR = _WORKSPACE / "awesome-system-prompts" / "leaks"
AGENCY_DIR       = _PROJECTS / "agency-agents"
AGENCY_REGISTRY  = AGENCY_DIR / "roles_registry.json"
ROLES_DIR        = _WORKSPACE / "roles"
WORKSPACE_ROOT   = _WORKSPACE

# Cursor rules: probe actual path
CURSOR_MDC_DIR = None
for _cd in [Path.home() / ".cursor", Path("/home/<user>/.cursor")]:
    if _cd.exists() and list(_cd.rglob("*.mdc")):
        CURSOR_MDC_DIR = _cd
        break

# ── Utilities ──────────────────────────────────────────────────────

def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, cwd=str(Path.home()))
        return r.stdout.strip()
    except Exception:
        return ""

def _grep_files(directory, query, glob="*.md", limit=20):
    if not directory.exists():
        return []
    # Try rg first
    try:
        res = subprocess.run(
            ["rg", "-l", "-i", query, str(directory), "--glob", glob],
            capture_output=True, text=True, timeout=5)
        if res.returncode in (0, 1) and res.stdout.strip():
            return [Path(p) for p in res.stdout.strip().split("\n") if p][:limit]
    except (FileNotFoundError, Exception):
        pass
    # Fallback to grep
    try:
        res = subprocess.run(
            ["grep", "-r", "-l", "-i", "--include", glob, query, str(directory)],
            capture_output=True, text=True, timeout=5)
        if res.returncode in (0, 1) and res.stdout.strip():
            return [Path(p) for p in res.stdout.strip().split("\n") if p][:limit]
    except Exception:
        pass
    return []

def _read_full(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

def _preview(text, max_chars=200):
    t = text.strip()
    return t[:max_chars] + ("..." if len(t) > max_chars else "")

def _extract_yfm(filepath):
    """Extract simple YAML frontmatter (key: value only)."""
    text = _read_full(filepath)
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    yfm_text = text[3:end].strip()
    result = {}
    for line in yfm_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip().strip('"').strip("'")
    return result

def _body_after_yfm(filepath):
    text = _read_full(filepath)
    if not text.startswith("---"):
        return text
    end = text.find("---", 3)
    return text[end + 3:].strip() if end != -1 else text

def _split_csv(line):
    """Split CSV line respecting quoted fields."""
    parts = []
    current = []
    in_quotes = False
    for c in line:
        if c == '"':
            in_quotes = not in_quotes
        elif c == ',' and not in_quotes:
            parts.append(''.join(current))
            current = []
        else:
            current.append(c)
    parts.append(''.join(current))
    return parts


# ── Adapters ───────────────────────────────────────────────────────

def _search_csv(query, limit=10):
    """Search awesome-chatgpt-prompts CSV (1695 rows, act/prompt/for_devs/type/contributor)."""
    if not CSV_PATH.exists():
        return []
    ql = query.lower()
    results = []
    seen = set()

    # L1: awk on act column (case-insensitive fuzzy)
    for _ in range(3):  # retry
        awk_out = _run(
            f'''awk -F',' 'NR>1 && tolower($1) ~ tolower("{re.escape(ql)}")' '''
            f'''"{CSV_PATH}" | head -{limit}''', timeout=15)
        if awk_out or _ == 2:
            break
    for line in awk_out.split("\n")[:limit]:
        if not line.strip():
            continue
        parts = _split_csv(line)
        if len(parts) < 2:
            continue
        name = parts[0].strip().strip('"')
        if name in seen:
            continue
        seen.add(name)
        prompt = parts[1].strip().strip('"')
        results.append({
            "name": name, "source": "awesome-chatgpt-prompts", "score": 30,
            "preview": _preview(prompt), "full_text": prompt,
            "metadata": {
                "type": parts[3].strip().strip('"') if len(parts) > 3 else "",
                "for_devs": parts[2].strip().strip('"') if len(parts) > 2 else ""}
        })

    # L2: grep full-text supplement
    if len(results) < limit:
        try:
            extra_lines = _run(
                f'grep -i "{re.escape(query)}" "{CSV_PATH}" | head -{limit - len(results)}',
                timeout=10)
            for line in extra_lines.split("\n"):
                if not line.strip():
                    continue
                parts = _split_csv(line)
                if len(parts) >= 2:
                    name = parts[0].strip().strip('"')
                    if name not in seen:
                        seen.add(name)
                        results.append({
                            "name": name, "source": "awesome-chatgpt-prompts",
                            "score": 30, "preview": _preview(parts[1].strip().strip('"')),
                            "full_text": parts[1].strip().strip('"'), "metadata": {}})
                if len(results) >= limit:
                    break
        except Exception:
            pass

    return results[:limit]


def _search_md_dir(directory, query, limit=10, source_prefix="", score=90):
    """Search a Markdown directory (used for system-prompts and roles/)."""
    if not directory.exists():
        return []
    ql = query.lower()
    results = []
    seen = set()

    # L1: filename match
    for f in sorted(directory.rglob("*.md"))[:50]:
        if ql in f.stem.lower():
            seen.add(f.stem)
            text = _read_full(f)
            company = f.parent.name if f.parent != directory else ""
            s = f"{source_prefix}/{company}" if company else source_prefix
            results.append({
                "name": f.stem, "source": s, "score": score,
                "preview": _preview(text), "full_text": text,
                "metadata": {"path": str(f)}})

    # L2: grep full-text supplement
    if len(results) < limit:
        extra = _grep_files(directory, query, "*.md", limit=limit - len(results))
        for ep in extra:
            if ep.stem in seen:
                continue
            seen.add(ep.stem)
            text = _read_full(ep)
            company = ep.parent.name if ep.parent != directory else ""
            s = f"{source_prefix}/{company}" if company else source_prefix
            results.append({
                "name": ep.stem, "source": s, "score": score,
                "preview": _preview(text), "full_text": text,
                "metadata": {"path": str(ep)}})

    return results[:limit]


def _search_agency(query, limit=10):
    """Search agency-agents (22 categories, 178 roles, YAML frontmatter)."""
    if not AGENCY_DIR.exists():
        return []
    ql = query.lower()
    results = []
    seen = set()

    # L1: roles_registry.json — name + trigger_keywords
    registry = []
    if AGENCY_REGISTRY.exists():
        try:
            registry = json.loads(AGENCY_REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            pass

    for role in registry:
        name = role.get("name", "")
        keywords = role.get("trigger_keywords", [])
        desc = role.get("description", "")
        name_match = ql in name.lower()
        kw_match = any(ql in str(kw).lower() for kw in keywords) if keywords else False

        if name_match or kw_match:
            seen.add(name)
            # Find and read the actual .md file
            cat = role.get("category", "")
            fpath = AGENCY_DIR / cat / f"{name}.md"
            text = _read_full(fpath) if fpath.exists() else desc
            body = _body_after_yfm(fpath) if fpath.exists() else ""
            results.append({
                "name": name,
                "source": f"agency/{cat}",
                "score": 70,
                "preview": _preview(desc + "\n" + body[:100]) if desc else _preview(body),
                "full_text": text,
                "metadata": {
                    "emoji": role.get("emoji", ""),
                    "vibe": role.get("vibe", ""),
                    "trigger_keywords": keywords,
                    "category": cat,
                    "path": str(fpath) if fpath.exists() else ""}
            })

    # L2: grep full-text supplement
    if len(results) < limit:
        extra = _grep_files(AGENCY_DIR, query, "*.md", limit=limit - len(results))
        for ep in extra:
            if ep.stem in seen or ep.parent.name == AGENCY_DIR.name:
                continue
            seen.add(ep.stem)
            cat = ep.parent.name
            yfm = _extract_yfm(ep)
            body = _body_after_yfm(ep)
            results.append({
                "name": yfm.get("name", ep.stem),
                "source": f"agency/{cat}",
                "score": 70,
                "preview": _preview(yfm.get("description", "") + "\n" + body[:100])
                           if yfm.get("description") else _preview(body),
                "full_text": _read_full(ep),
                "metadata": {
                    "emoji": yfm.get("emoji", ""),
                    "vibe": yfm.get("vibe", ""),
                    "category": cat,
                    "path": str(ep)}
            })

    return results[:limit]


def _search_mdc(query, limit=10):
    """Search Cursor rules (~/.cursor/*.mdc)."""
    results = []
    if not CURSOR_MDC_DIR or not CURSOR_MDC_DIR.exists():
        return results
    ql = query.lower()
    seen = set()

    # L1: filename match
    for f in sorted(CURSOR_MDC_DIR.rglob("*.mdc")):
        if f.is_dir() or "/cache/" in str(f) or "/plugins/" in str(f):
            continue
        if ql in f.stem.lower():
            seen.add(f.stem)
            text = _read_full(f)
            yfm = _extract_yfm(f)
            results.append({
                "name": f.stem, "source": "cursor-rule", "score": 50,
                "preview": _preview(yfm.get("description", "") or text),
                "full_text": text,
                "metadata": {"path": str(f), "frontmatter": yfm}})

    # L2: grep full-text supplement
    if len(results) < limit:
        extra = _grep_files(CURSOR_MDC_DIR, query, "*.mdc", limit=limit - len(results))
        for ep in extra:
            if ep.stem in seen:
                continue
            seen.add(ep.stem)
            text = _read_full(ep)
            yfm = _extract_yfm(ep)
            results.append({
                "name": ep.stem, "source": "cursor-rule", "score": 50,
                "preview": _preview(text), "full_text": text,
                "metadata": {"path": str(ep), "frontmatter": yfm}})

    return results[:limit]


def _search_root_md(query, limit=10):
    """Search loose .md files in workspace root (exclude known subdirs)."""
    if not WORKSPACE_ROOT.exists():
        return []
    ql = query.lower()
    excluded = {"awesome-chatgpt-prompts", "awesome-system-prompts", "roles"}
    results = []
    seen = set()

    for f in WORKSPACE_ROOT.glob("*.md"):
        if ql in f.stem.lower():
            seen.add(f.stem)
            text = _read_full(f)
            results.append({
                "name": f.stem, "source": "workspace", "score": 20,
                "preview": _preview(text), "full_text": text,
                "metadata": {"path": str(f)}})

    # L2: grep full-text (exclude subdirs)
    if len(results) < limit:
        extra = _grep_files(WORKSPACE_ROOT, query, "*.md", limit=limit - len(results))
        for ep in extra:
            if ep.stem in seen:
                continue
            if any(ex in str(ep) for ex in excluded):
                continue
            seen.add(ep.stem)
            text = _read_full(ep)
            results.append({
                "name": ep.stem, "source": "workspace", "score": 20,
                "preview": _preview(text), "full_text": text,
                "metadata": {"path": str(ep)}})

    return results[:limit]


# ── Unified entry ──────────────────────────────────────────────────

def search_all(query, limit=10, scenario="auto"):
    """Cross-6-library parallel search, returns sorted by score desc.

    Args:
        query: Search keywords
        limit: Max results to return
        scenario: "role" (L1 priority), "recommend" (L1+L2 equal),
                  "compare" (at least 1 per library), "auto" (auto-detect)

    Returns:
        list[dict] with keys: name, source, score, preview, full_text, metadata
    """
    if not query or not query.strip():
        return []

    libraries = [
        ("roles", lambda: _search_md_dir(ROLES_DIR, query, limit, "roles", 100)),
        ("system-prompts", lambda: _search_md_dir(SYSTEM_LEAKS_DIR, query, limit, "system-prompts", 90)),
        ("agency", lambda: _search_agency(query, limit)),
        ("cursor-rules", lambda: _search_mdc(query, limit)),
        ("chatgpt-prompts", lambda: _search_csv(query, limit)),
        ("workspace", lambda: _search_root_md(query, limit)),
    ]

    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fn): name for name, fn in libraries}
        for future in concurrent.futures.as_completed(futures, timeout=5):
            try:
                all_results.extend(future.result())
            except Exception:
                pass

    # Sort by score desc, then by name
    all_results.sort(key=lambda r: (-r["score"], r["name"]))

    # Scenario: "compare" — ensure at least 1 per library
    if scenario == "compare":
        seen_sources = set()
        final = []
        rest = []
        for r in all_results:
            if r["source"] not in seen_sources:
                seen_sources.add(r["source"])
                final.append(r)
            else:
                rest.append(r)
        final.extend(rest)
        return final[:limit]

    return all_results[:limit]


# ── CLI ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Search mode
        results = search_all(sys.argv[1], limit=10)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        # Self-check mode
        print("All adapters loaded: OK")
        print(f"  CSV:        {'found' if CSV_PATH.exists() else 'MISSING'}")
        print(f"  System:     {'found' if SYSTEM_LEAKS_DIR.exists() else 'MISSING'}")
        print(f"  Agency:     {'found' if AGENCY_DIR.exists() else 'MISSING'}")
        print(f"  Roles:      {'found' if ROLES_DIR.exists() else 'MISSING'}")
        print(f"  Cursor:     {'found' if CURSOR_MDC_DIR else 'MISSING'}")
        print(f"  Workspace:  {'found' if WORKSPACE_ROOT.exists() else 'MISSING'}")
