"""Run-level provenance context (Q3-B / A2 + G-4 merged).

Why this module exists
----------------------
2026-09-12 incident (four-party card ``唤醒单例与并发写治理-Q3``): two runs of the
*same* gateway process interleaved commits into this repo, and **neither the git
author field nor the gateway log could tell them apart**. Root cause was not a
missing lock - it was a missing *field*:

* the repo used one git identity for every writer (wanxian <wanxian@worldweaver.ai>),
* the gateway log recorded runs but not *what triggered them*,
* git tool invocations were not logged at all (``grep git`` in the log -> 0 hits).

So "no evidence of duplicate wakeups" was really "**not measurable under the
current log design**" (Hermes audit sec.4, 2026-09-12). This module adds the
minimum fields needed to make run provenance measurable:

``trace_id``       - per-run id (API path reuses ``run_<uuid>``; local path mints one)
``trigger_source`` - feishu / api / buzz-watcher / watchdog / cron / self-restart ...
``agent_id``       - who owns the process (default ``mimir``, env ``MIMIR_AGENT_ID``)
``session_key``    - which session the run belongs to (duplicate-wake detection)

Plus :func:`audit_git_tool_call`: every ``git`` mutation attempted through a tool
call is recorded with **repo + command class(es)** (``commit`` / ``amend`` /
``push`` ...) into ``logs/git-audit.jsonl`` and one ``[GIT-AUDIT]`` log line -
SRE acceptance criterion from the same receipt.

X-series follow-up (card ``2026-09-12-四方讨论-审计流三处缺口-Q3后续.md``,
Hermes receipt 2026-09-12):

* **X1-c** - one record carries the whole *set* of classes
  (``classes: [add, commit, push]``). Real commands are chains, so the old
  first-invocation-only classifier recorded ``add`` and *never* a commit
  (measured: commit-level coverage 0%). ``repo`` is ``expanduser`` +
  ``realpath`` normalised so it can serve as a cross-stream join key.
* **X2-a** - :func:`child_env_injection` hands ``MIMIR_TRACE_ID`` /
  ``MIMIR_AGENT_ID`` to child processes (shells / code sandbox) so the commit
  hook - which runs *outside* this process - can write a non-empty trace and
  the two audit streams finally share a join key.

Design notes
------------
* Thread-local primary, process-wide fallback: tools may run in a worker thread
  (parallel dispatcher), where a contextvar set in the event-loop thread would
  not be visible.
* Everything here is **best-effort and non-blocking**: provenance must never
  break a conversation. All file writes swallow OSError.
* stdlib only.

RS11 pre-probe (four-party ruling sec.29 Q17, 2026-09-14)
-------------------------------------------------------
"Duplicate reply" was observed at the **delivery** layer (same reply text sent
twice, two different ``message_id``, gateway.log 11:39:21 + 11:42:53 on
2026-09-13; >=8 groups since 08-18) yet could **not** be reproduced from the
session transcripts. Root cause is therefore either the delivery layer or
"stale history slice" - both need a join key that survives across runs.

So every run now carries the two hashes of the message pair::

    [RUN] ... in_sha1=<sha1(user text)[:12]>                    # at begin_run
    [RUN] ... phase=finish in_sha1=<..> resp_sha1=<sha1(reply)[:12]>

Two runs with *different* ``in_sha1`` but *identical* ``resp_sha1`` = one reply
delivered twice. **No gate** (ruling: "先拿真数据") - this only records.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from typing import Union
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "agent_id",
    "begin_run",
    "end_run",
    "finish_run",
    "sha1_12",
    "current_run",
    "resolve_trigger_source",
    "classify_git_command",
    "classify_git_command_classes",
    "audit_git_tool_call",
    "child_env_injection",
    "apply_child_env",
    "GIT_WRITE_CLASSES",
    "PROVENANCE_ENV_KEYS",
]

# Waking entry points known to exist (sec.4-A-5 of the Q3 card).
# Order matters: the *first* matching marker wins.
_TRIGGER_MARKERS: Tuple[Tuple[str, str], ...] = (
    ("【自动唤醒】", "buzz-watcher"),
    ("Buzz收件箱有", "buzz-watcher"),
    ("discussion-watchdog", "watchdog"),
    ("【讨论室唤醒】", "watchdog"),
    ("自动唤醒", "auto-wake"),
)

_PLATFORM_TRIGGERS: Dict[str, str] = {
    "feishu": "feishu",
    "local": "cli",
    "cli": "cli",
    "api": "api",
    "api_server": "api",
    "webhook": "webhook",
    "discord": "discord",
    "telegram": "telegram",
    "slack": "slack",
}

# git subcommands that *change* history or remote state - these are the ones an
# audit needs (read-only commands are classified as "read" and still counted).
_GIT_WRITE_CLASSES: Dict[str, str] = {
    "commit": "commit",
    "push": "push",
    "merge": "merge",
    "rebase": "rebase",
    "reset": "reset",
    "revert": "revert",
    "cherry-pick": "cherry-pick",
    "tag": "tag",
    "stash": "stash",
    "checkout": "checkout",
    "switch": "switch",
    "restore": "restore",
    "clean": "clean",
    "am": "am",
    "init": "init",
    "clone": "clone",
    "fetch": "fetch",
    "pull": "pull",
    "apply": "apply",
    "rm": "rm",
    "mv": "mv",
}
GIT_WRITE_CLASSES = frozenset(_GIT_WRITE_CLASSES)

# Callers name themselves in their own vocabulary (the buzz watcher posts
# metadata.source="buzz-inbox-watcher"). Normalise so one source has one name
# in the audit trail -- otherwise "duplicate wake" analysis compares apples to
# oranges.
_TRIGGER_ALIASES: Dict[str, str] = {
    "buzz-inbox-watcher": "buzz-watcher",
    "buzz_inbox_watcher": "buzz-watcher",
    "discussion-watchdog": "watchdog",
    "self_restart": "self-restart",
    "selfrestart": "self-restart",
}


def _normalize_trigger(value: str) -> str:
    key = str(value).strip()
    return _TRIGGER_ALIASES.get(key, _TRIGGER_ALIASES.get(key.lower(), key))

_GIT_READ_CLASSES = frozenset(
    {"status", "log", "diff", "show", "branch", "rev-parse", "ls-files", "grep", "remote", "config"}
)

# List form: subprocess.run(["git", "push"]) inside execute_code -- there is no
# shell command position to anchor on, so the quoted-token form is matched.
_GIT_LIST_RE = re.compile(r"['\"]git['\"]\s*,\s*['\"](?P<sub>[a-z][a-z-]*)['\"]")

# ``git commit --amend`` is judged inside the invocation's own span, so
# "git commit -m x && git commit --amend" classifies as [commit, amend].
_AMEND_RE = re.compile(r"--amend\b")

# "git" in a real *command position* (start, after ; | & ( or after wrappers such
# as sudo/env/xargs), not as an argument of something else.
# A separator may be followed by more separators/space ("a && git push",
# "; git commit"): the run of separators is consumed as one boundary.
_GIT_INVOCATION_RE = re.compile(
    r"(?:^|[;&|()\n]|\b(?:sudo|env|time|nice|nohup|xargs|command|then|do)\s)"
    r"[\s;&|()]*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"git\s+(?P<sub>[a-z][a-z-]*)"
)

_thread_ctx = threading.local()
_global_ctx: Optional[Dict[str, Any]] = None
_global_lock = threading.Lock()


def agent_id() -> str:
    """Identity of this process/agent (env ``MIMIR_AGENT_ID`` overrides)."""
    return os.getenv("MIMIR_AGENT_ID") or "mimir"


def _new_trace_id() -> str:
    return "tr_" + uuid.uuid4().hex[:12]


def sha1_12(text: Optional[Union[str, bytes]]) -> str:
    """12-hex-char digest of a message body (RS11 pre-probe join key).

    The **field name** in log lines must stay free of``key`` / ``token`` /
    ``secret`` (tool-output redaction turns those into ``***`` and makes an
    empty value indistinguishable from a real one - RS16 lesson). ``*_sha1`` is
    safe. Empty input -> ``"-"`` so "no body" never looks like a real digest.
    """
    if text is None:
        return "-"
    data = text if isinstance(text, bytes) else str(text).encode("utf-8", "replace")
    if not data:
        return "-"
    return hashlib.sha1(data).hexdigest()[:12]


def resolve_trigger_source(
    explicit: Optional[str] = None,
    platform: Optional[str] = None,
    text: Optional[str] = None,
) -> str:
    """Best-effort answer to "what woke this run up?".

    Precedence: explicit argument > ``MIMIR_TRIGGER_SOURCE`` env > message
    markers (buzz watcher / watchdog) > platform name > ``"unknown"``.

    Platform alone is *not* enough: the buzz watcher wakes Mimir through the API
    and the watchdog through Feishu, so both would look like plain ``api`` /
    ``feishu`` - exactly the blind spot Hermes called out (sec.4, objection 1).
    """
    if explicit:
        return _normalize_trigger(explicit)
    env_val = os.getenv("MIMIR_TRIGGER_SOURCE")
    if env_val:
        return _normalize_trigger(env_val)
    if text:
        for marker, src in _TRIGGER_MARKERS:
            if marker in text:
                return src
    if platform:
        key = str(platform).lower()
        return _PLATFORM_TRIGGERS.get(key, key)
    return "unknown"


def begin_run(
    *,
    trace_id: Optional[str] = None,
    trigger_source: Optional[str] = None,
    session_key: Optional[str] = None,
    platform: Optional[str] = None,
    text: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Open a run and log one ``[RUN]`` provenance line. Returns the context dict."""
    meta_source = None
    if isinstance(metadata, dict):
        meta_source = metadata.get("source") or metadata.get("trigger_source")
    ctx: Dict[str, Any] = {
        "trace_id": trace_id or _new_trace_id(),
        "trigger_source": resolve_trigger_source(
            explicit=trigger_source or meta_source, platform=platform, text=text
        ),
        "agent_id": agent_id(),
        "session_key": session_key or "",
        "platform": platform or "",
        "started_at": time.time(),
        "pid": os.getpid(),
        "thread": threading.current_thread().name,
        # RS11 pre-probe (Q17): inbound message identity
        "in_sha1": sha1_12(text),
        "in_len": len(text or "") if isinstance(text, (str, bytes)) else 0,
    }
    _thread_ctx.run = ctx
    global _global_ctx
    with _global_lock:
        _global_ctx = ctx
    try:
        logger.info(
            "[RUN] trace_id=%s trigger_source=%s agent_id=%s platform=%s session=%s pid=%d "
            "in_sha1=%s in_len=%d",
            ctx["trace_id"], ctx["trigger_source"], ctx["agent_id"],
            ctx["platform"] or "-", ctx["session_key"] or "-", ctx["pid"],
            ctx["in_sha1"], ctx["in_len"],
        )
    except Exception:  # pragma: no cover - logging must never break a run
        pass
    return ctx


