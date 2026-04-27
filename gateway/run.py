#!/usr/bin/env python3
"""
# TODO-自研: Gateway运行入口
# 来源: hermes-agent/gateway/run.py
# 改造点:
#   1. 移除 hermes_cli.config.get_hermes_home → 适配 OpenClaw (~/.openclaw/)
#   2. 移除 hermes_cli.env_loader.load_hermes_dotenv → 适配 OpenClaw dotenv
#   3. 移除 hermes_state.SessionDB → 自研持久化层
#   4. 移除 tools.process_registry → 自研进程注册
#   5. 移除 hermes_logging → 使用 mimiraether_logging
#   6. 移除 hermes_cli.pairing.PairingStore → 自研配对存储
#   7. 移除 tools.tirith_security → 自研安全扫描
#   8. 移除 tools.skills_sync → 自研技能同步
#   9. 移除 Hermes AIAgent 集成 → 适配 OpenClaw agent
#   10. 移除 Hermes 品牌标识
#
# 这个文件是 gateway Phase 2 的核心模块 (9003行 -> 精简骨架)
"""

import asyncio
import json
import logging
import os
import re
import shlex
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any, List

# ---------------------------------------------------------------------------
# SSL certificate auto-detection for NixOS and other non-standard systems.
# Must run BEFORE any HTTP library (discord, aiohttp, etc.) is imported.
# ---------------------------------------------------------------------------
def _ensure_ssl_certs() -> None:
    """Set SSL_CERT_FILE if the system doesn't expose CA certs to Python."""
    if "SSL_CERT_FILE" in os.environ:
        return  # user already configured it

    import ssl

    # 1. Python's compiled-in defaults
    paths = ssl.get_default_verify_paths()
    for candidate in (paths.cafile, paths.openssl_cafile):
        if candidate and os.path.exists(candidate):
            os.environ["SSL_CERT_FILE"] = candidate
            return

    # 2. certifi (ships its own Mozilla bundle)
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
        return
    except ImportError:
        pass

    # 3. Common distro / macOS locations
    for candidate in (
        "/etc/ssl/certs/ca-certificates.crt",               # Debian/Ubuntu/Gentoo
        "/etc/pki/tls/certs/ca-bundle.crt",                 # RHEL/CentOS 7
        "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem", # RHEL/CentOS 8+
        "/etc/ssl/ca-bundle.pem",                            # SUSE/OpenSUSE
        "/etc/ssl/cert.pem",                                 # Alpine / macOS
        "/etc/pki/tls/cert.pem",                             # Fedora
        "/usr/local/etc/openssl@1.1/cert.pem",               # macOS Homebrew Intel
        "/opt/homebrew/etc/openssl@1.1/cert.pem",            # macOS Homebrew ARM
    ):
        if os.path.exists(candidate):
            os.environ["SSL_CERT_FILE"] = candidate
            return

_ensure_ssl_certs()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# OpenClaw Home 目录
# ---------------------------------------------------------------------------
# TODO-自研: 替换 hermes_constants.get_hermes_home
def _get_openclaw_home() -> Path:
    """Return the OpenClaw home directory."""
    return Path.home() / ".openclaw"

_OPENCLAW_HOME = _get_openclaw_home()

# ---------------------------------------------------------------------------
# 环境变量加载
# ---------------------------------------------------------------------------
# TODO-自研: 替换 hermes_cli.env_loader.load_hermes_dotenv
try:
    from dotenv import load_dotenv
    _env_path = _OPENCLAW_HOME / '.env'
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path, override=False)
    # Also load project .env
    _project_env = Path(__file__).resolve().parents[1] / '.env'
    if _project_env.exists():
        load_dotenv(dotenv_path=_project_env, override=False)
except ImportError:
    pass  # dotenv optional

# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------
from .config import load_gateway_config, GatewayConfig

# ---------------------------------------------------------------------------
# 日志设置
# ---------------------------------------------------------------------------
# TODO-自研: 替换 hermes_logging.setup_logging
try:
    from mimiraether_logging import setup_logging
    setup_logging(mode="gateway")
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT = 60.0
DEFAULT_GATEWAY_TIMEOUT = 600.0
DEFAULT_GATEWAY_TIMEOUT_WARNING = 300.0
DEFAULT_NOTIFY_INTERVAL = 60.0

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _normalize_whatsapp_identifier(value: str) -> str:
    """Normalize WhatsApp identifiers to international format."""
    import re
    value = value.strip()
    # Remove common prefixes
    value = re.sub(r'^(?:whatsapp:|wa:|\+?1)[\s\-]*', '', value)
    # Remove non-digit characters except leading +
    if not value.startswith('+'):
        value = re.sub(r'[^\d]', '', value)
    return value


def _expand_whatsapp_auth_aliases(identifier: str) -> set:
    """Expand WhatsApp identifier aliases for authorization matching."""
    normalized = _normalize_whatsapp_identifier(identifier)
    aliases = {normalized}
    # Add with country code if looks like a US number
    if normalized.startswith('1') and len(normalized) == 11:
        aliases.add(normalized[1:])
    return aliases


