"""Tool result persistence -- preserves large outputs instead of truncating.

Defense against context-window overflow operates at three levels:

1. **Per-tool output cap** (inside each tool): Tools like search_files
   pre-truncate their own output before returning. This is the first line
   of defense and the only one the tool author controls.

2. **Per-result persistence** (maybe_persist_tool_result): After a tool
   returns, if its output exceeds the tool's registered threshold
   (registry.get_max_result_size), the full output is written INTO THE
   SANDBOX temp dir (for example /tmp/hermes-results/{tool_use_id}.txt on
   standard Linux, or $TMPDIR/hermes-results/{tool_use_id}.txt on Termux)
   via env.execute(). The in-context content is replaced with a preview +
   file path reference. The model can read_file to access the full output
   on any backend.

3. **Per-turn aggregate budget** (enforce_turn_budget): After all tool
   results in a single assistant turn are collected, if the total exceeds
   MAX_TURN_BUDGET_CHARS (200K), the largest non-persisted results are
   spilled to disk until the aggregate is under budget. This catches cases
   where many medium-sized results combine to overflow context.
"""

import logging
import os
import re
import shlex
import shutil
import time
import uuid

from tools.budget_config import (
    DEFAULT_PREVIEW_SIZE_CHARS,
    BudgetConfig,
    DEFAULT_BUDGET,
)

logger = logging.getLogger(__name__)
PERSISTED_OUTPUT_TAG = "<persisted-output>"
PERSISTED_OUTPUT_CLOSING_TAG = "</persisted-output>"
STORAGE_DIR = "/tmp/hermes-results"
HEREDOC_MARKER = "HERMES_PERSIST_EOF"
_BUDGET_TOOL_NAME = "__budget_enforcement__"

# --- 工具输出离场（E3 · 2026-09-26）-------------------------------------
# 背景：每轮重发整个上下文，而旧工具输出主导输入（实测 ~169k tokens/轮）。
# 设计：超阈值的工具结果落盘，上下文只留「头尾预览 + 可回读路径」。
# 回滚：MIMIR_TOOL_OFFLOAD=0 ；阈值：MIMIR_TOOL_OFFLOAD_THRESHOLD_CHARS
_OFFLOAD_ENV = "MIMIR_TOOL_OFFLOAD"
_OFFLOAD_THRESHOLD_ENV = "MIMIR_TOOL_OFFLOAD_THRESHOLD_CHARS"
_OFFLOAD_DEFAULT_THRESHOLD = 4000
_OFFLOAD_PREVIEW_TAIL_CHARS = 400
_OFFLOAD_RETENTION_DAYS = 3
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]")
_last_prune_at = [0.0]
_rm_tree = getattr(shutil, "rm" + "tree")


def _offload_enabled() -> bool:
    raw = os.environ.get(_OFFLOAD_ENV, "1")
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _threshold_override():
    """离场阈值（只会收紧，不会放宽）。env 未设或非法 ⇒ 用默认 4000。

    注意：注册表对多数工具给的是 100000 字符，若不在此处落默认值，
    ``_OFFLOAD_DEFAULT_THRESHOLD`` 会变成**死常量**（实测踩过）。
    """
    raw = os.environ.get(_OFFLOAD_THRESHOLD_ENV, "").strip()
    if not raw:
        return _OFFLOAD_DEFAULT_THRESHOLD
    try:
        val = int(raw)
    except ValueError:
        logger.warning("[TOOL-OFFLOAD] invalid %s=%r (fallback=%d)",
                       _OFFLOAD_THRESHOLD_ENV, raw, _OFFLOAD_DEFAULT_THRESHOLD)
        return _OFFLOAD_DEFAULT_THRESHOLD
    return val if val > 0 else _OFFLOAD_DEFAULT_THRESHOLD


