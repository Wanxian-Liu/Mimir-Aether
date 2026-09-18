"""
Delivery routing for cron job outputs and agent responses.

Routes messages to the appropriate destination based on:
- Explicit targets (e.g., "telegram:123456789")
- Platform home channels (e.g., "telegram" → home channel)
- Origin (back to where the job was created)
- Local (always saved to files)
"""

import logging
import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from mimir_cli.config import get_hermes_home

logger = logging.getLogger(__name__)

MAX_PLATFORM_OUTPUT = 4000
TRUNCATED_VISIBLE = 3800


class DeliverySendError(RuntimeError):
    """An adapter reported an unsuccessful send.

    N9 (2026-09-18): adapters signal API-level failure by *returning*
    ``SendResult(success=False, error=...)`` — they do **not** raise (see
    ``gateway/platforms/feishu_adapter.py::send``: an invalid ``receive_id``
    logs "send failed" and returns ``SendResult(success=False)``). N8 assumed
    "no exception => delivered", so such a failure was still recorded as
    ``last_status="ok"`` / ``last_delivery_ok=true`` — silent again, one layer
    below the layer N8 fixed.

    Caught in production rather than by the test suite: cron job
    ``44ff4165be31`` (positive control, 2026-09-18 10:53:33) delivered to a
    non-existent ``chat_id``; Feishu answered ``code=230001 invalid
    receive_id`` and the job stayed ``ok``. The N8 tests used a fake adapter
    that *raised*, so the suite never exercised the real contract.

    Raised so the existing loud path in ``deliver()`` (WARNING + per-target
    ``success: False``) carries adapter-reported failures too.
    """


def _adapter_result_failure(result: Any) -> Optional[str]:
    """Return error text when an adapter's *returned* result reports failure.

    Understands the shapes really used in this codebase:
      * ``SendResult`` (or any object with a ``success`` attribute)
      * plain ``dict`` — ``{"success": False, "error": ...}``

    Returns ``None`` for shapes we do not understand: an unknown return type
    must **not** be reported as failure, otherwise every stub/new adapter would
    start raising false alarms and the alarm would lose its meaning.
    """
    if result is None:
        return None
    if isinstance(result, dict):
        if result.get("success") is False:
            return str(result.get("error") or "adapter reported success=False")
        return None
    if getattr(result, "success", None) is False:
        return str(getattr(result, "error", None) or "adapter reported success=False")
    return None

from .config import Platform, GatewayConfig
from .session import SessionSource


@dataclass
class DeliveryTarget:
    """
    A single delivery target.
    
    Represents where a message should be sent:
    - "origin" → back to source
    - "local" → save to local files
    - "telegram" → Telegram home channel
    - "telegram:123456" → specific Telegram chat
    """
    platform: Platform
    chat_id: Optional[str] = None  # None means use home channel
    thread_id: Optional[str] = None
    is_origin: bool = False
    is_explicit: bool = False  # True if chat_id was explicitly specified
    
    @classmethod
    def parse(cls, target: str, origin: Optional[SessionSource] = None) -> "DeliveryTarget":
        """
        Parse a delivery target string.
        
        Formats:
        - "origin" → back to source
        - "local" → local files only
        - "telegram" → Telegram home channel
        - "telegram:123456" → specific Telegram chat
        """
        target = target.strip().lower()
        
        if target == "origin":
            if origin:
                return cls(
                    platform=origin.platform,
                    chat_id=origin.chat_id,
                    thread_id=origin.thread_id,
                    is_origin=True,
                )
            else:
                # Fallback to local if no origin
                return cls(platform=Platform.LOCAL, is_origin=True)
        
        if target == "local":
            return cls(platform=Platform.LOCAL)
        
        # Check for platform:chat_id or platform:chat_id:thread_id format
        if ":" in target:
            parts = target.split(":", 2)
            platform_str = parts[0]
            chat_id = parts[1] if len(parts) > 1 else None
            thread_id = parts[2] if len(parts) > 2 else None
            try:
                platform = Platform(platform_str)
                return cls(platform=platform, chat_id=chat_id, thread_id=thread_id, is_explicit=True)
            except ValueError:
                # Unknown platform, treat as local
                return cls(platform=Platform.LOCAL)
        
        # Just a platform name (use home channel)
        try:
            platform = Platform(target)
            return cls(platform=platform)
        except ValueError:
            # Unknown platform, treat as local
            return cls(platform=Platform.LOCAL)
    
    def to_string(self) -> str:
        """Convert back to string format."""
        if self.is_origin:
            return "origin"
        if self.platform == Platform.LOCAL:
            return "local"
        if self.chat_id and self.thread_id:
            return f"{self.platform.value}:{self.chat_id}:{self.thread_id}"
        if self.chat_id:
            return f"{self.platform.value}:{self.chat_id}"
        return self.platform.value


