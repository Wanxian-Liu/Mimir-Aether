"""P3-XSR-02: L2 cross-session retrieval prefetch into system prompt."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def cross_session_retrieval_enabled() -> bool:
    raw = os.environ.get("MIMIR_CROSS_SESSION_RETRIEVAL", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _prefetch_pending_path() -> Path:
    from mimir_constants import get_mimir_home

    path = Path(get_mimir_home()) / "data" / "ops"
    path.mkdir(parents=True, exist_ok=True)
    return path / "session_prefetch_pending.json"


def request_cross_session_prefetch(session_key: str, *, reason: str = "") -> None:
    """Queue L2 prefetch for the next system prompt build on this session_key."""
    key = (session_key or "").strip()
    if not key:
        return
    payload = {
        "session_key": key,
        "requested_at": time.time(),
        "reason": (reason or "").strip()[:500],
    }
    _prefetch_pending_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def consume_cross_session_prefetch_pending(session_key: str) -> bool:
    """Return True once if prefetch was requested for this session_key."""
    key = (session_key or "").strip()
    if not key:
        return False
    path = _prefetch_pending_path()
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
    if data.get("session_key") != key:
        return False
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return True


def _retrieval_max_chars() -> int:
    raw = os.environ.get("MIMIR_CROSS_SESSION_RETRIEVAL_MAX_CHARS", "2000").strip()
    try:
        return max(200, int(raw))
    except ValueError:
        return 2000


def _session_limit() -> int:
    raw = os.environ.get("MIMIR_CROSS_SESSION_RETRIEVAL_SESSION_LIMIT", "3").strip()
    try:
        return max(1, min(5, int(raw)))
    except ValueError:
        return 3


def _messages_per_session() -> int:
    raw = os.environ.get("MIMIR_CROSS_SESSION_RETRIEVAL_MSG_LIMIT", "3").strip()
    try:
        return max(1, min(10, int(raw)))
    except ValueError:
        return 3


def _session_key_from_env() -> str:
    return (os.environ.get("HERMES_SESSION_KEY") or "").strip()


def _load_persistent_state() -> Dict[str, Any]:
    from mimir_constants import get_mimir_data_dir

    path = get_mimir_data_dir() / "persistent.json"
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def _next_session_snippet(max_len: int = 400) -> str:
    from mimir_constants import get_mimir_home

    path = get_mimir_home() / "NEXT_SESSION.md"
    if not path.is_file() or max_len < 20:
        return ""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not text:
        return ""
    return text[:max_len]


def derive_retrieval_query(state: Optional[Dict[str, Any]] = None) -> str:
    """Objective first, then NEXT_SESSION.md snippet."""
    st = state if state is not None else _load_persistent_state()
    progress = st.get("progress") if isinstance(st.get("progress"), dict) else {}
    objective = progress.get("current_objective") or st.get("current_objective")
    if objective and str(objective).strip():
        return str(objective).strip()[:500]
    snippet = _next_session_snippet()
    return snippet.strip()


def _format_message_line(msg: Dict[str, Any]) -> str:
    role = (msg.get("role") or "unknown").strip()
    content = (msg.get("content") or "").strip().replace("\n", " ")
    tool = (msg.get("tool_name") or "").strip()
    if not content:
        return ""
    prefix = f"{role}"
    if tool:
        prefix += f"({tool})"
    line = f"- {prefix}: {content[:400]}"
    return line


def format_retrieved_sessions(
    results: List[Dict[str, Any]],
    *,
    max_chars: Optional[int] = None,
) -> str:
    cap = max_chars if max_chars is not None else _retrieval_max_chars()
    if not results or cap < 80:
        return ""

    blocks: List[str] = []
    used = 0
    header_budget = 60
    per_block_budget = max(120, (cap - header_budget) // max(1, len(results)))

    for sess in results:
        if used >= cap - header_budget:
            break
        title = (sess.get("title") or "Untitled").strip()
        sid = (sess.get("session_id") or "").strip()
        source = (sess.get("source") or "unknown").strip()
        started = (sess.get("started_at") or "").strip()
        head = f"### {title}"
        if started:
            head += f" · {started}"
        if source:
            head += f" · {source}"
        if sid:
            head += f"\n(session_id: {sid[:48]})"

        lines = [head]
        messages = sess.get("messages")
        if isinstance(messages, list):
            for msg in messages[:_messages_per_session()]:
                if not isinstance(msg, dict):
                    continue
                line = _format_message_line(msg)
                if line:
                    lines.append(line)

        block = "\n".join(lines)
        if len(block) > per_block_budget:
            block = block[: per_block_budget - 20] + "\n…[truncated]"
        if used + len(block) + 2 > cap:
            remaining = cap - used - 25
            if remaining > 80:
                block = block[:remaining] + "\n…[truncated]"
            blocks.append(block)
            break
        blocks.append(block)
        used += len(block) + 2

    if not blocks:
        return ""

    body = "\n\n".join(blocks)
    if len(body) > cap:
        body = body[: cap - 20] + "\n…[truncated]"
    return "<retrieved-sessions>\n" + body + "\n</retrieved-sessions>"


def build_retrieved_sessions_context(
    *,
    session_key: Optional[str] = None,
    search_fn: Any = None,
) -> str:
    """
    L2 prefetch: run session_search once after session reset when queued.

    ``search_fn`` is injectable for tests (defaults to ``session_search``).
    """
    if not cross_session_retrieval_enabled():
        return ""

    key = (session_key or _session_key_from_env()).strip()
    if not key or not consume_cross_session_prefetch_pending(key):
        return ""

    query = derive_retrieval_query()
    if not query:
        return ""

    if search_fn is None:
        from tools.session_search_tool import session_search

        search_fn = session_search

    try:
        results = search_fn(
            query,
            limit=_messages_per_session(),
            session_limit=_session_limit(),
            use_llm=False,
        )
    except Exception as exc:
        logger.debug("L2 cross-session prefetch skipped: %s", exc)
        return ""

    if not isinstance(results, list):
        return ""
    return format_retrieved_sessions(results)
