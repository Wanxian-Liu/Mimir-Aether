"""
CronMixin — cron jobs, background tasks, update notifications.

Extracted from GatewayRunner (gateway/run.py) as part of d3 GOD class split.
"""

from __future__ import annotations
from gateway.restart import _AGENT_PENDING_SENTINEL
from gateway.session import build_session_context, build_session_context_prompt

import asyncio
from datetime import datetime
import json
import logging
import os
import re as _re
import subprocess
import tempfile
import uuid as _uuid
from typing import Dict, Any, Optional, TYPE_CHECKING

from gateway.config import Platform
from gateway.home_paths import _hermes_home, get_hermes_home
from gateway.platforms.base import MessageEvent, MessageType

if TYPE_CHECKING:
    from gateway.run import GatewayRunner

logger = logging.getLogger(__name__)


class CronMixin:
    """Cron job scheduling, background tasks, and update notifications.

    Designed to be mixed into GatewayRunner. All methods assume the
    host class provides: self.config, self._running_agents,
    self.adapters, self._tracked_task(), etc.
    """

    async def _handle_background_command(self, event: MessageEvent) -> str:
        """Handle /background <prompt> — run a prompt in a separate background session.

        Spawns a new AIAgent in a background thread with its own session.
        When it completes, sends the result back to the same chat without
        modifying the active session's conversation history.
        """
        prompt = event.get_command_args().strip()
        if not prompt:
            return (
                "Usage: /background <prompt>\n"
                "Example: /background Summarize the top HN stories today\n\n"
                "Runs the prompt in a separate session. "
                "You can keep chatting — the result will appear here when done."
            )

        source = event.source
        task_id = f"bg_{datetime.now().strftime('%H%M%S')}_{os.urandom(3).hex()}"

        # Fire-and-forget the background task
        _task = asyncio.create_task(
            self._run_background_task(prompt, source, task_id)
        )
        self._background_tasks.add(_task)
        _task.add_done_callback(self._background_tasks.discard)

        preview = prompt[:60] + ("..." if len(prompt) > 60 else "")
        return f'🔄 Background task started: "{preview}"\nTask ID: {task_id}\nYou can keep chatting — results will appear when done.'

    async def _run_background_task(
        self, prompt: str, source: "SessionSource", task_id: str
    ) -> None:
        """Execute a background agent task and deliver the result to the chat."""
        from run_agent import AIAgent

        adapter = self.adapters.get(source.platform)
        if not adapter:
            logger.warning("No adapter for platform %s in background task %s", source.platform, task_id)
            return

        _thread_metadata = {"thread_id": source.thread_id} if source.thread_id else None

        try:
            from gateway.run import _load_gateway_config, _platform_config_key; user_config = _load_gateway_config()
            model, runtime_kwargs = self._resolve_session_agent_runtime(
                source=source,
                user_config=user_config,
            )
            if not runtime_kwargs.get("api_key"):
                await adapter.send(
                    source.chat_id,
                    f"❌ Background task {task_id} failed: no provider credentials configured.",
                    metadata=_thread_metadata,
                )
                return

            platform_key = _platform_config_key(source.platform)

            from mimir_cli.tools_config import _get_platform_tools
            enabled_toolsets = sorted(_get_platform_tools(user_config, platform_key))

            pr = self._provider_routing
            max_iterations = int(os.getenv("HERMES_MAX_ITERATIONS", "90"))
            reasoning_config = self._load_reasoning_config()
            self._reasoning_config = reasoning_config
            self._service_tier = self._load_service_tier()
            turn_route = self._resolve_turn_agent_config(prompt, model, runtime_kwargs)

            def run_sync():
                agent = AIAgent(
                    model=turn_route["model"],
                    **turn_route["runtime"],
                    max_iterations=max_iterations,
                    quiet_mode=True,
                    verbose_logging=False,
                    enabled_toolsets=enabled_toolsets,
                    reasoning_config=reasoning_config,
                    service_tier=self._service_tier,
                    request_overrides=turn_route.get("request_overrides"),
                    providers_allowed=pr.get("only"),
                    providers_ignored=pr.get("ignore"),
                    providers_order=pr.get("order"),
                    provider_sort=pr.get("sort"),
                    provider_require_parameters=pr.get("require_parameters", False),
                    provider_data_collection=pr.get("data_collection"),
                    session_id=task_id,
                    platform=platform_key,
                    user_id=source.user_id,
                    session_db=self._session_db,
                    fallback_model=self._fallback_model,
                )

                return agent.run_conversation(
                    user_message=prompt,
                    task_id=task_id,
                )

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_sync)

            response = result.get("final_response", "") if result else ""
            if not response and result and result.get("error"):
                response = f"Error: {result['error']}"

            # Extract media files from the response
            if response:
                media_files, response = adapter.extract_media(response)
                images, text_content = adapter.extract_images(response)

                preview = prompt[:60] + ("..." if len(prompt) > 60 else "")
                header = f'✅ Background task complete\nPrompt: "{preview}"\n\n'

                if text_content:
                    await adapter.send(
                        chat_id=source.chat_id,
                        content=header + text_content,
                        metadata=_thread_metadata,
                    )
                elif not images and not media_files:
                    await adapter.send(
                        chat_id=source.chat_id,
                        content=header + "(No response generated)",
                        metadata=_thread_metadata,
                    )

                # Send extracted images
                for image_url, alt_text in (images or []):
                    try:
                        await adapter.send_image(
                            chat_id=source.chat_id,
                            image_url=image_url,
                            caption=alt_text,
                        )
                    except Exception:
                        pass

                # Send media files
                for media_path in (media_files or []):
                    try:
                        await adapter.send_document(
                            chat_id=source.chat_id,
                            file_path=media_path,
                        )
                    except Exception:
                        pass
            else:
                preview = prompt[:60] + ("..." if len(prompt) > 60 else "")
                await adapter.send(
                    chat_id=source.chat_id,
                    content=f'✅ Background task complete\nPrompt: "{preview}"\n\n(No response generated)',
                    metadata=_thread_metadata,
                )

        except Exception as e:
            logger.exception("Background task %s failed", task_id)
            try:
                await adapter.send(
                    chat_id=source.chat_id,
                    content=f"❌ Background task {task_id} failed: {e}",
                    metadata=_thread_metadata,
                )
            except Exception:
                pass

    async def _handle_btw_command(self, event: MessageEvent) -> str:
        """Handle /btw <question> — ephemeral side question in the same chat."""
        question = event.get_command_args().strip()
        if not question:
            return (
                "Usage: /btw <question>\n"
                "Example: /btw what module owns session title sanitization?\n\n"
                "Answers using session context. No tools, not persisted."
            )

        source = event.source
        session_key = self._session_key_for_source(source)

        # Guard: one /btw at a time per session
        existing = getattr(self, "_active_btw_tasks", {}).get(session_key)
        if existing and not existing.done():
            return "A /btw is already running for this chat. Wait for it to finish."

        if not hasattr(self, "_active_btw_tasks"):
            self._active_btw_tasks: dict = {}

        import uuid as _uuid
        task_id = f"btw_{datetime.now().strftime('%H%M%S')}_{_uuid.uuid4().hex[:6]}"
        _task = asyncio.create_task(self._run_btw_task(question, source, session_key, task_id))
        self._background_tasks.add(_task)
        self._active_btw_tasks[session_key] = _task

        def _cleanup(task):
            self._background_tasks.discard(task)
            if self._active_btw_tasks.get(session_key) is task:
                self._active_btw_tasks.pop(session_key, None)

        _task.add_done_callback(_cleanup)

        preview = question[:60] + ("..." if len(question) > 60 else "")
        return f'💬 /btw: "{preview}"\nReply will appear here shortly.'

    async def _run_btw_task(
        self, question: str, source, session_key: str, task_id: str,
    ) -> None:
        """Execute an ephemeral /btw side question and deliver the answer."""
        from run_agent import AIAgent

        adapter = self.adapters.get(source.platform)
        if not adapter:
            logger.warning("No adapter for platform %s in /btw task %s", source.platform, task_id)
            return

        _thread_meta = {"thread_id": source.thread_id} if source.thread_id else None

        try:
            from gateway.run import _load_gateway_config, _platform_config_key; user_config = _load_gateway_config()
            model, runtime_kwargs = self._resolve_session_agent_runtime(
                source=source,
                session_key=session_key,
                user_config=user_config,
            )
            if not runtime_kwargs.get("api_key"):
                await adapter.send(
                    source.chat_id,
                    "❌ /btw failed: no provider credentials configured.",
                    metadata=_thread_meta,
                )
                return

            platform_key = _platform_config_key(source.platform)
            reasoning_config = self._load_reasoning_config()
            self._service_tier = self._load_service_tier()
            turn_route = self._resolve_turn_agent_config(question, model, runtime_kwargs)
            pr = self._provider_routing

            # Snapshot history from running agent or stored transcript
            running_agent = self._running_agents.get(session_key)
            if running_agent and running_agent is not _AGENT_PENDING_SENTINEL:
                history_snapshot = list(getattr(running_agent, "_session_messages", []) or [])
            else:
                session_entry = self.session_store.get_or_create_session(source)
                history_snapshot = self.session_store.load_transcript(session_entry.session_id)

            btw_prompt = (
                "[Ephemeral /btw side question. Answer using the conversation "
                "context. No tools available. Be direct and concise.]\n\n"
                + question
            )

            def run_sync():
                agent = AIAgent(
                    model=turn_route["model"],
                    **turn_route["runtime"],
                    max_iterations=8,
                    quiet_mode=True,
                    verbose_logging=False,
                    enabled_toolsets=[],
                    reasoning_config=reasoning_config,
                    service_tier=self._service_tier,
                    request_overrides=turn_route.get("request_overrides"),
                    providers_allowed=pr.get("only"),
                    providers_ignored=pr.get("ignore"),
                    providers_order=pr.get("order"),
                    provider_sort=pr.get("sort"),
                    provider_require_parameters=pr.get("require_parameters", False),
                    provider_data_collection=pr.get("data_collection"),
                    session_id=task_id,
                    platform=platform_key,
                    session_db=None,
                    fallback_model=self._fallback_model,
                    skip_memory=True,
                    skip_context_files=True,
                    persist_session=False,
                )
                return agent.run_conversation(
                    user_message=btw_prompt,
                    conversation_history=history_snapshot,
                    task_id=task_id,
                )

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_sync)

            response = (result.get("final_response") or "") if result else ""
            if not response and result and result.get("error"):
                response = f"Error: {result['error']}"
            if not response:
                response = "(No response generated)"

            media_files, response = adapter.extract_media(response)
            images, text_content = adapter.extract_images(response)
            preview = question[:60] + ("..." if len(question) > 60 else "")
            header = f'💬 /btw: "{preview}"\n\n'

            if text_content:
                await adapter.send(
                    chat_id=source.chat_id,
                    content=header + text_content,
                    metadata=_thread_meta,
                )
            elif not images and not media_files:
                await adapter.send(
                    chat_id=source.chat_id,
                    content=header + "(No response generated)",
                    metadata=_thread_meta,
                )

            for image_url, alt_text in (images or []):
                try:
                    await adapter.send_image(chat_id=source.chat_id, image_url=image_url, caption=alt_text)
                except Exception:
                    pass

            for media_path in (media_files or []):
                try:
                    await adapter.send_file(chat_id=source.chat_id, file_path=media_path)
                except Exception:
                    pass

        except Exception as e:
            logger.exception("/btw task %s failed", task_id)
            try:
                await adapter.send(
                    chat_id=source.chat_id,
                    content=f"❌ /btw failed: {e}",
                    metadata=_thread_meta,
                )
            except Exception:
                pass

    def _schedule_update_notification_watch(self) -> None:
        """Ensure a background task is watching for update completion."""
        existing_task = getattr(self, "_update_notification_task", None)
        if existing_task and not existing_task.done():
            return

        try:
            self._update_notification_task = asyncio.create_task(
                self._watch_update_progress()
            )
        except RuntimeError:
            logger.debug("Skipping update notification watcher: no running event loop")

    async def _watch_update_progress(
        self,
        poll_interval: float = 2.0,
        stream_interval: float = 4.0,
        timeout: float = 1800.0,
    ) -> None:
        """Watch ``hermes update --gateway``, streaming output + forwarding prompts.

        Polls ``.update_output.txt`` for new content and sends chunks to the
        user periodically.  Detects ``.update_prompt.json`` (written by the
        update process when it needs user input) and forwards the prompt to
        the messenger.  The user's next message is intercepted by
        ``_handle_message`` and written to ``.update_response``.
        """
        import json
        import re as _re

        pending_path = _hermes_home / ".update_pending.json"
        claimed_path = _hermes_home / ".update_pending.claimed.json"
        output_path = _hermes_home / ".update_output.txt"
        exit_code_path = _hermes_home / ".update_exit_code"
        prompt_path = _hermes_home / ".update_prompt.json"

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        # Resolve the adapter and chat_id for sending messages
        adapter = None
        chat_id = None
        session_key = None
        for path in (claimed_path, pending_path):
            if path.exists():
                try:
                    pending = json.loads(path.read_text())
                    platform_str = pending.get("platform")
                    chat_id = pending.get("chat_id")
                    session_key = pending.get("session_key")
                    if platform_str and chat_id:
                        platform = Platform(platform_str)
                        adapter = self.adapters.get(platform)
                        # Fallback session key if not stored (old pending files)
                        if not session_key:
                            session_key = f"{platform_str}:{chat_id}"
                    break
                except Exception:
                    pass

        if not adapter or not chat_id:
            logger.warning("Update watcher: cannot resolve adapter/chat_id, falling back to completion-only")
            # Fall back to old behavior: wait for exit code and send final notification
            while (pending_path.exists() or claimed_path.exists()) and loop.time() < deadline:
                if exit_code_path.exists():
                    await self._send_update_notification()
                    return
                await asyncio.sleep(poll_interval)
            if (pending_path.exists() or claimed_path.exists()) and not exit_code_path.exists():
                exit_code_path.write_text("124")
                await self._send_update_notification()
            return

        def _strip_ansi(text: str) -> str:
            return _re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)

        bytes_sent = 0
        last_stream_time = loop.time()
        buffer = ""

        async def _flush_buffer() -> None:
            """Send buffered output to the user."""
            nonlocal buffer, last_stream_time
            if not buffer.strip():
                buffer = ""
                return
            # Chunk to fit message limits (Telegram: 4096, others: generous)
            clean = _strip_ansi(buffer).strip()
            buffer = ""
            last_stream_time = loop.time()
            if not clean:
                return
            # Split into chunks if too long
            max_chunk = 3500
            chunks = [clean[i:i + max_chunk] for i in range(0, len(clean), max_chunk)]
            for chunk in chunks:
                try:
                    await adapter.send(chat_id, f"```\n{chunk}\n```")
                except Exception as e:
                    logger.debug("Update stream send failed: %s", e)

        while loop.time() < deadline:
            # Check for completion
            if exit_code_path.exists():
                # Read any remaining output
                if output_path.exists():
                    try:
                        content = output_path.read_text()
                        if len(content) > bytes_sent:
                            buffer += content[bytes_sent:]
                            bytes_sent = len(content)
                    except OSError:
                        pass
                await _flush_buffer()

                # Send final status
                try:
                    exit_code_raw = exit_code_path.read_text().strip() or "1"
                    exit_code = int(exit_code_raw)
                    if exit_code == 0:
                        await adapter.send(chat_id, "✅ Hermes update finished.")
                    else:
                        await adapter.send(chat_id, "❌ Hermes update failed (exit code {}).".format(exit_code))
                    logger.info("Update finished (exit=%s), notified %s", exit_code, session_key)
                except Exception as e:
                    logger.warning("Update final notification failed: %s", e)

                # Cleanup
                for p in (pending_path, claimed_path, output_path,
                          exit_code_path, prompt_path):
                    p.unlink(missing_ok=True)
                (_hermes_home / ".update_response").unlink(missing_ok=True)
                self._update_prompt_pending.pop(session_key, None)
                return

            # Check for new output
            if output_path.exists():
                try:
                    content = output_path.read_text()
                    if len(content) > bytes_sent:
                        buffer += content[bytes_sent:]
                        bytes_sent = len(content)
                except OSError:
                    pass

            # Flush buffer periodically
            if buffer.strip() and (loop.time() - last_stream_time) >= stream_interval:
                await _flush_buffer()

            # Check for prompts — only forward if we haven't already sent
            # one that's still awaiting a response.  Without this guard the
            # watcher would re-read the same .update_prompt.json every poll
            # cycle and spam the user with duplicate prompt messages.
            if (prompt_path.exists() and session_key
                    and not self._update_prompt_pending.get(session_key)):
                try:
                    prompt_data = json.loads(prompt_path.read_text())
                    prompt_text = prompt_data.get("prompt", "")
                    default = prompt_data.get("default", "")
                    if prompt_text:
                        # Flush any buffered output first so the user sees
                        # context before the prompt
                        await _flush_buffer()
                        # Try platform-native buttons first (Discord, Telegram)
                        sent_buttons = False
                        if getattr(type(adapter), "send_update_prompt", None) is not None:
                            try:
                                await adapter.send_update_prompt(
                                    chat_id=chat_id,
                                    prompt=prompt_text,
                                    default=default,
                                    session_key=session_key,
                                )
                                sent_buttons = True
                            except Exception as btn_err:
                                logger.debug("Button-based update prompt failed: %s", btn_err)
                        if not sent_buttons:
                            default_hint = f" (default: {default})" if default else ""
                            await adapter.send(
                                chat_id,
                                f"⚕ **Update needs your input:**\n\n"
                                f"{prompt_text}{default_hint}\n\n"
                                f"Reply `/approve` (yes) or `/deny` (no), "
                                f"or type your answer directly."
                            )
                        self._update_prompt_pending[session_key] = True
                        # Remove the prompt file so it isn't re-read on the
                        # next poll cycle.  The update process only needs
                        # .update_response to continue — it doesn't re-check
                        # .update_prompt.json while waiting.
                        prompt_path.unlink(missing_ok=True)
                        logger.info("Forwarded update prompt to %s: %s", session_key, prompt_text[:80])
                except (json.JSONDecodeError, OSError) as e:
                    logger.debug("Failed to read update prompt: %s", e)

            await asyncio.sleep(poll_interval)

        # Timeout
        if not exit_code_path.exists():
            logger.warning("Update watcher timed out after %.0fs", timeout)
            exit_code_path.write_text("124")
            await _flush_buffer()
            try:
                await adapter.send(chat_id, "❌ Hermes update timed out after 30 minutes.")
            except Exception:
                pass
            for p in (pending_path, claimed_path, output_path,
                      exit_code_path, prompt_path):
                p.unlink(missing_ok=True)
            (_hermes_home / ".update_response").unlink(missing_ok=True)
            self._update_prompt_pending.pop(session_key, None)

    async def _send_update_notification(self) -> bool:
        """If an update finished, notify the user.

        Returns False when the update is still running so a caller can retry
        later. Returns True after a definitive send/skip decision.

        This is the legacy notification path used when the streaming watcher
        cannot resolve the adapter (e.g. after a gateway restart where the
        platform hasn't reconnected yet).
        """
        import json
        import re as _re

        pending_path = _hermes_home / ".update_pending.json"
        claimed_path = _hermes_home / ".update_pending.claimed.json"
        output_path = _hermes_home / ".update_output.txt"
        exit_code_path = _hermes_home / ".update_exit_code"

        if not pending_path.exists() and not claimed_path.exists():
            return False

        cleanup = True
        active_pending_path = claimed_path
        try:
            if pending_path.exists():
                try:
                    pending_path.replace(claimed_path)
                except FileNotFoundError:
                    if not claimed_path.exists():
                        return True
            elif not claimed_path.exists():
                return True

            pending = json.loads(claimed_path.read_text())
            platform_str = pending.get("platform")
            chat_id = pending.get("chat_id")

            if not exit_code_path.exists():
                logger.info("Update notification deferred: update still running")
                cleanup = False
                active_pending_path = pending_path
                claimed_path.replace(pending_path)
                return False

            exit_code_raw = exit_code_path.read_text().strip() or "1"
            exit_code = int(exit_code_raw)

            # Read the captured update output
            output = ""
            if output_path.exists():
                output = output_path.read_text()

            # Resolve adapter
            platform = Platform(platform_str)
            adapter = self.adapters.get(platform)

            if adapter and chat_id:
                # Strip ANSI escape codes for clean display
                output = _re.sub(r'\x1b\[[0-9;]*m', '', output).strip()
                if output:
                    if len(output) > 3500:
                        output = "…" + output[-3500:]
                    if exit_code == 0:
                        msg = f"✅ Hermes update finished.\n\n```\n{output}\n```"
                    else:
                        msg = f"❌ Hermes update failed.\n\n```\n{output}\n```"
                else:
                    if exit_code == 0:
                        msg = "✅ Hermes update finished successfully."
                    else:
                        msg = "❌ Hermes update failed. Check the gateway logs or run `hermes update` manually for details."
                await adapter.send(chat_id, msg)
                logger.info(
                    "Sent post-update notification to %s:%s (exit=%s)",
                    platform_str,
                    chat_id,
                    exit_code,
                )
        except Exception as e:
            logger.warning("Post-update notification failed: %s", e)
        finally:
            if cleanup:
                active_pending_path.unlink(missing_ok=True)
                claimed_path.unlink(missing_ok=True)
                output_path.unlink(missing_ok=True)
                exit_code_path.unlink(missing_ok=True)

        return True

    async def _send_restart_notification(self) -> None:
        """Notify the chat that initiated /restart that the gateway is back."""
        import json as _json

        notify_path = _hermes_home / ".restart_notify.json"
        if not notify_path.exists():
            return

        try:
            data = _json.loads(notify_path.read_text())
            platform_str = data.get("platform")
            chat_id = data.get("chat_id")
            thread_id = data.get("thread_id")

            if not platform_str or not chat_id:
                return

            platform = Platform(platform_str)
            adapter = self.adapters.get(platform)
            if not adapter:
                logger.debug(
                    "Restart notification skipped: %s adapter not connected",
                    platform_str,
                )
                return

            metadata = {"thread_id": thread_id} if thread_id else None
            await adapter.send(
                chat_id,
                "♻ Gateway restarted successfully. Your session continues.",
                metadata=metadata,
            )
            logger.info(
                "Sent restart notification to %s:%s",
                platform_str,
                chat_id,
            )
        except Exception as e:
            logger.warning("Restart notification failed: %s", e)
        finally:
            notify_path.unlink(missing_ok=True)

    async def execute_cron_job(self, job: Dict[str, Any]) -> None:
        """Run one due cron job: optional script, else agent prompt; then deliver."""
        import subprocess
        from agent.prompt_builder import PLATFORM_HINTS
        from agent.skill_commands import _build_skill_message, _load_skill_payload
        from cron.jobs import mark_job_run
        from gateway.config import Platform
        from gateway.delivery import DeliveryTarget
        from gateway.session import (
            SessionSource,
            build_session_context,
            build_session_context_prompt,
        )
        from gateway.session_context import clear_session_vars, set_session_vars

        job_id = str(job.get("id") or "")
        job_name = str(job.get("name") or job_id)
        if not job_id:
            return

        logger.info("Cron: executing job %s (%s)", job_id, job_name)

        script_rel = (job.get("script") or "").strip()
        deliver_raw = job.get("deliver", "local")
        if isinstance(deliver_raw, list):
            deliver_targets = deliver_raw
        else:
            deliver_targets = [deliver_raw]

        origin = None
        if job.get("origin"):
            try:
                origin = SessionSource.from_dict(job["origin"])
            except Exception as exc:
                logger.debug("Cron job %s: invalid origin, ignoring: %s", job_id, exc)

        source = SessionSource(
            platform=Platform.LOCAL,
            chat_id=f"cron:{job_id}",
            chat_type="dm",
            user_id="cron",
            user_name="cron",
        )
        session_entry = self.session_store.get_or_create_session(source)
        session_key = session_entry.session_key
        session_id = session_entry.session_id

        tokens = set_session_vars(
            platform=source.platform.value,
            chat_id=source.chat_id,
            user_name=source.user_name or "",
            user_id=source.user_id or "",
            session_key=session_key,
        )
        final_text = ""
        try:
            context = build_session_context(source, self.config, session_entry)
            context_prompt = build_session_context_prompt(context, redact_pii=False)
            cron_hint = PLATFORM_HINTS.get("cron")
            if cron_hint:
                context_prompt = f"{context_prompt}\n\n{cron_hint}"

            message_body = job.get("prompt") or ""
            skills = job.get("skills") or ([] if not job.get("skill") else [job["skill"]])
            if skills:
                try:
                    parts: List[str] = []
                    for sname in skills:
                        loaded = _load_skill_payload(sname, task_id=session_key)
                        if loaded:
                            _ls, _sdir, _dname = loaded
                            note = f'[SYSTEM: The "{_dname}" skill is loaded for this cron job.]'
                            part = _build_skill_message(_ls, _sdir, note)
                            if part:
                                parts.append(part)
                    if parts:
                        message_body = "\n\n".join(parts + ([message_body] if message_body.strip() else []))
                except Exception as exc:
                    logger.warning("Cron job %s: skill load failed: %s", job_id, exc)

            if script_rel:
                scripts_dir = Path(get_hermes_home()) / "scripts"
                scripts_dir.mkdir(parents=True, exist_ok=True)
                script_path = (scripts_dir / script_rel).resolve()
                if not str(script_path).startswith(str(scripts_dir.resolve())):
                    mark_job_run(job_id, "error", "invalid script path")
                    return
                if not script_path.is_file():
                    mark_job_run(job_id, "error", f"script not found: {script_rel}")
                    return
                try:
                    proc = subprocess.run(
                        ["/bin/bash", str(script_path)],
                        capture_output=True,
                        text=True,
                        timeout=600,
                        cwd=str(get_hermes_home()),
                    )
                    final_text = proc.stdout or ""
                    if proc.stderr:
                        final_text = f"{final_text}\n--- stderr ---\n{proc.stderr}"
                    if proc.returncode != 0:
                        mark_job_run(
                            job_id,
                            "error",
                            f"script exit {proc.returncode}",
                        )
                    else:
                        mark_job_run(job_id, "ok", None)
                except subprocess.TimeoutExpired:
                    mark_job_run(job_id, "error", "script timeout (600s)")
                    final_text = "(timeout)"
                except Exception as exc:
                    logger.exception("Cron job %s: script failed", job_id)
                    mark_job_run(job_id, "error", str(exc))
                    final_text = str(exc)
            else:
                if not str(message_body).strip():
                    mark_job_run(job_id, "error", "empty prompt and no script")
                    return
                history = self.session_store.load_transcript(session_id)
                try:
                    result = await self._run_agent(
                        message=message_body,
                        context_prompt=context_prompt,
                        history=history,
                        source=source,
                        session_id=session_id,
                        session_key=session_key,
                        event_message_id=None,
                    )
                    final_text = result.get("final_response") or ""
                    if result.get("error"):
                        mark_job_run(job_id, "error", str(result.get("error")))
                    else:
                        mark_job_run(job_id, "ok", None)
                except Exception as exc:
                    logger.exception("Cron job %s: agent failed", job_id)
                    mark_job_run(job_id, "error", str(exc))
                    final_text = f"cron error: {exc}"

            if not str(final_text).strip():
                return
            if "[SILENT]" in final_text:
                return

            targets: List[DeliveryTarget] = []
            for d in deliver_targets:
                t = str(d).strip()
                if not t:
                    continue
                try:
                    targets.append(DeliveryTarget.parse(t, origin=origin))
                except Exception as exc:
                    logger.warning("Cron job %s: bad deliver target %r: %s", job_id, t, exc)

            if not targets:
                targets = [DeliveryTarget.parse("local", origin=origin)]

            metadata = {"job_id": job_id, "job_name": job_name}
            self.delivery_router.adapters = self.adapters
            try:
                await self.delivery_router.deliver(
                    final_text,
                    targets,
                    job_id=job_id,
                    job_name=job_name,
                    metadata=metadata,
                )
            except Exception as exc:
                logger.warning("Cron job %s: delivery failed: %s", job_id, exc)
        finally:
            clear_session_vars(tokens)


