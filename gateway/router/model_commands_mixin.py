"""Gateway router model commands mixin — extracted from router_mixin (P1-LONG-GOD)."""
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


class ModelCommandsMixin:
    """Router model commands mixin mixin for GatewayRunner."""

    async def _handle_model_command(self, event: MessageEvent) -> Optional[str]:
        """Handle /model command — switch model for this session.

        Supports:
          /model                              — interactive picker (Telegram/Discord) or text list
          /model <name>                       — switch for this session only
          /model <name> --global              — switch and persist to config.yaml
          /model <name> --provider <provider> — switch provider + model
          /model --provider <provider>        — switch to provider, auto-detect model
        """
        import yaml
        from mimir_cli.model_switch import (
            switch_model as _switch_model, parse_model_flags,
            list_authenticated_providers,
        )
        from mimir_cli.providers import get_label

        raw_args = event.get_command_args().strip()

        # Parse --provider and --global flags
        model_input, explicit_provider, persist_global = parse_model_flags(raw_args)

        # Read current model/provider from config
        current_model = ""
        current_provider = "openrouter"
        current_base_url = ""
        current_api_key = ""
        user_provs = None
        custom_provs = None
        config_path = _hermes_home / "config.yaml"
        try:
            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                model_cfg = cfg.get("model", {})
                if isinstance(model_cfg, dict):
                    current_model = model_cfg.get("default", "")
                    current_provider = model_cfg.get("provider", current_provider)
                    current_base_url = model_cfg.get("base_url", "")
                user_provs = cfg.get("providers")
                try:
                    from mimir_cli.config import get_compatible_custom_providers
                    custom_provs = get_compatible_custom_providers(cfg)
                except Exception:
                    custom_provs = cfg.get("custom_providers")
        except Exception:
            pass

        # Check for session override
        source = event.source
        session_key = self._session_key_for_source(source)
        override = self._session_model_overrides.get(session_key, {})
        if override:
            current_model = override.get("model", current_model)
            current_provider = override.get("provider", current_provider)
            current_base_url = override.get("base_url", current_base_url)
            current_api_key = override.get("api_key", current_api_key)

        # No args: show interactive picker (Telegram/Discord) or text list
        if not model_input and not explicit_provider:
            # Try interactive picker if the platform supports it
            adapter = self.adapters.get(source.platform)
            has_picker = (
                adapter is not None
                and getattr(type(adapter), "send_model_picker", None) is not None
            )

            if has_picker:
                try:
                    providers = list_authenticated_providers(
                        current_provider=current_provider,
                        user_providers=user_provs,
                        custom_providers=custom_provs,
                        max_models=50,
                    )
                except Exception:
                    providers = []

                if providers:
                    # Build a callback closure for when the user picks a model.
                    # Captures self + locals needed for the switch logic.
                    _self = self
                    _session_key = session_key
                    _cur_model = current_model
                    _cur_provider = current_provider
                    _cur_base_url = current_base_url
                    _cur_api_key = current_api_key

                    async def _on_model_selected(
                        _chat_id: str, model_id: str, provider_slug: str
                    ) -> str:
                        """Perform the model switch and return confirmation text."""
                        result = _switch_model(
                            raw_input=model_id,
                            current_provider=_cur_provider,
                            current_model=_cur_model,
                            current_base_url=_cur_base_url,
                            current_api_key=_cur_api_key,
                            is_global=False,
                            explicit_provider=provider_slug,
                            user_providers=user_provs,
                            custom_providers=custom_provs,
                        )
                        if not result.success:
                            return f"Error: {result.error_message}"

                        # Update cached agent in-place
                        cached_entry = None
                        _cache_lock = getattr(_self, "_agent_cache_lock", None)
                        _cache = getattr(_self, "_agent_cache", None)
                        if _cache_lock and _cache is not None:
                            with _cache_lock:
                                cached_entry = _cache.get(_session_key)
                        if cached_entry and cached_entry[0] is not None:
                            try:
                                cached_entry[0].switch_model(
                                    new_model=result.new_model,
                                    new_provider=result.target_provider,
                                    api_key=result.api_key,
                                    base_url=result.base_url,
                                    api_mode=result.api_mode,
                                )
                            except Exception as exc:
                                logger.warning("Picker model switch failed for cached agent: %s", exc)

                        # Store model note + session override
                        if not hasattr(_self, "_pending_model_notes"):
                            _self._pending_model_notes = {}
                        _self._pending_model_notes[_session_key] = (
                            f"[Note: model was just switched from {_cur_model} to {result.new_model} "
                            f"via {result.provider_label or result.target_provider}. "
                            f"Adjust your self-identification accordingly.]"
                        )
                        _self._session_model_overrides[_session_key] = {
                            "model": result.new_model,
                            "provider": result.target_provider,
                            "api_key": result.api_key,
                            "base_url": result.base_url,
                            "api_mode": result.api_mode,
                        }

                        # Evict cached agent so the next turn creates a fresh
                        # agent from the override rather than relying on the
                        # stale cache signature to trigger a rebuild.
                        _self._evict_cached_agent(_session_key)

                        # Build confirmation text
                        plabel = result.provider_label or result.target_provider
                        lines = [f"Model switched to `{result.new_model}`"]
                        lines.append(f"Provider: {plabel}")
                        mi = result.model_info
                        if mi:
                            if mi.context_window:
                                lines.append(f"Context: {mi.context_window:,} tokens")
                            if mi.max_output:
                                lines.append(f"Max output: {mi.max_output:,} tokens")
                            if mi.has_cost_data():
                                lines.append(f"Cost: {mi.format_cost()}")
                            lines.append(f"Capabilities: {mi.format_capabilities()}")
                        lines.append("_(session only — use `/model <name> --global` to persist)_")
                        return "\n".join(lines)

                    metadata = {"thread_id": source.thread_id} if source.thread_id else None
                    result = await adapter.send_model_picker(
                        chat_id=source.chat_id,
                        providers=providers,
                        current_model=current_model,
                        current_provider=current_provider,
                        session_key=session_key,
                        on_model_selected=_on_model_selected,
                        metadata=metadata,
                    )
                    if result.success:
                        return None  # Picker sent — adapter handles the response

            # Fallback: text list (for platforms without picker or if picker failed)
            provider_label = get_label(current_provider)
            lines = [f"Current: `{current_model or 'unknown'}` on {provider_label}", ""]

            try:
                providers = list_authenticated_providers(
                    current_provider=current_provider,
                    user_providers=user_provs,
                    custom_providers=custom_provs,
                    max_models=5,
                )
                for p in providers:
                    tag = " (current)" if p["is_current"] else ""
                    lines.append(f"**{p['name']}** `--provider {p['slug']}`{tag}:")
                    if p["models"]:
                        model_strs = ", ".join(f"`{m}`" for m in p["models"])
                        extra = f" (+{p['total_models'] - len(p['models'])} more)" if p["total_models"] > len(p["models"]) else ""
                        lines.append(f"  {model_strs}{extra}")
                    elif p.get("api_url"):
                        lines.append(f"  `{p['api_url']}`")
                    lines.append("")
            except Exception:
                pass

            lines.append("`/model <name>` — switch model")
            lines.append("`/model <name> --provider <slug>` — switch provider")
            lines.append("`/model <name> --global` — persist")
            return "\n".join(lines)

        # Perform the switch
        result = _switch_model(
            raw_input=model_input,
            current_provider=current_provider,
            current_model=current_model,
            current_base_url=current_base_url,
            current_api_key=current_api_key,
            is_global=persist_global,
            explicit_provider=explicit_provider,
            user_providers=user_provs,
            custom_providers=custom_provs,
        )

        if not result.success:
            return f"Error: {result.error_message}"

        # If there's a cached agent, update it in-place
        cached_entry = None
        _cache_lock = getattr(self, "_agent_cache_lock", None)
        _cache = getattr(self, "_agent_cache", None)
        if _cache_lock and _cache is not None:
            with _cache_lock:
                cached_entry = _cache.get(session_key)

        if cached_entry and cached_entry[0] is not None:
            try:
                cached_entry[0].switch_model(
                    new_model=result.new_model,
                    new_provider=result.target_provider,
                    api_key=result.api_key,
                    base_url=result.base_url,
                    api_mode=result.api_mode,
                )
            except Exception as exc:
                logger.warning("In-place model switch failed for cached agent: %s", exc)

        # Store a note to prepend to the next user message so the model
        # knows about the switch (avoids system messages mid-history).
        if not hasattr(self, "_pending_model_notes"):
            self._pending_model_notes = {}
        self._pending_model_notes[session_key] = (
            f"[Note: model was just switched from {current_model} to {result.new_model} "
            f"via {result.provider_label or result.target_provider}. "
            f"Adjust your self-identification accordingly.]"
        )

        # Store session override so next agent creation uses the new model
        self._session_model_overrides[session_key] = {
            "model": result.new_model,
            "provider": result.target_provider,
            "api_key": result.api_key,
            "base_url": result.base_url,
            "api_mode": result.api_mode,
        }

        # Evict cached agent so the next turn creates a fresh agent from the
        # override rather than relying on cache signature mismatch detection.
        self._evict_cached_agent(session_key)

        # Persist to config if --global
        if persist_global:
            try:
                if config_path.exists():
                    with open(config_path, encoding="utf-8") as f:
                        cfg = yaml.safe_load(f) or {}
                else:
                    cfg = {}
                model_cfg = cfg.setdefault("model", {})
                model_cfg["default"] = result.new_model
                model_cfg["provider"] = result.target_provider
                if result.base_url:
                    model_cfg["base_url"] = result.base_url
                from mimir_cli.config import save_config
                save_config(cfg)
            except Exception as e:
                logger.warning("Failed to persist model switch: %s", e)

        # Build confirmation message with full metadata
        provider_label = result.provider_label or result.target_provider
        lines = [f"Model switched to `{result.new_model}`"]
        lines.append(f"Provider: {provider_label}")

        # Rich metadata from models.dev
        mi = result.model_info
        if mi:
            if mi.context_window:
                lines.append(f"Context: {mi.context_window:,} tokens")
            if mi.max_output:
                lines.append(f"Max output: {mi.max_output:,} tokens")
            if mi.has_cost_data():
                lines.append(f"Cost: {mi.format_cost()}")
            lines.append(f"Capabilities: {mi.format_capabilities()}")
        else:
            try:
                from agent.model_metadata import get_model_context_length
                ctx = get_model_context_length(
                    result.new_model,
                    base_url=result.base_url or current_base_url,
                    api_key=result.api_key or current_api_key,
                    provider=result.target_provider,
                )
                lines.append(f"Context: {ctx:,} tokens")
            except Exception:
                pass

        # Cache notice
        cache_enabled = (
            ("openrouter" in (result.base_url or "").lower() and "claude" in result.new_model.lower())
            or result.api_mode == "anthropic_messages"
        )
        if cache_enabled:
            lines.append("Prompt caching: enabled")

        if result.warning_message:
            lines.append(f"Warning: {result.warning_message}")

        if persist_global:
            lines.append("Saved to config.yaml (`--global`)")
        else:
            lines.append("_(session only -- add `--global` to persist)_")

        return "\n".join(lines)

    async def _handle_provider_command(self, event: MessageEvent) -> str:
        """Handle /provider command - show available providers."""
        import yaml
        from mimir_cli.models import (
            list_available_providers,
            normalize_provider,
            _PROVIDER_LABELS,
        )

        # Resolve current provider from config
        current_provider = "openrouter"
        model_cfg = {}
        config_path = _hermes_home / 'config.yaml'
        try:
            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                model_cfg = cfg.get("model", {})
                if isinstance(model_cfg, dict):
                    current_provider = model_cfg.get("provider", current_provider)
        except Exception:
            pass

        current_provider = normalize_provider(current_provider)
        if current_provider == "auto":
            try:
                from mimir_cli.auth import resolve_provider as _resolve_provider
                current_provider = _resolve_provider(current_provider)
            except Exception:
                current_provider = "openrouter"

        # Detect custom endpoint from config base_url
        if current_provider == "openrouter":
            _cfg_base = model_cfg.get("base_url", "") if isinstance(model_cfg, dict) else ""
            if _cfg_base and "openrouter.ai" not in _cfg_base:
                current_provider = "custom"

        current_label = _PROVIDER_LABELS.get(current_provider, current_provider)

        lines = [
            f"🔌 **Current provider:** {current_label} (`{current_provider}`)",
            "",
            "**Available providers:**",
        ]

        providers = list_available_providers()
        for p in providers:
            marker = " ← active" if p["id"] == current_provider else ""
            auth = "✅" if p["authenticated"] else "❌"
            aliases = f"  _(also: {', '.join(p['aliases'])})_" if p["aliases"] else ""
            lines.append(f"{auth} `{p['id']}` — {p['label']}{aliases}{marker}")

        lines.append("")
        lines.append("Switch: `/model provider:model-name`")
        lines.append("Setup: `hermes setup`")
        return "\n".join(lines)

    async def _handle_personality_command(self, event: MessageEvent) -> str:
        """Handle /personality command - list or set a personality."""
        import yaml

        args = event.get_command_args().strip().lower()
        config_path = _hermes_home / 'config.yaml'

        try:
            if config_path.exists():
                with open(config_path, 'r', encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                personalities = config.get("agent", {}).get("personalities", {})
            else:
                config = {}
                personalities = {}
        except Exception:
            config = {}
            personalities = {}

        if not personalities:
            from mimir_constants import display_hermes_home

            return f"No personalities configured in `{display_hermes_home()}/config.yaml`"

        if not args:
            lines = ["🎭 **Available Personalities**\n"]
            lines.append("• `none` — (no personality overlay)")
            for name, prompt in personalities.items():
                if isinstance(prompt, dict):
                    preview = prompt.get("description") or prompt.get("system_prompt", "")[:50]
                else:
                    preview = prompt[:50] + "..." if len(prompt) > 50 else prompt
                lines.append(f"• `{name}` — {preview}")
            lines.append("\nUsage: `/personality <name>`")
            return "\n".join(lines)

        def _resolve_prompt(value):
            if isinstance(value, dict):
                parts = [value.get("system_prompt", "")]
                if value.get("tone"):
                    parts.append(f'Tone: {value["tone"]}')
                if value.get("style"):
                    parts.append(f'Style: {value["style"]}')
                return "\n".join(p for p in parts if p)
            return str(value)

        if args in ("none", "default", "neutral"):
            try:
                if "agent" not in config or not isinstance(config.get("agent"), dict):
                    config["agent"] = {}
                config["agent"]["system_prompt"] = ""
                atomic_yaml_write(config_path, config)
            except Exception as e:
                return f"⚠️ Failed to save personality change: {e}"
            self._ephemeral_system_prompt = ""
            return "🎭 Personality cleared — using base agent behavior.\n_(takes effect on next message)_"
        elif args in personalities:
            new_prompt = _resolve_prompt(personalities[args])

            # Write to config.yaml, same pattern as CLI save_config_value.
            try:
                if "agent" not in config or not isinstance(config.get("agent"), dict):
                    config["agent"] = {}
                config["agent"]["system_prompt"] = new_prompt
                atomic_yaml_write(config_path, config)
            except Exception as e:
                return f"⚠️ Failed to save personality change: {e}"

            # Update in-memory so it takes effect on the very next message.
            self._ephemeral_system_prompt = new_prompt

            return f"🎭 Personality set to **{args}**\n_(takes effect on next message)_"

        available = "`none`, " + ", ".join(f"`{n}`" for n in personalities)
        return f"Unknown personality: `{args}`\n\nAvailable: {available}"

    async def _handle_retry_command(self, event: MessageEvent) -> str:
        """Handle /retry command - re-send the last user message."""
        source = event.source
        session_entry = self.session_store.get_or_create_session(source)
        history = self.session_store.load_transcript(session_entry.session_id)
        
        # Find the last user message
        last_user_msg = None
        last_user_idx = None
        for i in range(len(history) - 1, -1, -1):
            if history[i].get("role") == "user":
                last_user_msg = history[i].get("content", "")
                last_user_idx = i
                break
        
        if not last_user_msg:
            return "No previous message to retry."
        
        # Truncate history to before the last user message and persist
        truncated = history[:last_user_idx]
        self.session_store.rewrite_transcript(session_entry.session_id, truncated)
        # Reset stored token count — transcript was truncated
        session_entry.last_prompt_tokens = 0
        
        # Re-send by creating a fake text event with the old message
        retry_event = MessageEvent(
            text=last_user_msg,
            message_type=MessageType.TEXT,
            source=source,
            raw_message=event.raw_message,
        )
        
        # Let the normal message handler process it
        return await self._handle_message(retry_event)

    async def _handle_undo_command(self, event: MessageEvent) -> str:
        """Handle /undo command - remove the last user/assistant exchange."""
        source = event.source
        session_entry = self.session_store.get_or_create_session(source)
        history = self.session_store.load_transcript(session_entry.session_id)
        
        # Find the last user message and remove everything from it onward
        last_user_idx = None
        for i in range(len(history) - 1, -1, -1):
            if history[i].get("role") == "user":
                last_user_idx = i
                break
        
        if last_user_idx is None:
            return "Nothing to undo."
        
        removed_msg = history[last_user_idx].get("content", "")
        removed_count = len(history) - last_user_idx
        self.session_store.rewrite_transcript(session_entry.session_id, history[:last_user_idx])
        # Reset stored token count — transcript was truncated
        session_entry.last_prompt_tokens = 0
        
        preview = removed_msg[:40] + "..." if len(removed_msg) > 40 else removed_msg
        return f"↩️ Undid {removed_count} message(s).\nRemoved: \"{preview}\""

    async def _handle_set_home_command(self, event: MessageEvent) -> str:
        """Handle /sethome command -- set the current chat as the platform's home channel."""
        source = event.source
        platform_name = source.platform.value if source.platform else "unknown"
        chat_id = source.chat_id
        chat_name = source.chat_name or chat_id
        
        env_key = f"{platform_name.upper()}_HOME_CHANNEL"
        
        # Save to config.yaml
        try:
            import yaml
            config_path = _hermes_home / 'config.yaml'
            user_config = {}
            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    user_config = yaml.safe_load(f) or {}
            user_config[env_key] = chat_id
            atomic_yaml_write(config_path, user_config)
            # Also set in the current environment so it takes effect immediately
            os.environ[env_key] = str(chat_id)
        except Exception as e:
            return f"Failed to save home channel: {e}"
        
        return (
            f"✅ Home channel set to **{chat_name}** (ID: {chat_id}).\n"
            f"Cron jobs and cross-platform messages will be delivered here."
        )