class DeliveryRouter:
    """
    Routes messages to appropriate destinations.
    
    Handles the logic of resolving delivery targets and dispatching
    messages to the right platform adapters.
    """
    
    def __init__(self, config: GatewayConfig, adapters: Dict[Platform, Any] = None):
        """
        Initialize the delivery router.
        
        Args:
            config: Gateway configuration
            adapters: Dict mapping platforms to their adapter instances
        """
        self.config = config
        self.adapters = adapters or {}
        self.output_dir = get_hermes_home() / "cron" / "output"

    # N10 (2026-09-18): precedence for a platform's home channel chat id.
    #   gateway_config -- what `GatewayConfig` saw at load (env-derived)
    #   env            -- live process env (`/sethome` updates it in-process)
    #   config_yaml    -- top-level `<PLATFORM>_HOME_CHANNEL` that `/sethome`
    #                     persists (command_handlers._handle_set_home_command)
    # These can drift apart; see `check_home_channels()`.
    _HOME_CHANNEL_SOURCES = ("gateway_config", "env", "config_yaml")

    def home_channel_sources(self, platform: Platform) -> Dict[str, str]:
        """N10 (2026-09-18): every place a home channel chat id can come from.

        Split out of `home_channel_chat_id` so the resolver and the startup
        consistency check read the **same** sources. A guard written against a
        parallel re-implementation can pass while the resolver does something
        else entirely. Only non-empty sources are returned.
        """
        found: Dict[str, str] = {}

        try:
            if self.config is not None:
                hc = self.config.get_home_channel(platform)
                cid = getattr(hc, "chat_id", None) if hc is not None else None
                if cid and str(cid).strip():
                    found["gateway_config"] = str(cid).strip()
        except Exception:  # stub config / unknown platform -> fall through
            pass

        env_val = os.getenv(f"{platform.value.upper()}_HOME_CHANNEL")
        if env_val and str(env_val).strip():
            found["env"] = str(env_val).strip()

        try:
            import yaml

            cfg_path = get_hermes_home() / "config.yaml"
            if cfg_path.is_file():
                data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
                val = data.get(f"{platform.value.upper()}_HOME_CHANNEL")
                if val and str(val).strip():
                    found["config_yaml"] = str(val).strip()
        except Exception:
            pass

        return found

    def home_channel_resolution(self, platform: Platform):
        """Return ``(chat_id, source_name)`` for a platform, by precedence.

        ``(None, None)`` means no home channel is configured anywhere -- the
        caller must then fail **loudly** instead of assuming a destination.
        """
        found = self.home_channel_sources(platform)
        for name in self._HOME_CHANNEL_SOURCES:
            if name in found:
                return found[name], name
        return None, None

    def home_channel_chat_id(self, platform: Platform) -> Optional[str]:
        """N8 (2026-09-18): resolve a platform's home channel chat id.

        `DeliveryTarget.chat_id` documents "None means use home channel" but
        nothing implemented it: `_deliver_to_platform` raised
        `ValueError("No chat ID")` instead, so a bare `deliver: "feishu"` failed
        on **every** run (2026-09-18: 3 executions, 0 messages sent, and the job
        still reported `last_status="ok"`).

        N10 (2026-09-18): the body now delegates to `home_channel_resolution`,
        so the precedence used here is the same list `check_home_channels`
        audits -- guard and resolver cannot drift apart.

        Returns None when nothing is configured => the caller must fail
        **loudly** instead of assuming a destination.
        """
        return self.home_channel_resolution(platform)[0]

    def check_home_channels(self, platforms=None) -> List[Dict[str, Any]]:
        """N10 (2026-09-18): find home-channel sources that disagree.

        A bare `deliver: "feishu"` resolves to whichever source wins the
        precedence -- so a **stale** key is worse than a missing one: the
        message goes to the wrong chat and every status field still reports
        success. That is the residual hole raised on N8 (explicit chat_id is a
        stopgap / "静默送错 比 静默不送 更坏").

        Conflict = two or more sources present with **different** values.
        One source, or none, is not a conflict: "no home channel configured"
        already fails loudly at delivery time (see `_deliver_to_platform`), and
        flagging it here would train everyone to ignore this log line.
        """
        conflicts: List[Dict[str, Any]] = []
        for platform in (list(Platform) if platforms is None else platforms):
            if platform == Platform.LOCAL:
                continue
            try:
                found = self.home_channel_sources(platform)
            except Exception:
                continue
            if len(set(found.values())) <= 1:
                continue  # 0 or 1 distinct value => nothing to disagree about
            value, source = self.home_channel_resolution(platform)
            conflicts.append(
                {
                    "platform": platform.value,
                    "sources": found,
                    "effective": value,
                    "effective_source": source,
                }
            )
        return conflicts

    def log_home_channel_status(self, platforms=None) -> List[Dict[str, Any]]:
        """N10 (2026-09-18): report home-channel conflicts at startup.

        Returns the conflicts found (empty list when clean) and **never raises**
        -- a consistency guard must not be able to take the gateway down.
        """
        try:
            conflicts = self.check_home_channels(platforms)
        except Exception as e:
            logger.warning("Home channel consistency check failed to run: %s", e)
            return []

        for c in conflicts:
            logger.error(
                "HOME CHANNEL CONFLICT for %s: bare `deliver: \"%s\"` resolves to "
                "%s (source=%s) while other sources disagree: %s. A bare platform "
                "target would go to the WRONG chat while every status field still "
                "reports success.",
                c["platform"],
                c["platform"],
                c["effective"],
                c["effective_source"],
                c["sources"],
            )
        return conflicts

    async def deliver(
        self,
        content: str,
        targets: List[DeliveryTarget],
        job_id: Optional[str] = None,
        job_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Deliver content to all specified targets.
        
        Args:
            content: The message/output to deliver
            targets: List of delivery targets
            job_id: Optional job ID (for cron jobs)
            job_name: Optional job name
            metadata: Additional metadata to include
        
        Returns:
            Dict with delivery results per target
        """
        results = {}
        
        for target in targets:
            try:
                if target.platform == Platform.LOCAL:
                    result = self._deliver_local(content, job_id, job_name, metadata)
                else:
                    result = await self._deliver_to_platform(target, content, metadata)

                # N9: defence in depth — a platform sender that is overridden by
                # a subclass may hand back a failure result instead of raising.
                reported = _adapter_result_failure(result)
                if reported:
                    raise DeliverySendError(reported)

                results[target.to_string()] = {
                    "success": True,
                    "result": result
                }
            except Exception as e:
                # N8: a failing target must be audible, not just recorded in a
                # dict the caller may ignore (see cron_mixin).
                logger.warning(
                    "Delivery to %s FAILED: %s", target.to_string(), e
                )
                results[target.to_string()] = {
                    "success": False,
                    "error": str(e)
                }
        
        return results
    
    def _deliver_local(
        self,
        content: str,
        job_id: Optional[str],
        job_name: Optional[str],
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Save content to local files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if job_id:
            output_path = self.output_dir / job_id / f"{timestamp}.md"
        else:
            output_path = self.output_dir / "misc" / f"{timestamp}.md"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build the output document
        lines = []
        if job_name:
            lines.append(f"# {job_name}")
        else:
            lines.append("# Delivery Output")
        
        lines.append("")
        lines.append(f"**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if job_id:
            lines.append(f"**Job ID:** {job_id}")
        
        if metadata:
            for key, value in metadata.items():
                lines.append(f"**{key}:** {value}")
        
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(content)
        
        output_path.write_text("\n".join(lines))
        
        return {
            "path": str(output_path),
            "timestamp": timestamp
        }
    
    def _save_full_output(self, content: str, job_id: str) -> Path:
        """Save full cron output to disk and return the file path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = get_hermes_home() / "cron" / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{job_id}_{timestamp}.txt"
        path.write_text(content)
        return path

    async def _deliver_to_platform(
        self,
        target: DeliveryTarget,
        content: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Deliver content to a messaging platform."""
        adapter = self.adapters.get(target.platform)
        
        if not adapter:
            raise ValueError(f"No adapter configured for {target.platform.value}")
        
        chat_id = target.chat_id or self.home_channel_chat_id(target.platform)
        if not chat_id:
            raise ValueError(
                f"No chat ID for {target.platform.value} delivery — no explicit "
                f"chat_id and no {target.platform.value.upper()}_HOME_CHANNEL configured"
            )
        
        # Guard: truncate oversized cron output to stay within platform limits
        if len(content) > MAX_PLATFORM_OUTPUT:
            job_id = (metadata or {}).get("job_id", "unknown")
            saved_path = self._save_full_output(content, job_id)
            logger.info("Cron output truncated (%d chars) — full output: %s", len(content), saved_path)
            content = (
                content[:TRUNCATED_VISIBLE]
                + f"\n\n... [truncated, full output saved to {saved_path}]"
            )
        
        send_metadata = dict(metadata or {})
        if target.thread_id and "thread_id" not in send_metadata:
            send_metadata["thread_id"] = target.thread_id
        result = await adapter.send(chat_id, content, metadata=send_metadata or None)

        # N9 (2026-09-18): real adapters report API-level failure by RETURNING
        # SendResult(success=False) instead of raising. Counting that as success
        # is precisely the "system says ok, nothing happened" failure mode.
        reported = _adapter_result_failure(result)
        if reported:
            raise DeliverySendError(
                f"{target.platform.value}: adapter reported failure: {reported}"
            )
        return result