def _start_cron_ticker(
    stop_event: threading.Event,
    adapters=None,
    loop=None,
    runner=None,
    interval: int = 60,
):
    """
    Background thread that ticks the cron scheduler at a regular interval.
    
    Runs inside the gateway process so cronjobs fire automatically without
    needing a separate `hermes cron daemon` or system cron entry.

    When ``adapters`` and ``loop`` are provided, passes them through to the
    cron delivery path so live adapters can be used for E2EE rooms.

    Also refreshes the channel directory every 5 minutes and prunes the
    image/audio/document cache once per hour.
    """
    from cron.scheduler import tick as cron_tick
    from gateway.platforms.base import cleanup_image_cache, cleanup_document_cache

    IMAGE_CACHE_EVERY = 60   # ticks — once per hour at default 60s interval
    CHANNEL_DIR_EVERY = 5    # ticks — every 5 minutes

    logger.info("Cron ticker started (interval=%ds)", interval)
    tick_count = 0
    while not stop_event.is_set():
        try:
            cron_tick(verbose=False, adapters=adapters, loop=loop, runner=runner)
        except Exception:
            logger.error("Cron tick error", exc_info=True)

        tick_count += 1

        if tick_count % CHANNEL_DIR_EVERY == 0 and adapters:
            try:
                from gateway.channel_directory import build_channel_directory
                build_channel_directory(adapters)
            except Exception as e:
                logger.debug("Channel directory refresh error: %s", e)

        if tick_count % IMAGE_CACHE_EVERY == 0:
            try:
                removed = cleanup_image_cache(max_age_hours=24)
                if removed:
                    logger.info("Image cache cleanup: removed %d stale file(s)", removed)
            except Exception as e:
                logger.debug("Image cache cleanup error: %s", e)
            try:
                removed = cleanup_document_cache(max_age_hours=24)
                if removed:
                    logger.info("Document cache cleanup: removed %d stale file(s)", removed)
            except Exception as e:
                logger.debug("Document cache cleanup error: %s", e)

        # D3-P0-4: Use 1s sub-waits instead of a single <interval>-second
        # wait so the stop signal is noticed within 1 second rather than
        # being blocked for up to the full tick interval.
        for _ in range(interval):
            if stop_event.is_set():
                break
            stop_event.wait(timeout=1)
    logger.info("Cron ticker stopped")