# TODO-自研: _resolve_runtime_agent_kwargs - 适配 OpenClaw agent
def _resolve_runtime_agent_kwargs() -> dict:
    """Resolve agent runtime kwargs from config/environment.
    
    Returns dict with keys like:
    - model, provider, api_key, base_url, api_mode
    - max_turns, timeout, system_prompt
    - reasoning, vision, etc.
    """
    kwargs = {}
    
    # Agent model
    model = os.environ.get("OPENCLAW_MODEL") or os.environ.get("HERMES_MODEL", "")
    if model:
        kwargs["model"] = model
    
    # Provider
    provider = os.environ.get("OPENCLAW_PROVIDER") or os.environ.get("HERMES_PROVIDER", "")
    if provider:
        kwargs["provider"] = provider
    
    # API key
    api_key = os.environ.get("OPENCLAW_API_KEY") or os.environ.get("HERMES_API_KEY", "")
    if api_key:
        kwargs["api_key"] = api_key
    
    # Base URL
    base_url = os.environ.get("OPENCLAW_BASE_URL") or os.environ.get("HERMES_BASE_URL", "")
    if base_url:
        kwargs["base_url"] = base_url
    
    # Timeout
    timeout = os.environ.get("HERMES_GATEWAY_TIMEOUT")
    if timeout:
        try:
            kwargs["timeout"] = float(timeout)
        except ValueError:
            pass
    
    # Max turns
    max_turns = os.environ.get("HERMES_MAX_ITERATIONS")
    if max_turns:
        try:
            kwargs["max_turns"] = int(max_turns)
        except ValueError:
            pass
    
    return kwargs


# TODO-自研: _build_media_placeholder - 适配 OpenClaw 媒体处理
def _build_media_placeholder(event) -> str:
    """Build a placeholder string for unsupported media types."""
    media_type = getattr(event, 'media_type', 'unknown') if hasattr(event, 'media_type') else 'unknown'
    return f"[Media: {media_type} — preview not available in this context]"


# TODO-自研: _dequeue_pending_event - 适配 OpenClaw 事件队列
def _dequeue_pending_event(adapter, session_key: str):
    """Dequeue a pending event for a session from an adapter."""
    # TODO-自研: 实现 OpenClaw 事件队列
    return None


# TODO-自研: _check_unavailable_skill - 适配 OpenClaw skill
def _check_unavailable_skill(command_name: str) -> str | None:
    """Check if a skill is unavailable and return an error message."""
    # TODO-自研: 实现 OpenClaw skill 检查
    return None


def _platform_config_key(platform: "Platform") -> str:
    """Get the environment variable key for a platform's token."""
    return f"{platform.value.upper()}_BOT_TOKEN"


def _load_gateway_config() -> dict:
    """Load gateway config dict (legacy helper)."""
    config = load_gateway_config()
    return config.to_dict()


def _resolve_gateway_model(config: dict | None = None) -> str:
    """Resolve the gateway model from config."""
    # TODO-自研: 适配 OpenClaw model resolution
    return os.environ.get("OPENCLAW_MODEL", "auto")


def _resolve_openclaw_bin() -> Optional[list[str]]:
    """Resolve the openclaw binary path for detached restart."""
    import shutil
    bin_path = shutil.which("openclaw")
    if bin_path:
        return [bin_path, "gateway", "run"]
    
    # Try common locations
    candidates = [
        Path("/usr/local/bin/openclaw"),
        Path.home() / ".local" / "bin" / "openclaw",
        _OPENCLAW_HOME / "bin" / "openclaw",
    ]
    for cand in candidates:
        if cand.exists():
            return [str(cand), "gateway", "run"]
    return None


def _format_gateway_process_notification(evt: dict) -> str | None:
    """Format a gateway process event as a notification message."""
    event_type = evt.get("type", "")
    if event_type == "restart_requested":
        return "Gateway restart requested..."
    elif event_type == "restart_begin":
        return "Gateway restarting..."
    elif event_type == "exit_scheduled":
        return f"Gateway exit scheduled: {evt.get('reason', 'unknown')}"
    return None


