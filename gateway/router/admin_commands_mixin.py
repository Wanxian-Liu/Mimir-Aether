"""Gateway router admin commands mixin — extracted from router_mixin (P1-LONG-GOD)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import subprocess
import time
import uuid as _uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from gateway._shared import (
    _check_unavailable_skill,
    _format_gateway_process_notification,
    _load_gateway_config,
    _platform_config_key,
    _resolve_gateway_model,
    _resolve_runtime_agent_kwargs,
    _resolve_hermes_bin,
)
from gateway.home_paths import _hermes_home
from gateway.platforms.base import MessageEvent, MessageType, Platform, merge_pending_message_event
from gateway.restart import _AGENT_PENDING_SENTINEL
from gateway.session import SessionSource, build_session_context, build_session_context_prompt
from utils import atomic_yaml_write

logger = logging.getLogger(__name__)


class AdminCommandsMixin:
    """Router admin commands mixin mixin for GatewayRunner."""

    _APPROVAL_TIMEOUT_SECONDS = 300  # 5 minutes

    _UPDATE_ALLOWED_PLATFORMS = frozenset({
        Platform.TELEGRAM, Platform.DISCORD, Platform.SLACK, Platform.WHATSAPP,
        Platform.SIGNAL, Platform.MATTERMOST, Platform.MATRIX,
        Platform.HOMEASSISTANT, Platform.EMAIL, Platform.SMS, Platform.DINGTALK,
        Platform.FEISHU, Platform.WECOM, Platform.WECOM_CALLBACK, Platform.WEIXIN, Platform.BLUEBUBBLES, Platform.LOCAL,
    })
    async def _handle_approve_command(self, event: MessageEvent) -> Optional[str]:
        """Handle /approve command — unblock waiting agent thread(s).

        The agent thread(s) are blocked inside tools/approval.py waiting for
        the user to respond.  This handler signals the event so the agent
        resumes and the terminal_tool executes the command inline — the same
        flow as the CLI's synchronous input() approval.

        Supports multiple concurrent approvals (parallel subagents,
        execute_code).  ``/approve`` resolves the oldest pending command;
        ``/approve all`` resolves every pending command at once.

        Usage:
            /approve              — approve oldest pending command once
            /approve all          — approve ALL pending commands at once
            /approve session      — approve oldest + remember for session
            /approve all session  — approve all + remember for session
            /approve always       — approve oldest + remember permanently
            /approve all always   — approve all + remember permanently
        """
        source = event.source
        session_key = self._session_key_for_source(source)

        from tools.approval import (
            resolve_gateway_approval, has_blocking_approval,
        )

        if not has_blocking_approval(session_key):
            if session_key in self._pending_approvals:
                self._pending_approvals.pop(session_key)
                return "⚠️ Approval expired (agent is no longer waiting). Ask the agent to try again."
            return "No pending command to approve."

        # Parse args: support "all", "all session", "all always", "session", "always"
        args = event.get_command_args().strip().lower().split()
        resolve_all = "all" in args
        remaining = [a for a in args if a != "all"]

        if any(a in ("always", "permanent", "permanently") for a in remaining):
            choice = "always"
            scope_msg = " (pattern approved permanently)"
        elif any(a in ("session", "ses") for a in remaining):
            choice = "session"
            scope_msg = " (pattern approved for this session)"
        else:
            choice = "once"
            scope_msg = ""

        count = resolve_gateway_approval(session_key, choice, resolve_all=resolve_all)
        if not count:
            return "No pending command to approve."

        # Resume typing indicator — agent is about to continue processing.
        _adapter = self.adapters.get(source.platform)
        if _adapter:
            _adapter.resume_typing_for_chat(source.chat_id)

        count_msg = f" ({count} commands)" if count > 1 else ""
        logger.info("User approved %d dangerous command(s) via /approve%s", count, scope_msg)
        return f"✅ Command{'s' if count > 1 else ''} approved{scope_msg}{count_msg}. The agent is resuming..."

    async def _handle_deny_command(self, event: MessageEvent) -> str:
        """Handle /deny command — reject pending dangerous command(s).

        Signals blocked agent thread(s) with a 'deny' result so they receive
        a definitive BLOCKED message, same as the CLI deny flow.

        ``/deny`` denies the oldest; ``/deny all`` denies everything.
        """
        source = event.source
        session_key = self._session_key_for_source(source)

        from tools.approval import (
            resolve_gateway_approval, has_blocking_approval,
        )

        if not has_blocking_approval(session_key):
            if session_key in self._pending_approvals:
                self._pending_approvals.pop(session_key)
                return "❌ Command denied (approval was stale)."
            return "No pending command to deny."

        args = event.get_command_args().strip().lower()
        resolve_all = "all" in args

        count = resolve_gateway_approval(session_key, "deny", resolve_all=resolve_all)
        if not count:
            return "No pending command to deny."

        # Resume typing indicator — agent continues (with BLOCKED result).
        _adapter = self.adapters.get(source.platform)
        if _adapter:
            _adapter.resume_typing_for_chat(source.chat_id)

        count_msg = f" ({count} commands)" if count > 1 else ""
        logger.info("User denied %d dangerous command(s) via /deny", count)
        return f"❌ Command{'s' if count > 1 else ''} denied{count_msg}."

    # Platforms where /update is allowed.  ACP, API server, and webhooks are
    # programmatic interfaces that should not trigger system updates.

    async def _handle_debug_command(self, event: MessageEvent) -> str:
        """Handle /debug — upload debug report + logs and return paste URLs."""
        import asyncio
        from mimir_cli.debug import (
            _capture_dump, collect_debug_report, _read_full_log,
            upload_to_pastebin,
        )

        loop = asyncio.get_running_loop()

        # Run blocking I/O (dump capture, log reads, uploads) in a thread.
        def _collect_and_upload():
            dump_text = _capture_dump()
            report = collect_debug_report(log_lines=200, dump_text=dump_text)
            agent_log = _read_full_log("agent")
            gateway_log = _read_full_log("gateway")

            if agent_log:
                agent_log = dump_text + "\n\n--- full agent.log ---\n" + agent_log
            if gateway_log:
                gateway_log = dump_text + "\n\n--- full gateway.log ---\n" + gateway_log

            urls = {}
            failures = []

            try:
                urls["Report"] = upload_to_pastebin(report)
            except Exception as exc:
                return f"✗ Failed to upload debug report: {exc}"

            if agent_log:
                try:
                    urls["agent.log"] = upload_to_pastebin(agent_log)
                except Exception:
                    failures.append("agent.log")

            if gateway_log:
                try:
                    urls["gateway.log"] = upload_to_pastebin(gateway_log)
                except Exception:
                    failures.append("gateway.log")

            lines = ["**Debug report uploaded:**", ""]
            label_width = max(len(k) for k in urls)
            for label, url in urls.items():
                lines.append(f"`{label:<{label_width}}`  {url}")

            if failures:
                lines.append(f"\n_(failed to upload: {', '.join(failures)})_")

            lines.append("\nShare these links with the Hermes team for support.")
            return "\n".join(lines)

        return await loop.run_in_executor(None, _collect_and_upload)

    async def _handle_update_command(self, event: MessageEvent) -> str:
        """Handle /update command — update Hermes Agent to the latest version.

        Spawns ``hermes update`` in a detached session (via ``setsid``) so it
        survives the gateway restart that ``hermes update`` may trigger. Marker
        files are written so either the current gateway process or the next one
        can notify the user when the update finishes.
        """
        import json
        import shutil
        import subprocess
        from datetime import datetime
        from mimir_cli.config import is_managed, format_managed_message

        # Block non-messaging platforms (API server, webhooks, ACP)
        platform = event.source.platform
        if platform not in self._UPDATE_ALLOWED_PLATFORMS:
            return "✗ /update is only available from messaging platforms. Run `hermes update` from the terminal."

        if is_managed():
            return f"✗ {format_managed_message('update Hermes Agent')}"

        project_root = Path(__file__).parent.parent.resolve()
        git_dir = project_root / '.git'

        if not git_dir.exists():
            return "✗ Not a git repository — cannot update."

        hermes_cmd = _resolve_hermes_bin()
        if not hermes_cmd:
            return (
                "✗ Could not locate the `hermes` command. "
                "Hermes is running, but the update command could not find the "
                "executable on PATH or via the current Python interpreter. "
                "Try running `hermes update` manually in your terminal."
            )

        pending_path = _hermes_home / ".update_pending.json"
        output_path = _hermes_home / ".update_output.txt"
        exit_code_path = _hermes_home / ".update_exit_code"
        session_key = self._session_key_for_source(event.source)
        pending = {
            "platform": event.source.platform.value,
            "chat_id": event.source.chat_id,
            "user_id": event.source.user_id,
            "session_key": session_key,
            "timestamp": datetime.now().isoformat(),
        }
        _tmp_pending = pending_path.with_suffix(".tmp")
        _tmp_pending.write_text(json.dumps(pending))
        _tmp_pending.replace(pending_path)
        exit_code_path.unlink(missing_ok=True)

        # Spawn `hermes update --gateway` detached so it survives gateway restart.
        # --gateway enables file-based IPC for interactive prompts (stash
        # restore, config migration) so the gateway can forward them to the
        # user instead of silently skipping them.
        # Use setsid for portable session detach (works under system services
        # where systemd-run --user fails due to missing D-Bus session).
        # PYTHONUNBUFFERED ensures output is flushed line-by-line so the
        # gateway can stream it to the messenger in near-real-time.
        hermes_cmd_str = " ".join(shlex.quote(part) for part in hermes_cmd)
        update_cmd = (
            f"PYTHONUNBUFFERED=1 {hermes_cmd_str} update --gateway"
            f" > {shlex.quote(str(output_path))} 2>&1; "
            f"status=$?; printf '%s' \"$status\" > {shlex.quote(str(exit_code_path))}"
        )
        try:
            setsid_bin = shutil.which("setsid")
            if setsid_bin:
                # Preferred: setsid creates a new session, fully detached
                subprocess.Popen(
                    [setsid_bin, "bash", "-c", update_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            else:
                # Fallback: start_new_session=True calls os.setsid() in child
                subprocess.Popen(
                    ["bash", "-c", update_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
        except Exception as e:
            pending_path.unlink(missing_ok=True)
            exit_code_path.unlink(missing_ok=True)
            return f"✗ Failed to start update: {e}"

        self._schedule_update_notification_watch()
        return "⚕ Starting Hermes update… I'll stream progress here."
