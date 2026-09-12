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
call is recorded with **repo + command class** (``commit`` / ``amend`` / ``push`` ...)
into ``logs/git-audit.jsonl`` and one ``[GIT-AUDIT]`` log line - SRE acceptance
criterion from the same receipt.

Design notes
------------
* Thread-local primary, process-wide fallback: tools may run in a worker thread
  (parallel dispatcher), where a contextvar set in the event-loop thread would
  not be visible.
* Everything here is **best-effort and non-blocking**: provenance must never
  break a conversation. All file writes swallow OSError.
* stdlib only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "agent_id",
    "begin_run",
    "end_run",
    "current_run",
    "resolve_trigger_source",
    "classify_git_command",
    "audit_git_tool_call",
    "GIT_WRITE_CLASSES",
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
    }
    _thread_ctx.run = ctx
    global _global_ctx
    with _global_lock:
        _global_ctx = ctx
    try:
        logger.info(
            "[RUN] trace_id=%s trigger_source=%s agent_id=%s platform=%s session=%s pid=%d",
            ctx["trace_id"], ctx["trigger_source"], ctx["agent_id"],
            ctx["platform"] or "-", ctx["session_key"] or "-", ctx["pid"],
        )
    except Exception:  # pragma: no cover - logging must never break a run
        pass
    return ctx


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


def classify_git_command(command: str) -> Optional[str]:
    """Return the audit class for a shell command, or ``None`` if it has no git call.

    ``commit --amend`` reports ``"amend"`` (distinct from ``"commit"``) because
    amend is the operation that rewrote history in the 2026-09-12 incident.
    """
    if not command or not isinstance(command, str):
        return None
    match = _GIT_INVOCATION_RE.search(command) or _GIT_LIST_RE.search(command)
    if not match:
        return None
    sub = match.group("sub")
    if sub == "commit":
        return "amend" if re.search(r"--amend\b", command) else "commit"
    if sub in _GIT_WRITE_CLASSES:
        return _GIT_WRITE_CLASSES[sub]
    if sub in _GIT_READ_CLASSES:
        return "read"
    return sub or "unknown"


def _extract_command(tool_name: str, arguments: Any) -> str:
    """Pull the shell/code text out of a tool call, whatever its shape."""
    if not isinstance(arguments, dict):
        return ""
    for key in ("command", "code", "script", "cmd"):
        val = arguments.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


def _audit_log_path() -> Optional[str]:
    override = os.getenv("MIMIR_GIT_AUDIT_LOG")
    if override:
        return override
    home = os.getenv("MIMIR_AETHER_HOME") or os.path.expanduser("~/.mimiraether")
    if not home:
        return None
    return os.path.join(home, "logs", "git-audit.jsonl")


def _repo_hint(command: str) -> str:
    """Cheap repo hint from ``-C <path>`` / ``cd <path>`` when present, else cwd."""
    if isinstance(command, str):
        m = re.search(r"git\s+-C\s+(\S+)", command) or re.search(r"\bcd\s+(\S+)\s*&&", command)
        if m:
            return m.group(1)
    return os.getcwd()


def audit_git_tool_call(tool_name: str, arguments: Any) -> Optional[Dict[str, Any]]:
    """Record a git-mutating tool call. Returns the audit record (or ``None``).

    Fires for any tool carrying shell text (``terminal``, ``execute_code`` ...).
    A shell command may contain several git calls - only the first is classified,
    which is enough for the three classes the audit asks for (commit/amend/push).
    """
    command = _extract_command(tool_name, arguments)
    if not command:
        return None
    klass = classify_git_command(command)
    if klass is None:
        return None
    # Read-only git (status/log/diff/...) is intentionally NOT audited: the
    # trail must stay small enough to read, and the question it answers is
    # "which run CHANGED which repo, how" (Hermes receipt sec.3, SRE item).
    if klass == "read":
        return None

    ctx = current_run()
    record = {
        "ts": time.time(),
        "tool": tool_name,
        "class": klass,
        "repo": _repo_hint(command),
        "trace_id": ctx.get("trace_id", ""),
        "trigger_source": ctx.get("trigger_source", "unknown"),
        "agent_id": ctx.get("agent_id") or agent_id(),
        "session_key": ctx.get("session_key", ""),
        "pid": os.getpid(),
        "command": command[:400],
    }
    try:
        logger.info(
            "[GIT-AUDIT] class=%s repo=%s tool=%s trace_id=%s trigger_source=%s agent_id=%s",
            klass, record["repo"], tool_name, record["trace_id"] or "-",
            record["trigger_source"], record["agent_id"],
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
