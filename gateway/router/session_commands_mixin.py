"""Gateway router session commands mixin — extracted from router_mixin (P1-LONG-GOD)."""
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


class SessionCommandsMixin:
    """Router session commands mixin mixin for GatewayRunner."""

    async def _handle_reset_command(self, event: MessageEvent) -> str:
        """Handle /new or /reset command."""
        source = event.source
        
        # Get existing session key
        session_key = self._session_key_for_source(source)
        old_entry = self.session_store._entries.get(session_key)

        # Grain A: await memory flush before reset so /new does not drop unsaved turns.
        if old_entry:
            await self._await_flush_memories_for_manual_reset(
                old_entry.session_id,
                session_key,
            )
        # Close tool resources on the old agent (terminal sandboxes, browser
        # daemons, background processes) before evicting from cache.
        # Guard with getattr because test fixtures may skip __init__.
        _cache_lock = getattr(self, "_agent_cache_lock", None)
        if _cache_lock is not None:
            with _cache_lock:
                _cached = self._agent_cache.get(session_key)
                _old_agent = _cached[0] if isinstance(_cached, tuple) else _cached if _cached else None
            if _old_agent is not None:
                try:
                    if hasattr(_old_agent, "close"):
                        _old_agent.close()
                except Exception:
                    pass
        self._evict_cached_agent(session_key)

        try:
            from tools.env_passthrough import clear_env_passthrough
            clear_env_passthrough()
        except Exception:
            pass

        try:
            from tools.credential_files import clear_credential_files
            clear_credential_files()
        except Exception:
            pass

        # Reset the session
        new_entry = self.session_store.reset_session(session_key)

        try:
            from agent.cross_session_retrieval import request_cross_session_prefetch

            request_cross_session_prefetch(session_key, reason="/new")
        except Exception:
            pass

        # Clear any session-scoped model override so the next agent picks up
        # the configured default instead of the previously switched model.
        self._session_model_overrides.pop(session_key, None)

        # Fire plugin on_session_finalize hook (session boundary)
        try:
            from mimir_cli.plugins import invoke_hook as _invoke_hook
            _old_sid = old_entry.session_id if old_entry else None
            _invoke_hook("on_session_finalize", session_id=_old_sid,
                         platform=source.platform.value if source.platform else "")
        except Exception:
            pass

        # Emit session:end hook (session is ending)
        await self.hooks.emit("session:end", {
            "platform": source.platform.value if source.platform else "",
            "user_id": source.user_id,
            "session_key": session_key,
        })

        # Emit session:reset hook
        await self.hooks.emit("session:reset", {
            "platform": source.platform.value if source.platform else "",
            "user_id": source.user_id,
            "session_key": session_key,
        })

        # Resolve session config info to surface to the user
        try:
            session_info = self._format_session_info()
        except Exception:
            session_info = ""

        if new_entry:
            header = "✨ Session reset! Starting fresh."
        else:
            # No existing session, just create one
            new_entry = self.session_store.get_or_create_session(source, force_new=True)
            header = "✨ New session started!"

        # Fire plugin on_session_reset hook (new session guaranteed to exist)
        try:
            from mimir_cli.plugins import invoke_hook as _invoke_hook
            _new_sid = new_entry.session_id if new_entry else None
            _invoke_hook("on_session_reset", session_id=_new_sid,
                         platform=source.platform.value if source.platform else "")
        except Exception:
            pass

        # Append a random tip to the reset message
        try:
            from mimir_cli.tips import get_random_tip
            _tip_line = f"\n✦ Tip: {get_random_tip()}"
        except Exception:
            _tip_line = ""

        if session_info:
            return f"{header}\n\n{session_info}{_tip_line}"
        return f"{header}{_tip_line}"

    async def _handle_profile_command(self, event: MessageEvent) -> str:
        """Handle /profile — show active profile name and home directory."""
        import os
        from pathlib import Path

        from mimir_constants import (
            display_hermes_home,
            get_default_hermes_root,
            get_hermes_home,
        )

        display = display_hermes_home()
        home = get_hermes_home().resolve()

        # Detect profile name from HERMES_HOME path (e.g. <openclaw_root>/profiles/<name>)
        profiles_parent = get_default_hermes_root() / "profiles"
        try:
            rel = home.relative_to(profiles_parent)
            profile_name = str(rel).split("/")[0]
        except ValueError:
            profile_name = None

        if profile_name:
            lines = [
                f"👤 **Profile:** `{profile_name}`",
                f"📂 **Home:** `{display}`",
            ]
        else:
            lines = [
                "👤 **Profile:** default",
                f"📂 **Home:** `{display}`",
            ]

        return "\n".join(lines)

    async def _handle_status_command(self, event: MessageEvent) -> str:
        """Handle /status command."""
        source = event.source
        session_entry = self.session_store.get_or_create_session(source)

        connected_platforms = [p.value for p in self.adapters.keys()]

        # Check if there's an active agent
        session_key = session_entry.session_key
        is_running = session_key in self._running_agents

        title = None
        if self._session_db:
            try:
                title = self._session_db.get_session_title(session_entry.session_id)
            except Exception:
                title = None

        lines = [
            "📊 **Hermes Gateway Status**",
            "",
            f"**Session ID:** `{session_entry.session_id}`",
        ]
        if title:
            lines.append(f"**Title:** {title}")
        lines.extend([
            f"**Created:** {session_entry.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"**Last Activity:** {session_entry.updated_at.strftime('%Y-%m-%d %H:%M')}",
            f"**Tokens:** {session_entry.total_tokens:,}",
            f"**Agent Running:** {'Yes ⚡' if is_running else 'No'}",
            "",
            f"**Connected Platforms:** {', '.join(connected_platforms)}",
        ])

        return "\n".join(lines)

    async def _handle_stop_command(self, event: MessageEvent) -> str:
        """Handle /stop command - interrupt a running agent.

        When an agent is truly hung (blocked thread that never checks
        _interrupt_requested), the early intercept in _handle_message()
        handles /stop before this method is reached.  This handler fires
        only through normal command dispatch (no running agent) or as a
        fallback.  Force-clean the session lock in all cases for safety.

        The session is preserved so the user can continue the conversation.
        """
        source = event.source
        session_entry = self.session_store.get_or_create_session(source)
        session_key = session_entry.session_key

        agent = self._running_agents.get(session_key)
        if agent is _AGENT_PENDING_SENTINEL:
            # Force-clean the sentinel so the session is unlocked.
            if session_key in self._running_agents:
                del self._running_agents[session_key]
            logger.info("STOP (pending) for session %s — sentinel cleared", session_key[:20])
            return "⚡ Stopped. The agent hadn't started yet — you can continue this session."
        if agent:
            agent.interrupt("Stop requested")
            # Force-clean the session lock so a truly hung agent doesn't
            # keep it locked forever.
            if session_key in self._running_agents:
                del self._running_agents[session_key]
            return "⚡ Stopped. You can continue this session."
        else:
            return "No active task to stop."

    async def _handle_restart_command(self, event: MessageEvent) -> str:
        """Handle /restart command - drain active work, then restart the gateway."""
        if self._restart_requested or self._draining:
            count = self._running_agent_count()
            if count:
                return f"⏳ Draining {count} active agent(s) before restart..."
            return "⏳ Gateway restart already in progress..."

        # Save the requester's routing info so the new gateway process can
        # notify them once it comes back online.
        try:
            import json as _json
            notify_data = {
                "platform": event.source.platform.value if event.source.platform else None,
                "chat_id": event.source.chat_id,
            }
            if event.source.thread_id:
                notify_data["thread_id"] = event.source.thread_id
            (_hermes_home / ".restart_notify.json").write_text(
                _json.dumps(notify_data)
            )
        except Exception as e:
            logger.debug("Failed to write restart notify file: %s", e)

        active_agents = self._running_agent_count()
        # When running under a service manager (systemd/launchd), use the
        # service restart path: exit with code 75 so the service manager
        # restarts us.  The detached subprocess approach (setsid + bash)
        # doesn't work under systemd because KillMode=mixed kills all
        # processes in the cgroup, including the detached helper.
        _under_service = bool(os.environ.get("INVOCATION_ID"))  # systemd sets this
        if _under_service:
            self.request_restart(detached=False, via_service=True)
        else:
            self.request_restart(detached=True, via_service=False)
        if active_agents:
            return f"⏳ Draining {active_agents} active agent(s) before restart..."
        return "♻ Restarting gateway. If you aren't notified within 60 seconds, restart from the console with `hermes gateway restart`."

    async def _handle_help_command(self, event: MessageEvent) -> str:
        """Handle /help command - list available commands."""
        from mimir_cli.commands import gateway_help_lines
        lines = [
            "📖 **Hermes Commands**\n",
            *gateway_help_lines(),
        ]
        try:
            from agent.skill_commands import get_skill_commands
            skill_cmds = get_skill_commands()
            if skill_cmds:
                lines.append(f"\n⚡ **Skill Commands** ({len(skill_cmds)} active):")
                # Show first 10, then point to /commands for the rest
                sorted_cmds = sorted(skill_cmds)
                for cmd in sorted_cmds[:10]:
                    lines.append(f"`{cmd}` — {skill_cmds[cmd]['description']}")
                if len(sorted_cmds) > 10:
                    lines.append(f"\n... and {len(sorted_cmds) - 10} more. Use `/commands` for the full paginated list.")
        except Exception:
            pass
        return "\n".join(lines)

    async def _handle_commands_command(self, event: MessageEvent) -> str:
        """Handle /commands [page] - paginated list of all commands and skills."""
        from mimir_cli.commands import gateway_help_lines

        raw_args = event.get_command_args().strip()
        if raw_args:
            try:
                requested_page = int(raw_args)
            except ValueError:
                return "Usage: `/commands [page]`"
        else:
            requested_page = 1

        # Build combined entry list: built-in commands + skill commands
        entries = list(gateway_help_lines())
        try:
            from agent.skill_commands import get_skill_commands
            skill_cmds = get_skill_commands()
            if skill_cmds:
                entries.append("")
                entries.append("⚡ **Skill Commands**:")
                for cmd in sorted(skill_cmds):
                    desc = skill_cmds[cmd].get("description", "").strip() or "Skill command"
                    entries.append(f"`{cmd}` — {desc}")
        except Exception:
            pass

        if not entries:
            return "No commands available."

        from gateway.config import Platform
        page_size = 15 if event.source.platform == Platform.TELEGRAM else 20
        total_pages = max(1, (len(entries) + page_size - 1) // page_size)
        page = max(1, min(requested_page, total_pages))
        start = (page - 1) * page_size
        page_entries = entries[start:start + page_size]

        lines = [
            f"📚 **Commands** ({len(entries)} total, page {page}/{total_pages})",
            "",
            *page_entries,
        ]
        if total_pages > 1:
            nav_parts = []
            if page > 1:
                nav_parts.append(f"`/commands {page - 1}` ← prev")
            if page < total_pages:
                nav_parts.append(f"next → `/commands {page + 1}`")
            lines.extend(["", " | ".join(nav_parts)])
        if page != requested_page:
            lines.append(f"_(Requested page {requested_page} was out of range, showing page {page}.)_")
        return "\n".join(lines)
