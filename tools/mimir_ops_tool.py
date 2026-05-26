"""Allowlisted Mimir ops for agent self-check (P1-LONG-AUTONOMY · AUTO-01/02/04)."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from mimir_constants import get_mimir_home

# Allowlisted scripts only (no arbitrary shell).
_ALLOWLIST: Dict[str, List[str]] = {
    "health_check": ["scripts/mimir_health_check.sh"],
    "evolution_eval": ["scripts/run_evolution_eval.sh"],
    "gateway_restart": ["scripts/restart_gateway_hard.sh"],
}


def _repo_root() -> Path:
    env = os.environ.get("MIMIR_REPO_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).resolve()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return Path(__file__).resolve().parents[1]


def _ops_data_dir() -> Path:
    path = Path(get_mimir_home()) / "data" / "ops"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _session_reset_pending_path() -> Path:
    return _ops_data_dir() / "session_reset_pending.json"


def request_session_reset(session_key: str, *, reason: str = "") -> None:
    """Queue session reset for gateway to apply before next agent run."""
    payload = {
        "session_key": session_key,
        "requested_at": time.time(),
        "reason": (reason or "").strip()[:500],
    }
    _session_reset_pending_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def consume_session_reset_pending(session_key: str) -> bool:
    """Return True once if a reset was requested for this session_key."""
    path = _session_reset_pending_path()
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    if not isinstance(data, dict):
        path.unlink(missing_ok=True)
        return False
    if data.get("session_key") != session_key:
        return False
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return True


def apply_session_reset_on_runner(runner: Any, session_key: str) -> Dict[str, Any]:
    """Evict cached agent and rotate session_id (gateway runner context)."""
    if not session_key:
        return {"ok": False, "error": "missing session_key"}

    evict = getattr(runner, "_evict_cached_agent", None)
    if callable(evict):
        try:
            evict(session_key)
        except Exception:
            pass

    store = getattr(runner, "session_store", None)
    if store is None:
        return {"ok": False, "error": "session_store unavailable"}

    overrides = getattr(runner, "_session_model_overrides", None)
    if isinstance(overrides, dict):
        overrides.pop(session_key, None)

    entry = store.reset_session(session_key)
    if entry is None:
        return {"ok": False, "error": f"unknown session_key: {session_key}"}
    return {
        "ok": True,
        "session_key": session_key,
        "session_id": entry.session_id,
        "message": "Session reset applied. Next turn uses a fresh session_id.",
    }


def _run_allowlisted_script(
    action: str,
    extra_args: Optional[List[str]] = None,
    *,
    timeout_sec: int = 600,
) -> Dict[str, Any]:
    rel_paths = _ALLOWLIST.get(action)
    if not rel_paths:
        return {"ok": False, "error": f"unknown action: {action}"}

    root = _repo_root()
    script = root / rel_paths[0]
    if not script.is_file():
        return {"ok": False, "error": f"script missing: {script}"}

    env = os.environ.copy()
    home = str(get_mimir_home())
    env.setdefault("MIMIR_AETHER_HOME", home)
    env.setdefault("HERMES_HOME", env.get("HERMES_HOME") or home)
    env.setdefault("MIMIR_REPO_ROOT", str(root))

    cmd = ["bash", str(script)] + (extra_args or [])
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout after {timeout_sec}s", "action": action}

    stdout = (proc.stdout or "")[-12000:]
    stderr = (proc.stderr or "")[-4000:]
    return {
        "ok": proc.returncode == 0,
        "action": action,
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def _action_health_check(*, quick: bool = True) -> Dict[str, Any]:
    args = ["--json"]
    if quick:
        args.append("--quick")
    return _run_allowlisted_script("health_check", args, timeout_sec=120)


def _action_evolution_eval() -> Dict[str, Any]:
    return _run_allowlisted_script("evolution_eval", [], timeout_sec=600)


def _action_gateway_restart(*, confirm: bool = False) -> Dict[str, Any]:
    if not confirm:
        return {
            "ok": False,
            "error": "gateway_restart requires confirm=true",
            "hint": "Set MIMIR_OPS_ALLOW_GATEWAY_RESTART=1 and pass confirm=true",
        }
    if os.environ.get("MIMIR_OPS_ALLOW_GATEWAY_RESTART", "").strip() not in (
        "1",
        "true",
        "yes",
    ):
        return {
            "ok": False,
            "error": "MIMIR_OPS_ALLOW_GATEWAY_RESTART not set",
            "hint": "Human must enable restart in $MIMIR_AETHER_HOME/.env before agent may restart gateway",
        }
    return _run_allowlisted_script("gateway_restart", [], timeout_sec=90)


def _action_context_usage() -> Dict[str, Any]:
    from agent.context_usage_snapshot import read_context_usage_snapshot
    from agent.monitor import snapshot_for_health

    snap = read_context_usage_snapshot() or {}
    monitor = snapshot_for_health()
    ctx_len = int(snap.get("context_length") or 0)
    prompt = int(snap.get("prompt_tokens") or 0)
    remaining = max(ctx_len - prompt, 0) if ctx_len > 0 else None
    return {
        "ok": True,
        "context_usage": snap,
        "remaining_tokens_estimate": remaining,
        "monitor": monitor,
        "note": (
            "Values reflect the last completed model call in this gateway process. "
            "Users may also send /new or /reset in Feishu to start a fresh session."
        ),
    }


def _action_session_search_baseline(*, days: int = 7) -> Dict[str, Any]:
    from tools.session_search_usage_baseline import write_baseline_json

    return write_baseline_json(days=max(1, int(days)))


def _action_session_reset(*, session_key: str = "") -> Dict[str, Any]:
    from tools.approval import get_current_session_key

    key = (session_key or get_current_session_key("")).strip()
    if not key or key == "default":
        return {
            "ok": False,
            "error": "no active session_key (not in gateway?)",
            "hint": "Ask the user to send /new or /reset in Feishu",
        }
    request_session_reset(key, reason="mimir_ops session_reset")
    return {
        "ok": True,
        "session_key": key,
        "pending": True,
        "message": (
            "Session reset queued for the next agent turn. "
            "For immediate reset, user can send /new or /reset in chat."
        ),
    }


def mimir_ops(
    action: str,
    *,
    quick: bool = True,
    confirm: bool = False,
    session_key: str = "",
    days: int = 7,
) -> str:
    """Dispatch allowlisted ops actions; returns JSON string."""
    action = (action or "").strip().lower()
    result: Dict[str, Any]
    if action == "health_check":
        result = _action_health_check(quick=quick)
    elif action == "evolution_eval":
        result = _action_evolution_eval()
    elif action == "gateway_restart":
        result = _action_gateway_restart(confirm=confirm)
    elif action == "context_usage":
        result = _action_context_usage()
    elif action == "session_search_baseline":
        result = _action_session_search_baseline(days=int(days or 7))
    elif action == "session_reset":
        result = _action_session_reset(session_key=session_key)
    else:
        result = {
            "ok": False,
            "error": f"unknown action: {action}",
            "allowed": sorted(_ALLOWLIST.keys())
            + ["context_usage", "session_reset", "session_search_baseline"],
        }
    return json.dumps(result, ensure_ascii=False, indent=2)


MIMIR_OPS_SCHEMA = {
    "name": "mimir_ops",
    "description": (
        "Allowlisted Mimir operations: health_check, evolution_eval, "
        "gateway_restart (needs confirm + env), context_usage, session_reset. "
        "Does not run arbitrary shell."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "health_check",
                    "evolution_eval",
                    "gateway_restart",
                    "context_usage",
                    "session_reset",
                    "session_search_baseline",
                ],
                "description": "Operation to run.",
            },
            "quick": {
                "type": "boolean",
                "description": "For health_check: use --quick (R1-R5 only).",
                "default": True,
            },
            "confirm": {
                "type": "boolean",
                "description": "Required true for gateway_restart.",
                "default": False,
            },
            "session_key": {
                "type": "string",
                "description": "Optional override for session_reset (default: current session).",
            },
            "days": {
                "type": "integer",
                "description": "For session_search_baseline: lookback days (default 7).",
                "default": 7,
            },
        },
        "required": ["action"],
    },
}

from tools.registry import registry

registry.register(
    name="mimir_ops",
    toolset="ops",
    schema=MIMIR_OPS_SCHEMA,
    handler=lambda args, **kw: mimir_ops(
        action=args.get("action", ""),
        quick=bool(args.get("quick", True)),
        confirm=bool(args.get("confirm", False)),
        session_key=args.get("session_key", ""),
        days=int(args.get("days", 7) or 7),
    ),
    emoji="🛠️",
    max_result_size_chars=50_000,
)