# ---------------------------------------------------------------------------
# GatewayRunner
# ---------------------------------------------------------------------------
class GatewayRunner:
    """
    Main gateway controller.

    Manages the lifecycle of all platform adapters and routes
    messages to/from the agent.

    # TODO-自研: 基于 hermes-agent GatewayRunner 改造
    # 原始: 8200+ 行，管理 Hermes AIAgent 生命周期
    # 自研: 适配 OpenClaw agent 和 OpenClaw 配置结构
    """

    # Class-level defaults so partial construction in tests doesn't
    # blow up on attribute access.
    _running_agents_ts: Dict[str, float] = {}
    _busy_input_mode: str = "interrupt"
    _restart_drain_timeout: float = DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT
    _exit_code: Optional[int] = None
    _draining: bool = False
    _restart_requested: bool = False
    _restart_task_started: bool = False
    _restart_detached: bool = False
    _restart_via_service: bool = False
    _stop_task: Optional[asyncio.Task] = None
    _session_model_overrides: Dict[str, Dict[str, str]] = {}

    def __init__(self, config: Optional[GatewayConfig] = None):
        # TODO-自研: 替换 hermes-specific 初始化
        self.config = config or load_gateway_config()
        self.adapters: Dict[Platform, Any] = {}

        # Load ephemeral config from config.yaml / env vars.
        self._prefill_messages = self._load_prefill_messages()
        self._ephemeral_system_prompt = self._load_ephemeral_system_prompt()
        self._reasoning_config = self._load_reasoning_config()
        self._service_tier = self._load_service_tier()
        self._show_reasoning = self._load_show_reasoning()
        self._busy_input_mode = self._load_busy_input_mode()
        self._restart_drain_timeout = self._load_restart_drain_timeout()
        self._provider_routing = self._load_provider_routing()
        self._fallback_model = self._load_fallback_model()
        self._smart_model_routing = self._load_smart_model_routing()

        # Wire process registry into session store for reset protection
        # TODO-自研: 替换 tools.process_registry
        try:
            from tools.process_registry import process_registry
            _has_active_fn = lambda key: process_registry.has_active_for_session(key)
        except ImportError:
            _has_active_fn = None

        from .session import SessionStore
        self.session_store = SessionStore(
            self.config.sessions_dir, self.config,
            has_active_processes_fn=_has_active_fn,
        )
        
        # TODO-自研: DeliveryRouter - 适配 OpenClaw delivery
        from .delivery import DeliveryRouter
        self.delivery_router = DeliveryRouter(self.config)
        
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._exit_cleanly = False
        self._exit_with_failure = False
        self._exit_reason: Optional[str] = None
        self._exit_code: Optional[int] = None
        self._draining = False
        self._restart_requested = False
        self._restart_task_started = False
        self._restart_detached = False
        self._restart_via_service = False
        self._stop_task: Optional[asyncio.Task] = None

        # Track running agents per session for interrupt support
        # Key: session_key, Value: AIAgent instance
        self._running_agents: Dict[str, Any] = {}
        self._running_agents_ts: Dict[str, float] = {}  # start timestamp per session
        self._pending_messages: Dict[str, str] = {}  # Queued messages during interrupt

        # Cache AIAgent instances per session to preserve prompt caching.
        # Key: session_key, Value: (AIAgent, config_signature_str)
        import threading as _threading
        self._agent_cache: Dict[str, tuple] = {}
        self._agent_cache_lock = _threading.Lock()

        # Per-session model overrides from /model command.
        self._session_model_overrides: Dict[str, Dict[str, str]] = {}
        # Track pending exec approvals per session
        self._pending_approvals: Dict[str, Dict[str, Any]] = {}

        # Track platforms that failed to connect for background reconnection.
        self._failed_platforms: Dict[Platform, Dict[str, Any]] = {}

        # Track pending /update prompt responses per session.
        self._update_prompt_pending: Dict[str, bool] = {}

        # TODO-自研: 移除 tirith_security
        # try:
        #     from tools.tirith_security import ensure_installed
        #     ensure_installed(log_failures=False)
        # except Exception:
        #     pass

        # TODO-自研: 替换 hermes_state.SessionDB
        self._session_db = None
        # try:
        #     from openclaw_state import SessionDB  # TODO-自研: 实现此模块
        #     self._session_db = SessionDB()
        # except Exception as e:
        #     logger.debug("SQLite session store not available: %s", e)

        # TODO-自研: 替换 gateway.pairing.PairingStore
        try:
            from .pairing import PairingStore
            self.pairing_store = PairingStore()
        except ImportError:
            self.pairing_store = None

        # TODO-自研: 替换 gateway.hooks.HookRegistry
        try:
            from .hooks import HookRegistry
            self.hooks = HookRegistry()
        except ImportError:
            self.hooks = None

        # Per-chat voice reply mode: "off" | "voice_only" | "all"
        self._voice_mode: Dict[str, str] = self._load_voice_modes()

        # Track background tasks to prevent garbage collection mid-execution
        self._background_tasks: set = set()

    # -- Setup skill availability ----------------------------------------

    def _has_setup_skill(self) -> bool:
        """Check if the openclaw-setup skill is installed."""
        # TODO-自研: 适配 OpenClaw skill 检查
        try:
            from tools.skill_manager_tool import _find_skill
            return _find_skill("openclaw-setup") is not None
        except Exception:
            return False

    # -- Voice mode persistence ------------------------------------------

    _VOICE_MODE_PATH = _OPENCLAW_HOME / "gateway_voice_mode.json"

    def _load_voice_modes(self) -> Dict[str, str]:
        try:
            data = json.loads(self._VOICE_MODE_PATH.read_text())
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if isinstance(v, str)}

    def _save_voice_modes(self) -> None:
        try:
            self._VOICE_MODE_PATH.write_text(json.dumps(self._voice_mode))
        except OSError:
            pass

    def _set_adapter_auto_tts_disabled(self, adapter, chat_id: str, disabled: bool) -> None:
        """Set per-chat TTS override."""
        # TODO-自研: 实现 OpenClaw TTS 禁用逻辑
        pass

    def _sync_voice_mode_state_to_adapter(self, adapter) -> None:
        """Sync voice mode settings to a newly-started adapter."""
        # TODO-自研: 实现 OpenClaw voice mode sync
        pass

    # -- Memory flushing -------------------------------------------------

    # TODO-自研: _flush_memories_for_session - 适配 OpenClaw memory
    def _flush_memories_for_session(
        self,
        session_key: str,
        session_entry: "SessionEntry",
    ) -> bool:
        """Flush session memories to the memory system.

        Returns True if memories were flushed (or already flushed).
        Returns False on error so the expiry watcher retries.
        """
        # TODO-自研: 实现 OpenClaw memory 刷新
        # 原始: hermes 使用 hermes_memory.flush_session_memories()
        # 自研: 需要适配 OpenClaw memory API
        if session_entry.memory_flushed:
            return True
        try:
            # from hermes_memory import flush_session_memories
            # result = flush_session_memories(session_key, ...)
            # session_entry.memory_flushed = True
            # self.session_store.update_session(session_key)
            session_entry.memory_flushed = True
            return True
        except Exception as e:
            logger.debug("Memory flush failed for %s: %s", session_key, e)
            return False

    async def _async_flush_memories(
        self,
        session_key: str,
        session_entry: "SessionEntry",
    ) -> bool:
        """Async wrapper for memory flushing."""
        return self._flush_memories_for_session(session_key, session_entry)

    # -- Exit status ----------------------------------------------------

    def should_exit_cleanly(self) -> bool:
        return self._exit_cleanly

    def should_exit_with_failure(self) -> bool:
        return self._exit_with_failure

    def exit_reason(self) -> Optional[str]:
        return self._exit_reason

    def exit_code(self) -> Optional[int]:
        return self._exit_code

    # -- Session helpers -------------------------------------------------

    def _session_key_for_source(self, source: "SessionSource") -> str:
        """Build session key from a SessionSource."""
        from .session import build_session_key
        return build_session_key(
            source,
            group_sessions_per_user=self.config.group_sessions_per_user,
            thread_sessions_per_user=self.config.thread_sessions_per_user,
        )

    # -- Agent config resolution -----------------------------------------

    # TODO-自研: _resolve_session_agent_runtime - 适配 OpenClaw agent runtime
    def _resolve_session_agent_runtime(
        self,
        source: "SessionSource",
        session_entry: "SessionEntry",
    ) -> dict:
        """Resolve agent runtime kwargs for a session.

        Combines:
        - Global config (from config.yaml / env)
        - Per-session model overrides (from /model command)
        - Platform-specific settings
        """
        kwargs = _resolve_runtime_agent_kwargs()

        # Apply per-session model override
        session_key = session_entry.session_key
        if session_key in self._session_model_overrides:
            override = self._session_model_overrides[session_key]
            kwargs.update(override)

        # Apply platform-specific settings
        if source.platform.value in self._provider_routing:
            route = self._provider_routing[source.platform.value]
            if route.get("model"):
                kwargs.setdefault("model", route["model"])
            if route.get("provider"):
                kwargs.setdefault("provider", route["provider"])

        return kwargs

    def _resolve_turn_agent_config(self, user_message: str, model: str, runtime_kwargs: dict) -> dict:
        """Resolve final agent config for a turn, considering dynamic routing."""
        # TODO-自研: 实现动态模型路由
        return runtime_kwargs

    # -- Adapter lifecycle -----------------------------------------------

    async def _handle_adapter_fatal_error(self, adapter: Any) -> None:
        """Handle a fatal error from an adapter."""
        platform = getattr(adapter, 'platform', None)
        logger.error("Adapter for %s had a fatal error", platform)
        if platform and platform in self.adapters:
            del self.adapters[platform]
        if platform:
            self._failed_platforms[platform] = {
                "config": getattr(adapter, 'config', None),
                "attempts": 0,
                "next_retry": 0.0,
            }

    # -- Exit management ------------------------------------------------

    def _request_clean_exit(self, reason: str) -> None:
        self._exit_cleanly = True
        self._exit_reason = reason

    def _running_agent_count(self) -> int:
        return len(self._running_agents)

    def _status_action_label(self) -> str:
        if self._restart_requested:
            return "Restarting"
        if self._draining:
            return "Draining"
        if self._running_agents:
            return "Busy"
        return "Ready"

    def _status_action_gerund(self) -> str:
        if self._restart_requested:
            return "restarting"
        if self._draining:
            return "draining"
        if self._running_agents:
            return "processing"
        return "idle"

    def _queue_during_drain_enabled(self) -> bool:
        return False  # TODO-自研

    def _update_runtime_status(self, gateway_state: Optional[str] = None, exit_reason: Optional[str] = None) -> None:
        # TODO-自研: 更新运行时状态
        pass

    def _update_platform_runtime_status(self, platform: "Platform", state: str, message: str = "") -> None:
        # TODO-自研: 更新平台状态
        pass

    # -- Ephemeral config loaders ----------------------------------------

    def _load_prefill_messages() -> List[Dict[str, Any]]:
        # TODO-自研: 加载预填充消息
        return []

    def _load_ephemeral_system_prompt() -> str:
        # TODO-自研: 加载临时系统提示词
        return ""

    def _load_reasoning_config() -> dict | None:
        # TODO-自研: 加载 reasoning 配置
        return None

    def _load_service_tier() -> str | None:
        return os.environ.get("OPENCLAW_SERVICE_TIER") or os.environ.get("HERMES_SERVICE_TIER")

    def _load_show_reasoning() -> bool:
        val = os.environ.get("OPENCLAW_SHOW_REASONING") or os.environ.get("HERMES_SHOW_REASONING", "true")
        return val.lower() in ("true", "1", "yes")

    def _load_busy_input_mode() -> str:
        return os.environ.get("OPENCLAW_GATEWAY_BUSY_INPUT_MODE") or os.environ.get("HERMES_GATEWAY_BUSY_INPUT_MODE", "interrupt")

    def _load_restart_drain_timeout() -> float:
        val = os.environ.get("OPENCLAW_RESTART_DRAIN_TIMEOUT") or os.environ.get("HERMES_RESTART_DRAIN_TIMEOUT")
        if val:
            try:
                return float(val)
            except ValueError:
                pass
        return DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT

    def _load_background_notifications_mode() -> str:
        return os.environ.get("OPENCLAW_BACKGROUND_NOTIFICATIONS_MODE", "queued")

    def _load_provider_routing() -> dict:
        # TODO-自研: 加载 provider routing 配置
        return {}

    def _load_fallback_model(self) -> list | dict | None:
        # TODO-自研: 加载 fallback model 配置
        return None

    def _load_smart_model_routing(self) -> dict:
        # TODO-自研: 加载智能模型路由
        return {}

    # -- Agent caching ---------------------------------------------------

    def _snapshot_running_agents(self) -> Dict[str, Any]:
        return dict(self._running_agents)

    def _queue_or_replace_pending_event(self, session_key: str, event: Any) -> None:
        """Queue or replace a pending event for a session during interrupt."""
        self._pending_messages[session_key] = event

    # -- Interrupt handling ----------------------------------------------

    async def _handle_active_session_busy_message(self, event: Any, session_key: str) -> bool:
        """Handle a message arriving while the session's agent is busy.

        Returns True if the message was handled (queued or rejected).
        Returns False if it should be processed normally.
        """
        if self._busy_input_mode == "queue" and self._queue_during_drain_enabled():
            self._queue_or_replace_pending_event(session_key, event)
            return True
        elif self._busy_input_mode == "interrupt":
            self._interrupt_running_agents(f"new message from {session_key}")
            return False  # Let the new message proceed
        else:
            # reject
            return True

    async def _drain_active_agents(self, timeout: float) -> tuple[Dict[str, Any], bool]:
        """Wait for running agents to finish gracefully.

        Returns (snapshot of agents, whether all drained within timeout).
        """
        # TODO-自研: 实现 agent 排水逻辑
        return ({}, True)

    def _interrupt_running_agents(self, reason: str) -> None:
        """Send interrupt signal to all running agents."""
        # TODO-自研: 实现 agent 中断
        for key, agent in list(self._running_agents.items()):
            try:
                if hasattr(agent, 'interrupt'):
                    agent.interrupt(reason)
            except Exception:
                pass

    def _finalize_shutdown_agents(self, active_agents: Dict[str, Any]) -> None:
        """Finalize shutdown of agents after drain timeout."""
        # TODO-自研: 实现 agent 关闭
        pass

    # -- Restart ---------------------------------------------------------

    async def _launch_detached_restart_command(self) -> None:
        """Launch a detached restart command (for background service restart)."""
        bin_path = _resolve_openclaw_bin()
        if not bin_path:
            logger.error("Cannot restart: openclaw binary not found")
            return

        logger.info("Launching detached restart: %s", " ".join(bin_path))

        # TODO-自研: 实现 detached restart
        # Original: subprocess.Popen([bin_path + ["--replace"], ...])
        pass

    def request_restart(self, *, detached: bool = False, via_service: bool = False) -> bool:
        """Request gateway restart.

        Returns True if restart was scheduled, False if already restarting.
        """
        if self._restart_requested:
            return False

        self._restart_requested = True
        self._restart_detached = detached
        self._restart_via_service = via_service

        async def _run_restart() -> None:
            await asyncio.sleep(0.1)
            await self._graceful_shutdown(reason="restart")

        asyncio.create_task(_run_restart())
        return True

    # -- Main lifecycle --------------------------------------------------

    async def start(self) -> bool:
        """Start the gateway.

        Returns True if started successfully, False on error.
        """
        # TODO-自研: 实现 gateway 启动逻辑
        # 原始: 加载所有配置的平台适配器，启动 cron ticker，启动 session expiry watcher
        if self._running:
            return True

        logger.info("Starting MimirAether Gateway...")
        self._running = True

        # Load platform adapters
        for platform in self.config.get_connected_platforms():
            try:
                adapter = self._create_adapter(platform)
                if adapter:
                    await adapter.start()
                    self.adapters[platform] = adapter
                    logger.info(f"Adapter started: {platform.value}")
            except Exception as e:
                logger.error(f"Failed to start adapter {platform.value}: {e}")
                self._failed_platforms[platform] = {
                    "config": self.config.platforms.get(platform),
                    "attempts": 1,
                    "next_retry": time.time() + 60,
                }

        # Start background tasks
        asyncio.create_task(self._session_expiry_watcher())
        asyncio.create_task(self._platform_reconnect_watcher())

        logger.info(f"Gateway started with {len(self.adapters)} adapter(s)")
        return True

    # -- Background watchers --------------------------------------------

    async def _session_expiry_watcher(self, interval: int = 300):
        """Background watcher that flushes memories for expired sessions."""
        while self._running:
            try:
                await asyncio.sleep(interval)
                if not self._running:
                    break

                for entry in self.session_store.list_sessions():
                    if self.session_store._is_session_expired(entry):  # noqa: access _is_session_expired
                        await self._async_flush_memories(entry.session_key, entry)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Session expiry watcher error: %s", e)

    async def _platform_reconnect_watcher(self) -> None:
        """Background watcher that retries connecting failed platforms."""
        retry_delay = 60
        while self._running:
            try:
                await asyncio.sleep(retry_delay)
                if not self._running:
                    break

                now = time.time()
                for platform, state in list(self._failed_platforms.items()):
                    if state["next_retry"] <= now:
                        try:
                            adapter = self._create_adapter(platform)
                            if adapter:
                                await adapter.start()
                                self.adapters[platform] = adapter
                                del self._failed_platforms[platform]
                                logger.info(f"Reconnected platform: {platform.value}")
                        except Exception as e:
                            state["attempts"] += 1
                            state["next_retry"] = now + min(300, 30 * state["attempts"])
                            logger.debug(f"Reconnect failed for {platform.value}: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Platform reconnect watcher error: %s", e)

    # -- Shutdown -------------------------------------------------------

    async def stop(
        self,
        reason: str = "stopped",
        timeout: Optional[float] = None,
    ) -> None:
        """Stop the gateway and all adapters."""
        # TODO-自研: 实现 gateway 停止逻辑
        await self._stop_impl(reason, timeout)

    async def _stop_impl(
        self,
        reason: str = "stopped",
        timeout: Optional[float] = None,
    ) -> None:
        """Internal stop implementation."""
        if not self._running:
            return

        logger.info("Stopping gateway: %s", reason)
        self._running = False
        self._shutdown_event.set()

        # Stop adapters
        for platform, adapter in list(self.adapters.items()):
            try:
                await adapter.stop()
                logger.info(f"Adapter stopped: {platform.value}")
            except Exception as e:
                logger.error(f"Error stopping adapter {platform.value}: {e}")

        self.adapters.clear()

    async def wait_for_shutdown(self) -> None:
        """Wait for the shutdown event."""
        await self._shutdown_event.wait()

    # -- Adapter factory ------------------------------------------------

    def _create_adapter(self, platform: "Platform") -> Optional[Any]:
        """Create a platform adapter instance."""
        # TODO-自研: 实现 OpenClaw 适配器工厂
        # 原始: 根据平台类型创建对应的适配器实例
        # 自研: 适配 OpenClaw 的平台适配器
        from .adapter import PlatformAdapter

        pconfig = self.config.platforms.get(platform)
        if not pconfig:
            return None

        if platform.value == "telegram":
            try:
                from .telegram_adapter import TelegramAdapter
                return TelegramAdapter(pconfig, self)
            except ImportError:
                return None
        elif platform.value == "discord":
            try:
                from .discord_adapter import DiscordAdapter
                return DiscordAdapter(pconfig, self)
            except ImportError:
                return None
        elif platform.value == "feishu":
            try:
                from .feishu_adapter import FeishuAdapter
                return FeishuAdapter(pconfig, self)
            except ImportError:
                return None

        logger.warning(f"No adapter available for platform: {platform.value}")
        return None

    # -- Message handling -----------------------------------------------

    def _is_user_authorized(self, source: "SessionSource") -> bool:
        """Check if a user is authorized to use the gateway."""
        # TODO-自研: 实现用户授权检查
        # 原始: 使用 PairingStore 检查授权
        if self.pairing_store is None:
            return True  # No pairing store = open access
        return True

    def _get_unauthorized_dm_behavior(self, platform: Optional["Platform"]) -> str:
        """Get behavior for unauthorized DMs on a platform."""
        return self.config.get_unauthorized_dm_behavior(platform)

    # TODO-自研: _handle_message - 核心消息处理
    async def _handle_message(self, event: Any) -> Optional[str]:
        """Handle an incoming message event.

        Returns a response string, or None for no response.
        """
        # TODO-自研: 实现完整消息处理
        # 原始: 900+ 行，包括:
        #   - 授权检查
        #   - 消息预处理
        #   - 快速命令处理
        #   - session 获取/创建
        #   - agent 调用
        #   - 响应发送
        pass

    async def _prepare_inbound_message_text(self, event: Any) -> str:
        """Prepare and clean the inbound message text."""
        # TODO-自研: 实现消息文本准备
        text = getattr(event, 'text', '') or ''
        return text.strip()

    # TODO-自研: _handle_message_with_agent - agent 调用核心
    async def _handle_message_with_agent(self, event, source, _quick_key: str):
        """Handle a message by running it through the agent.

        This is the main agent-loop entry point.
        """
        # TODO-自研: 实现 agent 调用
        # 原始: 500+ 行，包括:
        #   - session transcript 加载
        #   - system prompt 构建
        #   - agent runtime 解析
        #   - AIAgent 调用 (with streaming, tool calls, etc.)
        #   - 响应格式化
        #   - transcript 持久化
        pass

    # -- Command handlers -----------------------------------------------

    async def _handle_reset_command(self, event: Any) -> str:
        """Handle /reset command."""
        # TODO-自研
        return "Reset not yet implemented"

    async def _handle_status_command(self, event: Any) -> str:
        """Handle /status command."""
        # TODO-自研
        adapters = [f"{p.value}: {'running' if p in self.adapters else 'stopped'}" 
                    for p in self.config.get_connected_platforms()]
        return f"MimirAether Gateway\nAdapters: {', '.join(adapters) or 'none'}"

    async def _handle_stop_command(self, event: Any) -> str:
        """Handle /stop command."""
        # TODO-自研
        return "Stop not yet implemented"

    async def _handle_restart_command(self, event: Any) -> str:
        """Handle /restart command."""
        # TODO-自研
        return "Restart not yet implemented"

    async def _handle_help_command(self, event: Any) -> str:
        """Handle /help command."""
        # TODO-自研
        return "MimirAether Gateway\n\nCommands: /help, /status, /reset, /stop, /restart"

    async def _handle_commands_command(self, event: Any) -> str:
        """Handle /commands command - list all available commands."""
        # TODO-自研
        return "Commands: reset, status, stop, restart, help, commands, model, provider, personality"

    # -- /model command -------------------------------------------------

    async def _handle_model_command(self, event: Any) -> Optional[str]:
        """Handle /model command - show or set the model for a session."""
        # TODO-自研
        pass

    async def _handle_provider_command(self, event: Any) -> str:
        """Handle /provider command."""
        # TODO-自研
        return "Provider command not yet implemented"

    async def _handle_personality_command(self, event: Any) -> str:
        """Handle /personality command."""
        # TODO-自研
        return "Personality command not yet implemented"

    # -- /retry and /undo ----------------------------------------------

    async def _handle_retry_command(self, event: Any) -> str:
        """Handle /retry command."""
        # TODO-自研
        return "Retry not yet implemented"

    async def _handle_undo_command(self, event: Any) -> str:
        """Handle /undo command."""
        # TODO-自研
        return "Undo not yet implemented"

    # -- /compress, /title, /branch -----------------------------------

    async def _handle_compress_command(self, event: Any) -> str:
        """Handle /compress command."""
        # TODO-自研
        return "Compress not yet implemented"

    async def _handle_title_command(self, event: Any) -> str:
        """Handle /title command."""
        # TODO-自研
        return "Title not yet implemented"

    async def _handle_resume_command(self, event: Any) -> str:
        """Handle /resume command."""
        # TODO-自研
        return "Resume not yet implemented"

    async def _handle_branch_command(self, event: Any) -> str:
        """Handle /branch command."""
        # TODO-自研
        return "Branch not yet implemented"

    # -- /usage and /insights ------------------------------------------

    async def _handle_usage_command(self, event: Any) -> str:
        """Handle /usage command."""
        # TODO-自研
        return "Usage not yet implemented"

    async def _handle_insights_command(self, event: Any) -> str:
        """Handle /insights command."""
        # TODO-自研
        return "Insights not yet implemented"

    # -- /approve, /deny ----------------------------------------------

    async def _handle_approve_command(self, event: Any) -> Optional[str]:
        """Handle /approve command for pending exec approvals."""
        # TODO-自研
        pass

    async def _handle_deny_command(self, event: Any) -> str:
        """Handle /deny command for pending exec approvals."""
        # TODO-自研
        return "Deny not yet implemented"

    # -- /debug --------------------------------------------------------

    async def _handle_debug_command(self, event: Any) -> str:
        """Handle /debug command."""
        # TODO-自研
        return "Debug not yet implemented"

    # -- /update -------------------------------------------------------

    async def _handle_update_command(self, event: Any) -> str:
        """Handle /update command for updating system prompt."""
        # TODO-自研
        return "Update not yet implemented"

    # -- Voice ---------------------------------------------------------

    async def _handle_voice_command(self, event: Any) -> str:
        """Handle /voice command."""
        # TODO-自研
        return "Voice not yet implemented"

    async def _handle_voice_channel_join(self, event: Any) -> str:
        """Handle voice channel join."""
        # TODO-自研
        return "Voice channel join not yet implemented"

    async def _handle_voice_channel_leave(self, event: Any) -> str:
        """Handle voice channel leave."""
        # TODO-自研
        return "Voice channel leave not yet implemented"

    def _should_send_voice_reply(self, event: Any) -> bool:
        """Check if a voice reply should be sent."""
        # TODO-自研
        return False

    async def _send_voice_reply(self, event: Any, text: str) -> None:
        """Send a voice reply to an event."""
        # TODO-自研
        pass

    # -- Media delivery ------------------------------------------------

    async def _deliver_media_from_response(self, event: Any, response_text: str) -> None:
        """Deliver media attachments from an agent response."""
        # TODO-自研
        pass

    # -- /background and /btw ----------------------------------------

    async def _handle_background_command(self, event: Any) -> str:
        """Handle /background command."""
        # TODO-自研
        return "Background not yet implemented"

    async def _run_background_task(self, event: Any, command_text: str) -> None:
        """Run a task in the background."""
        # TODO-自研
        pass

    async def _handle_btw_command(self, event: Any) -> str:
        """Handle /btw (background thought) command."""
        # TODO-自研
        return "Btw not yet implemented"

    async def _run_btw_task(self, event: Any, btw_text: str) -> None:
        """Run a btw (background thought) task."""
        # TODO-自研
        pass

    # -- /reasoning, /fast, /yolo, /verbose ---------------------------

    async def _handle_reasoning_command(self, event: Any) -> str:
        """Handle /reasoning command."""
        # TODO-自研
        return "Reasoning not yet implemented"

    async def _handle_fast_command(self, event: Any) -> str:
        """Handle /fast command."""
        # TODO-自研
        return "Fast not yet implemented"

    async def _handle_yolo_command(self, event: Any) -> str:
        """Handle /yolo command."""
        # TODO-自研
        return "Yolo not yet implemented"

    async def _handle_verbose_command(self, event: Any) -> str:
        """Handle /verbose command."""
        # TODO-自研
        return "Verbose not yet implemented"

    # -- /rollback -----------------------------------------------------

    async def _handle_rollback_command(self, event: Any) -> str:
        """Handle /rollback command."""
        # TODO-自研
        return "Rollback not yet implemented"

    # -- /sethome ------------------------------------------------------

    async def _handle_set_home_command(self, event: Any) -> str:
        """Handle /sethome command."""
        # TODO-自研
        return "SetHome not yet implemented"

    # -- /reload_mcp ---------------------------------------------------

    async def _handle_reload_mcp_command(self, event: Any) -> str:
        """Handle /reload_mcp command."""
        # TODO-自研
        return "ReloadMCP not yet implemented"

    # -- Session info --------------------------------------------------

    def _format_session_info(self) -> str:
        """Format session information for display."""
        # TODO-自研
        sessions = self.session_store.list_sessions()
        if not sessions:
            return "No active sessions"
        lines = [f"Active sessions: {len(sessions)}"]
        for entry in sessions[:5]:
            lines.append(f"  - {entry.session_key}: {entry.session_id}")
        return "\n".join(lines)

    # -- Agent execution -----------------------------------------------

    # TODO-自研: _run_agent - agent 执行核心
    async def _run_agent(
        self,
        session_key: str,
        session_entry: "SessionEntry",
        messages: list,
        runtime_kwargs: dict,
        event: Any,
    ) -> tuple[str, bool]:
        """Run the agent for a session.

        Returns (response_text, should_deliver).
        """
        # TODO-自研: 实现 OpenClaw agent 调用
        # 原始: 800+ 行，包括:
        #   - streaming consumer
        #   - tool call handling
        #   - progress messages
        #   - approval workflow
        #   - interrupt monitoring
        #   - long-running notification
        return ("", False)

    def _agent_config_signature(self, runtime_kwargs: dict) -> str:
        """Build a signature string for agent cache keying."""
        sig_parts = []
        for key in sorted(runtime_kwargs.keys()):
            val = runtime_kwargs[key]
            if val is not None:
                sig_parts.append(f"{key}={val}")
        return "|".join(sig_parts)

    def _apply_session_model_override(self, session_key: str, override: dict) -> None:
        """Apply a per-session model override."""
        self._session_model_overrides[session_key] = override
        self._evict_cached_agent(session_key)

    def _is_intentional_model_switch(self, session_key: str, agent_model: str) -> bool:
        """Check if a model switch was explicitly requested via /model."""
        return session_key in self._session_model_overrides

    def _evict_cached_agent(self, session_key: str) -> None:
        """Remove a cached agent instance."""
        with self._agent_cache_lock:
            self._agent_cache.pop(session_key, None)

    # -- Signal handlers -----------------------------------------------

    def shutdown_signal_handler(self):
        """Handle shutdown signal."""
        asyncio.create_task(self.stop(reason="signal"))

    def restart_signal_handler(self):
        """Handle restart signal."""
        asyncio.create_task(self._graceful_shutdown(reason="restart"))