def finish_run(
    response_text: Optional[str] = None,
    *,
    already_sent: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """RS11 pre-probe: log the **outbound** half of the run (``resp_sha1``).

    Emitted as a second ``[RUN]`` line (``phase=finish``) so the two halves share
    a prefix and one ``grep "[RUN]"`` sees a whole run::

        [RUN] trace_id=tr_x ... in_sha1=ab.. resp_sha1=cd.. resp_len=2082 elapsed_s=41.7

    Never raises and never changes behaviour (ruling Q17: probe, no gate).
    """
    ctx = current_run() or {}
    resp_sha1 = sha1_12(response_text)
    elapsed = 0.0
    try:
        elapsed = round(time.time() - float(ctx.get("started_at") or time.time()), 3)
    except (TypeError, ValueError):
        elapsed = 0.0
    record: Dict[str, Any] = {
        "trace_id": ctx.get("trace_id", ""),
        "trigger_source": ctx.get("trigger_source", ""),
        "session_key": ctx.get("session_key", ""),
        "in_sha1": ctx.get("in_sha1", "-"),
        "in_len": ctx.get("in_len", 0),
        "resp_sha1": resp_sha1,
        "resp_len": len(response_text or ""),
        "already_sent": bool(already_sent),
        "elapsed_s": elapsed,
    }
    if extra:
        record.update(extra)
    try:
        logger.info(
            "[RUN] phase=finish trace_id=%s trigger_source=%s session=%s in_sha1=%s in_len=%s "
            "resp_sha1=%s resp_len=%s already_sent=%s elapsed_s=%s",
            record["trace_id"], record["trigger_source"], record["session_key"] or "-",
            record["in_sha1"], record["in_len"], resp_sha1, record["resp_len"],
            record["already_sent"], record["elapsed_s"],
        )
    except Exception:  # pragma: no cover - logging must never break a run
        pass
    return record


def end_run() -> None:
    """Close the run context for the current thread."""
    global _global_ctx
    _thread_ctx.run = None
    with _global_lock:
        _global_ctx = None


def current_run() -> Dict[str, Any]:
    """Current run context - thread-local first, else the process-wide fallback."""
    ctx = getattr(_thread_ctx, "run", None)
    if ctx:
        return dict(ctx)
    with _global_lock:
        return dict(_global_ctx) if _global_ctx else {}


def _iter_git_invocations(command: str) -> list:
    """Every git subcommand in a real command position, ordered by offset."""
    found = []
    for match in _GIT_INVOCATION_RE.finditer(command):
        found.append((match.start(), match.group("sub")))
    for match in _GIT_LIST_RE.finditer(command):
        found.append((match.start(), match.group("sub")))
    found.sort(key=lambda item: item[0])
    seen = set()
    ordered = []
    for start, sub in found:
        if (start, sub) in seen:
            continue
        seen.add((start, sub))
        ordered.append((start, sub))
    return ordered


def _class_for_invocation(sub: str, span: str) -> str:
    """Audit class of ONE invocation (``amend`` is distinct from ``commit``)."""
    if sub == "commit":
        return "amend" if _AMEND_RE.search(span) else "commit"
    if sub in _GIT_WRITE_CLASSES:
        return _GIT_WRITE_CLASSES[sub]
    if sub in _GIT_READ_CLASSES:
        return "read"
    return sub or "unknown"


def classify_git_command(command: str) -> Optional[str]:
    """Audit class of the *first* git call in a command, else ``None``.

    Kept as the single-value API (callers that only need "is this a git write?").
    For audit records use :func:`classify_git_command_classes`: a chained
    command (``git add && git commit && git push``) has one class per call, and
    taking only the first is exactly the X1 gap (commit-level coverage 0%).

    ``commit --amend`` reports ``"amend"`` (distinct from ``"commit"``) because
    amend is the operation that rewrote history in the 2026-09-12 incident.
    """
    if not command or not isinstance(command, str):
        return None
    invocations = _iter_git_invocations(command)
    if not invocations:
        return None
    start, sub = invocations[0]
    end = invocations[1][0] if len(invocations) > 1 else len(command)
    return _class_for_invocation(sub, command[start:end])


def classify_git_command_classes(command: str) -> list:
    """Every audited (non read-only) class in the command, first-seen order.

    X1-c ruling (Hermes receipt 2026-09-12): one record, one *set* of classes.
    Real agent commands are chains - ``cd X && cp ... && git add ... && git
    commit ... && git push`` - where the first-only classifier reported ``add``
    forever, so the audit could never answer "which run made this commit".

    Read-only subcommands are dropped (the trail answers "who changed what");
    duplicate classes are collapsed but their order is preserved.
    """
    if not command or not isinstance(command, str):
        return []
    invocations = _iter_git_invocations(command)
    classes = []
    for idx, (start, sub) in enumerate(invocations):
        end = invocations[idx + 1][0] if idx + 1 < len(invocations) else len(command)
        klass = _class_for_invocation(sub, command[start:end])
        if klass == "read" or klass in classes:
            continue
        classes.append(klass)
    return classes


def _extract_command(tool_name: str, arguments: Any) -> str:
    """Pull the shell/code text out of a tool call, whatever its shape."""
    if not isinstance(arguments, dict):
        return ""
    for key in ("command", "code", "script", "cmd"):
        val = arguments.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


# --- X2-a: provenance for CHILD processes -----------------------------------
# The commit hook (scripts/git-hooks/pre-commit) reads $MIMIR_TRACE_ID to stamp
# the B stream, but a hook runs in a *child* process: thread-local run state can
# never reach it (measured 2026-09-12: every B record had trace_id="", and no
# code in the repo ever exported the variable). So the two keys are injected
# into the env of the shells / code sandboxes that tools spawn.
PROVENANCE_ENV_KEYS = ("MIMIR_TRACE_ID", "MIMIR_AGENT_ID")


def child_env_injection() -> Dict[str, str]:
    """Provenance keys for a child process env; empty when no run is open.

    The values are *run tokens*, not credentials - the security question raised
    in the X2-a impact list is name collision, not leakage. Keys are exact
    (``MIMIR_TRACE_ID`` / ``MIMIR_AGENT_ID``), never a ``MIMIR_*`` wildcard, so
    the injection cannot widen itself into unrelated runtime config.
    """
    ctx = current_run()
    trace = ctx.get("trace_id") or ""
    if not trace:
        return {}
    return {
        "MIMIR_TRACE_ID": str(trace),
        "MIMIR_AGENT_ID": str(ctx.get("agent_id") or agent_id()),
    }


def apply_child_env(env: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a copy of ``env`` with :func:`child_env_injection` merged in."""
    out: Dict[str, Any] = dict(env or {})
    try:
        out.update(child_env_injection())
    except Exception:  # pragma: no cover - provenance must never break a run
        pass
    return out


def _audit_log_path() -> Optional[str]:
    override = os.getenv("MIMIR_GIT_AUDIT_LOG")
    if override:
        return override
    home = os.getenv("MIMIR_AETHER_HOME") or os.path.expanduser("~/.mimiraether")
    if not home:
        return None
    return os.path.join(home, "logs", "git-audit.jsonl")


def _normalize_repo_path(raw: str) -> str:
    """``expanduser`` + ``realpath`` so ``repo`` can be a join key (X1 note).

    Same command, two spellings - ``/home/rayliu/wiki`` vs a literal ``~/wiki``
    - made ``repo`` unusable for cross-stream joins (A stream carries trace_id
    but no sha; B stream carries sha but no trace_id; ``repo`` is what ties a
    record to a repository in both).
    """
    text = str(raw).strip().strip("'\"")
    if not text:
        return text
    try:
        return os.path.realpath(os.path.expanduser(text))
    except Exception:  # pragma: no cover - normalisation is best-effort
        return text


def _repo_hint(command: str) -> str:
    """Repo path from ``-C <path>`` / ``cd <path>`` when present, else cwd."""
    if isinstance(command, str):
        m = re.search(r"git\s+-C\s+(\S+)", command) or re.search(r"\bcd\s+(\S+)\s*&&", command)
        if m:
            return _normalize_repo_path(m.group(1))
    return _normalize_repo_path(os.getcwd())


def audit_git_tool_call(tool_name: str, arguments: Any) -> Optional[Dict[str, Any]]:
    """Record a git-mutating tool call. Returns the audit record (or ``None``).

    Fires for any tool carrying shell text (``terminal``, ``execute_code`` ...).
    Every git write in the command is classified and the record carries the whole
    set (X1-c): a single record for ``git add && git commit && git push`` has
    ``classes = ["add", "commit", "push"]``, so no commit-level call is lost.

    Read-only git (status/log/diff/...) is intentionally NOT audited: the trail
    must stay small enough to read, and the question it answers is "which run
    CHANGED which repo, how" (Hermes receipt sec.3, SRE item).
    """
    command = _extract_command(tool_name, arguments)
    if not command:
        return None
    classes = classify_git_command_classes(command)
    if not classes:
        return None

    ctx = current_run()
    record = {
        "ts": time.time(),
        "tool": tool_name,
        "class": classes[0],          # legacy single-value field
        "classes": classes,           # X1-c: authoritative ordered set
        "repo": _repo_hint(command),
        "trace_id": ctx.get("trace_id", ""),
        "trigger_source": ctx.get("trigger_source", "unknown"),
        "agent_id": ctx.get("agent_id") or agent_id(),
        "session_key": ctx.get("session_key", ""),
        "pid": os.getpid(),
        "command": command[:400],
        # kept explicitly so a truncated `command` cannot hide the fact that
        # the audit saw more than the stored 400 chars (X1 note)
        "command_len": len(command),
    }
    try:
        logger.info(
            "[GIT-AUDIT] class=%s repo=%s tool=%s classes=%s trace_id=%s "
            "trigger_source=%s agent_id=%s",
            ",".join(classes), record["repo"], tool_name, ",".join(classes),
            record["trace_id"] or "-", record["trigger_source"], record["agent_id"],
        )
    except Exception:  # pragma: no cover
        pass

    path = _audit_log_path()
    if path:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:  # pragma: no cover - audit trail is best-effort
            pass
    return record