async def start_gateway(config: Optional[GatewayConfig] = None, replace: bool = False, verbosity: Optional[int] = 0) -> bool:
    """
    Start the gateway and run until interrupted.
    
    This is the main entry point for running the gateway.
    Returns True if the gateway ran successfully, False if it failed to start.
    A False return causes a non-zero exit code so systemd can auto-restart.
    
    Args:
        config: Optional gateway configuration override.
        replace: If True, kill any existing gateway instance before starting.
                 Useful for systemd services to avoid restart-loop deadlocks
                 when the previous process hasn't fully exited yet.
    """
    # ── Duplicate-instance guard ──────────────────────────────────────
    # Prevent two gateways from running under the same HERMES_HOME.
    # The PID file is scoped to HERMES_HOME, so future multi-profile
    # setups (each profile using a distinct HERMES_HOME) will naturally
    # allow concurrent instances without tripping this guard.
    import time as _time
    from gateway.status import get_running_pid, remove_pid_file, terminate_pid
    existing_pid = get_running_pid()
    if existing_pid is not None and existing_pid != os.getpid():
        if replace:
            logger.info(
                "Replacing existing gateway instance (PID %d) with --replace.",
                existing_pid,
            )
            try:
                terminate_pid(existing_pid, force=False)
            except ProcessLookupError:
                pass  # Already gone
            except (PermissionError, OSError):
                logger.error(
                    "Permission denied killing PID %d. Cannot replace.",
                    existing_pid,
                )
                return False
            # Wait up to 10 seconds for the old process to exit
            for _ in range(20):
                try:
                    os.kill(existing_pid, 0)
                    _time.sleep(0.5)
                except (ProcessLookupError, PermissionError):
                    break  # Process is gone
            else:
                # Still alive after 10s — force kill
                logger.warning(
                    "Old gateway (PID %d) did not exit after SIGTERM, sending SIGKILL.",
                    existing_pid,
                )
                try:
                    terminate_pid(existing_pid, force=True)
                    _time.sleep(0.5)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
            remove_pid_file()
            # Also release all scoped locks left by the old process.
            # Stopped (Ctrl+Z) processes don't release locks on exit,
            # leaving stale lock files that block the new gateway from starting.
            try:
                from gateway.status import release_all_scoped_locks
                _released = release_all_scoped_locks()
                if _released:
                    logger.info("Released %d stale scoped lock(s) from old gateway.", _released)
            except Exception:
                pass
        else:
            hermes_home = str(get_hermes_home())
            logger.error(
                "Another gateway instance is already running (PID %d, HERMES_HOME=%s). "
                "Use 'hermes gateway restart' to replace it, or 'hermes gateway stop' first.",
                existing_pid, hermes_home,
            )
            print(
                f"\n❌ Gateway already running (PID {existing_pid}).\n"
                f"   Use 'hermes gateway restart' to replace it,\n"
                f"   or 'hermes gateway stop' to kill it first.\n"
                f"   Or use 'hermes gateway run --replace' to auto-replace.\n"
            )
            return False

    # Sync bundled skills on gateway start (fast -- skips unchanged)
    try:
        from tools.skills_sync import sync_skills
        sync_skills(quiet=True)
    except Exception:
        pass

    # Centralized logging — agent.log (INFO+), errors.log (WARNING+),
    # and gateway.log (INFO+, gateway-component records only).
    # Idempotent, so repeated calls from AIAgent.__init__ won't duplicate.
    from mimiraether_logging import setup_logging
    setup_logging(hermes_home=_hermes_home, mode="gateway")

    # Optional stderr handler — level driven by -v/-q flags on the CLI.
    # verbosity=None (-q/--quiet): no stderr output
    # verbosity=0    (default):    WARNING and above
    # verbosity=1    (-v):         INFO and above
    # verbosity=2+   (-vv/-vvv):   DEBUG
    if verbosity is not None:
        from agent.redact import RedactingFormatter

        _stderr_level = {0: logging.WARNING, 1: logging.INFO}.get(verbosity, logging.DEBUG)
        _stderr_handler = logging.StreamHandler()
        _stderr_handler.setLevel(_stderr_level)
        _stderr_handler.setFormatter(RedactingFormatter('%(levelname)s %(name)s: %(message)s'))
        logging.getLogger().addHandler(_stderr_handler)
        # Lower root logger level if needed so DEBUG records can reach the handler
        if _stderr_level < logging.getLogger().level:
            logging.getLogger().setLevel(_stderr_level)

    runner = GatewayRunner(config)
    