# ---------------------------------------------------------------------------
# Background cron ticker
# ---------------------------------------------------------------------------

def _start_cron_ticker(stop_event: threading.Event, adapters=None, loop=None, interval: int = 60):
    """Start a background thread that ticks every `interval` seconds.

    Used to trigger scheduled cron jobs while the gateway is running.
    """
    # TODO-自研: 实现 cron ticker
    # 原始: 在每个 tick 调用 cron 调度器检查任务
    pass


# ---------------------------------------------------------------------------
# Gateway startup
# ---------------------------------------------------------------------------

async def start_gateway(
    config: Optional[GatewayConfig] = None,
    replace: bool = False,
    verbosity: Optional[int] = 0,
) -> bool:
    """
    Start the gateway and run until interrupted.

    This is the main entry point for running the gateway.
    Returns True if the gateway ran successfully, False if it failed to start.
    A False return causes a non-zero exit code so systemd can auto-restart.

    Args:
        config: Optional gateway configuration override.
        replace: If True, kill any existing gateway instance before starting.
        verbosity: Logging verbosity (0=INFO, 1=DEBUG, 2+=DEBUG with more detail)
    """
    # TODO-自研: 替换 hermes-specific 重复实例 guard
    # 原始: 使用 hermes_status.get_running_pid()
    import time as _time
    try:
        from .status import get_running_pid, remove_pid_file, terminate_pid
        existing_pid = get_running_pid()
        if existing_pid is not None and existing_pid != os.getpid():
            if replace:
                logger.info("Replacing existing gateway instance (PID %d)", existing_pid)
                try:
                    terminate_pid(existing_pid, force=False)
                except ProcessLookupError:
                    pass
                except (PermissionError, OSError):
                    logger.error("Permission denied killing PID %d", existing_pid)
                    return False
                # Wait for old process to exit
                for _ in range(20):
                    try:
                        os.kill(existing_pid, 0)
                        _time.sleep(0.5)
                    except (ProcessLookupError, PermissionError):
                        break
                else:
                    try:
                        terminate_pid(existing_pid, force=True)
                        _time.sleep(0.5)
                    except (ProcessLookupError, PermissionError, OSError):
                        pass
                remove_pid_file()
                try:
                    from .status import release_all_scoped_locks
                    released = release_all_scoped_locks()
                    if released:
                        logger.info("Released %d stale scoped lock(s)", released)
                except Exception:
                    pass
            else:
                logger.error(
                    "Another gateway instance is already running (PID %d). "
                    "Use 'openclaw gateway restart' to replace it.",
                    existing_pid,
                )
                return False
    except ImportError:
        pass  # Status module not available

    # Sync bundled skills on gateway start
    try:
        from tools.skills_sync import sync_skills
        sync_skills(quiet=True)
    except ImportError:
        pass

    # Load configuration
    if config is None:
        config = load_gateway_config()

    # Optional stderr handler driven by verbosity
    # verbosity=None (-q): no stderr
    # verbosity=0: WARNING and above
    # verbosity=1 (-v): INFO and above
    # verbosity=2+ (-vv): DEBUG
    if verbosity is not None:
        import sys
        if verbosity >= 2:
            level = logging.DEBUG
        elif verbosity == 1:
            level = logging.INFO
        else:
            level = logging.WARNING
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        # Avoid duplicate handlers
        root = logging.getLogger()
        if not any(h for h in root.handlers if isinstance(h, logging.StreamHandler) and h.stream == sys.stderr):
            root.addHandler(handler)
        root.setLevel(level)

    runner = GatewayRunner(config=config)
    await runner.start()

    try:
        await runner.wait_for_shutdown()
    except asyncio.CancelledError:
        pass

    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    """Main entry point for the gateway CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="MimirAether Gateway - Multi-platform message integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace any existing gateway instance",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=None,
        help="Increase verbosity (-v=INFO, -vv=DEBUG)",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress stderr output",
    )
    parser.add_argument(
        "subcommand",
        nargs="?",
        choices=["start", "stop", "restart", "status"],
        default="start",
        help="Subcommand (default: start)",
    )

    args = parser.parse_args()

    if args.quiet:
        verbosity = None
    else:
        verbosity = args.verbose

    # Register signal handlers
    def _sigint_handler():
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, lambda s, f: _sigint_handler())
    signal.signal(signal.SIGTERM, lambda s, f: _sigint_handler())

    if args.subcommand == "stop":
        print("Use 'openclaw gateway stop' to stop the running gateway")
        return

    try:
        success = asyncio.run(start_gateway(replace=args.replace, verbosity=verbosity))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.error("Gateway failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