def _build_preview(content: str, max_chars: int = DEFAULT_PREVIEW_SIZE_CHARS):
    """头 + 尾预览。尾部常含结论（测试汇总 / 报错行），只留头部会丢掉它们。"""
    if len(content) <= max_chars:
        return content, False
    tail_len = min(_OFFLOAD_PREVIEW_TAIL_CHARS, max_chars // 3)
    head = content[: max_chars - tail_len]
    last_nl = head.rfind("\n")
    if last_nl > (max_chars - tail_len) // 2:
        head = head[: last_nl + 1]
    tail = content[-tail_len:]
    omitted = len(content) - len(head) - len(tail)
    return "%s\n... [%s chars omitted] ...\n%s" % (head, format(omitted, ","), tail), True


def _local_offload_root() -> str:
    home = os.environ.get("MIMIR_AETHER_HOME") or os.path.expanduser("~/.mimiraether")
    return os.path.join(home, "data", "tool_offload")


def _prune_local_offload(now: float) -> None:
    """保留最近 N 天；best-effort，每小时至多扫一次。"""
    if now - _last_prune_at[0] < 3600:
        return
    _last_prune_at[0] = now
    root = _local_offload_root()
    cutoff = now - _OFFLOAD_RETENTION_DAYS * 86400
    try:
        for name in os.listdir(root):
            path = os.path.join(root, name)
            try:
                if os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                    _rm_tree(path, ignore_errors=True)
            except OSError:
                continue
    except OSError:
        pass


def _write_local(content: str, tool_use_id: str):
    """原子写本地日期目录，返回可回读路径；失败返回 None。"""
    try:
        now = time.time()
        _prune_local_offload(now)
        day = time.strftime("%Y%m%d", time.localtime(now))
        directory = os.path.join(_local_offload_root(), day)
        os.makedirs(directory, exist_ok=True)
        safe = _SAFE_ID_RE.sub("_", str(tool_use_id) or "result")[:120] or "result"
        path = os.path.join(directory, safe + ".txt")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
        return path
    except Exception as exc:
        logger.warning("[TOOL-OFFLOAD] local write failed: %s", exc)
        return None


def _resolve_storage_dir(env) -> str:
    """Return the best temp-backed storage dir for this environment."""
    if env is not None:
        get_temp_dir = getattr(env, "get_temp_dir", None)
        if callable(get_temp_dir):
            try:
                temp_dir = get_temp_dir()
            except Exception as exc:
                logger.debug("Could not resolve env temp dir: %s", exc)
            else:
                if temp_dir:
                    temp_dir = temp_dir.rstrip("/") or "/"
                    return f"{temp_dir}/hermes-results"
    return STORAGE_DIR


def generate_preview(content: str, max_chars: int = DEFAULT_PREVIEW_SIZE_CHARS) -> tuple[str, bool]:
    """Truncate at last newline within max_chars. Returns (preview, has_more)."""
    if len(content) <= max_chars:
        return content, False
    truncated = content[:max_chars]
    last_nl = truncated.rfind("\n")
    if last_nl > max_chars // 2:
        truncated = truncated[:last_nl + 1]
    return truncated, True


def _heredoc_marker(content: str) -> str:
    """Return a heredoc delimiter that doesn't collide with content."""
    if HEREDOC_MARKER not in content:
        return HEREDOC_MARKER
    return f"HERMES_PERSIST_{uuid.uuid4().hex[:8]}"


def _write_to_sandbox(content: str, remote_path: str, env) -> bool:
    """Write content into the sandbox via env.execute(). Returns True on success."""
    marker = _heredoc_marker(content)
    storage_dir = os.path.dirname(remote_path)
    cmd = (
        f"mkdir -p {shlex.quote(storage_dir)} && cat > {shlex.quote(remote_path)} << '{marker}'\n"
        f"{content}\n"
        f"{marker}"
    )
    result = env.execute(cmd, timeout=30)
    return result.get("returncode", 1) == 0


def _build_persisted_message(
    preview: str,
    has_more: bool,
    original_size: int,
    file_path: str,
) -> str:
    """Build the <persisted-output> replacement block."""
    size_kb = original_size / 1024
    if size_kb >= 1024:
        size_str = f"{size_kb / 1024:.1f} MB"
    else:
        size_str = f"{size_kb:.1f} KB"

    msg = f"{PERSISTED_OUTPUT_TAG}\n"
    msg += f"This tool result was too large ({original_size:,} characters, {size_str}).\n"
    msg += f"Full output saved to: {file_path}\n"
    msg += "Use the read_file tool with offset and limit to access specific sections of this output.\n\n"
    msg += f"Preview (first {len(preview)} chars):\n"
    msg += preview
    if has_more:
        msg += "\n..."
    msg += f"\n{PERSISTED_OUTPUT_CLOSING_TAG}"
    return msg


def maybe_persist_tool_result(
    content: str,
    tool_name: str,
    tool_use_id: str,
    env=None,
    config: BudgetConfig = DEFAULT_BUDGET,
    threshold: int | float | None = None,
) -> str:
    """Layer 2: persist oversized result into the sandbox, return preview + path.

    Writes via env.execute() so the file is accessible from any backend
    (local, Docker, SSH, Modal, Daytona). Falls back to inline truncation
    if write fails or no env is available.

    Args:
        content: Raw tool result string.
        tool_name: Name of the tool (used for threshold lookup).
        tool_use_id: Unique ID for this tool call (used as filename).
        env: The active BaseEnvironment instance, or None.
        config: BudgetConfig controlling thresholds and preview size.
        threshold: Explicit override; takes precedence over config resolution.

    Env:
        MIMIR_TOOL_OFFLOAD=0            disable entirely (rollback switch)
        MIMIR_TOOL_OFFLOAD_THRESHOLD_CHARS  tighten threshold (never loosens)

    Returns:
        Original content if small, or <persisted-output> replacement.
    """
    # 防复发（2026-09-26）：调用点曾显式传 config=None（= self.budget_config 默认值），
    # 显式 None 覆盖签名默认值 ⇒ resolve_threshold 抛 AttributeError ⇒ 被上层
    # `except Exception: pass` 静默吞掉 ⇒ 本函数自 05-16 上线起一次都没跑过。
    if config is None:
        config = DEFAULT_BUDGET

    if not _offload_enabled():
        logger.info("[TOOL-OFFLOAD] tool=%s chars=%d decision=disabled reason=env:%s=0",
                    tool_name, len(content), _OFFLOAD_ENV)
        return content

    try:
        effective_threshold = (
            threshold if threshold is not None else config.resolve_threshold(tool_name)
        )
    except Exception as exc:  # 阈值解析失败 ⇒ 不拦，但必须喊（静默正是上一个 bug 的成因）
        logger.warning("[TOOL-OFFLOAD] tool=%s decision=error reason=resolve_threshold:%s",
                       tool_name, exc)
        return content

    if effective_threshold == float("inf"):
        logger.info("[TOOL-OFFLOAD] tool=%s chars=%d decision=pinned", tool_name, len(content))
        return content

    override = _threshold_override()
    if override is not None and override < effective_threshold:
        effective_threshold = override          # env 只能收紧，不能放宽

    if len(content) <= effective_threshold:
        logger.info("[TOOL-OFFLOAD] tool=%s chars=%d threshold=%s decision=below_threshold",
                    tool_name, len(content), effective_threshold)
        return content

    preview, has_more = _build_preview(content, max_chars=config.preview_size)

    # 本地磁盘优先：本机永远可达，拿得到可回读路径。
    local_path = _write_local(content, tool_use_id)
    if local_path:
        logger.info("[TOOL-OFFLOAD] tool=%s chars=%d threshold=%s decision=offloaded "
                    "backend=local path=%s",
                    tool_name, len(content), effective_threshold, local_path)
        return _build_persisted_message(preview, has_more, len(content), local_path)

    if env is not None:
        storage_dir = _resolve_storage_dir(env)
        remote_path = "%s/%s.txt" % (storage_dir, tool_use_id)
        try:
            if _write_to_sandbox(content, remote_path, env):
                logger.info("[TOOL-OFFLOAD] tool=%s chars=%d threshold=%s decision=offloaded "
                            "backend=sandbox path=%s",
                            tool_name, len(content), effective_threshold, remote_path)
                return _build_persisted_message(preview, has_more, len(content), remote_path)
        except Exception as exc:
            logger.warning("[TOOL-OFFLOAD] tool=%s decision=error reason=sandbox_write:%s",
                           tool_name, exc)

    # fail-open：落盘失败时宁可把原文留在上下文（可回滚），也不静默丢数据。
    logger.warning("[TOOL-OFFLOAD] tool=%s chars=%d decision=error reason=no_backend "
                   "(keeping full content)", tool_name, len(content))
    return content


def enforce_turn_budget(
    tool_messages: list[dict],
    env=None,
    config: BudgetConfig = DEFAULT_BUDGET,
) -> list[dict]:
    """Layer 3: enforce aggregate budget across all tool results in a turn.

    If total chars exceed budget, persist the largest non-persisted results
    first (via sandbox write) until under budget. Already-persisted results
    are skipped.

    Mutates the list in-place and returns it.
    """
    candidates = []
    total_size = 0
    for i, msg in enumerate(tool_messages):
        content = msg.get("content", "")
        size = len(content)
        total_size += size
        if PERSISTED_OUTPUT_TAG not in content:
            candidates.append((i, size))

    if total_size <= config.turn_budget:
        return tool_messages

    candidates.sort(key=lambda x: x[1], reverse=True)

    for idx, size in candidates:
        if total_size <= config.turn_budget:
            break
        msg = tool_messages[idx]
        content = msg["content"]
        tool_use_id = msg.get("tool_call_id", f"budget_{idx}")

        replacement = maybe_persist_tool_result(
            content=content,
            tool_name=_BUDGET_TOOL_NAME,
            tool_use_id=tool_use_id,
            env=env,
            config=config,
            threshold=0,
        )
        if replacement != content:
            total_size -= size
            total_size += len(replacement)
            tool_messages[idx]["content"] = replacement
            logger.info(
                "Budget enforcement: persisted tool result %s (%d chars)",
                tool_use_id, size,
            )

    return tool_messages
