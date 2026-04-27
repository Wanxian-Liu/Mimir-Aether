"""
# TODO-自研: 事件钩子系统
# 来源: mimir-aether/gateway/hooks.py
# 改造点:
#   1. 移除 hermes_cli.config 依赖 → 适配 OpenClaw 配置结构
#   2. hooks 目录路径改为 ~/.openclaw/hooks
#   3. builtin_hooks 路径需适配 OpenClaw 结构
"""

import asyncio
import importlib.util
import logging
from typing import Any, Callable, Dict, List, Optional

import yaml

# TODO-自研: from hermes_cli.config import get_hermes_home
# TODO-自研: hooks 目录改为 ~/.openclaw/hooks

logger = logging.getLogger(__name__)

# TODO-自研: HOOKS_DIR = get_hermes_home() / "hooks"
HOOKS_DIR = None  # TODO-自研: 初始化为 Path.home() / ".openclaw" / "hooks"


class HookRegistry:
    """
    Discovers, loads, and fires event hooks.

    Usage:
        registry = HookRegistry()
        registry.discover_and_load()
        await registry.emit("agent:start", {"platform": "telegram", ...})
    """

    def __init__(self):
        # event_type -> [handler_fn, ...]
        self._handlers: Dict[str, List[Callable]] = {}
        self._loaded_hooks: List[dict] = []  # metadata for listing

    @property
    def loaded_hooks(self) -> List[dict]:
        """Return metadata about all loaded hooks."""
        return list(self._loaded_hooks)

    def _register_builtin_hooks(self) -> None:
        """Register built-in hooks that are always active."""
        # TODO-自研: 需要适配 OpenClaw 的 builtin_hooks 路径
        try:
            # from gateway.builtin_hooks.boot_md import handle as boot_md_handle
            # self._handlers.setdefault("gateway:startup", []).append(boot_md_handle)
            # self._loaded_hooks.append({
            #     "name": "boot-md",
            #     "description": "Run ~/.openclaw/BOOT.md on gateway startup",
            #     "events": ["gateway:startup"],
            #     "path": "(builtin)",
            # })
            pass
        except Exception as e:
            print(f"[hooks] Could not load built-in boot-md hook: {e}", flush=True)

    def discover_and_load(self) -> None:
        """
        Scan the hooks directory for hook directories and load their handlers.

        Also registers built-in hooks that are always active.

        Each hook directory must contain:
          - HOOK.yaml with at least 'name' and 'events' keys
          - handler.py with a top-level 'handle' function (sync or async)
        """
        self._register_builtin_hooks()

        # TODO-自研: 初始化 HOOKS_DIR
        global HOOKS_DIR
        if HOOKS_DIR is None:
            from pathlib import Path
            HOOKS_DIR = Path.home() / ".openclaw" / "hooks"

        if not HOOKS_DIR.exists():
            return

        for hook_dir in sorted(HOOKS_DIR.iterdir()):
            if not hook_dir.is_dir():
                continue

            manifest_path = hook_dir / "HOOK.yaml"
            handler_path = hook_dir / "handler.py"

            if not manifest_path.exists() or not handler_path.exists():
                continue

            try:
                manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                if not manifest or not isinstance(manifest, dict):
                    print(f"[hooks] Skipping {hook_dir.name}: invalid HOOK.yaml", flush=True)
                    continue

                hook_name = manifest.get("name", hook_dir.name)
                events = manifest.get("events", [])
                if not events:
                    print(f"[hooks] Skipping {hook_name}: no events declared", flush=True)
                    continue

                # Dynamically load the handler module
                # TODO-自研: 移除 mimir 前缀，使用 openclaw 前缀
                spec = importlib.util.spec_from_file_location(
                    f"gateway_hook_{hook_name}", handler_path
                )
                if spec is None or spec.loader is None:
                    print(f"[hooks] Skipping {hook_name}: could not load handler.py", flush=True)
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                handle_fn = getattr(module, "handle", None)
                if handle_fn is None:
                    print(f"[hooks] Skipping {hook_name}: no 'handle' function found", flush=True)
                    continue

                # Register the handler for each declared event
                for event in events:
                    self._handlers.setdefault(event, []).append(handle_fn)

                self._loaded_hooks.append({
                    "name": hook_name,
                    "description": manifest.get("description", ""),
                    "events": events,
                    "path": str(hook_dir),
                })

                print(f"[hooks] Loaded hook '{hook_name}' for events: {events}", flush=True)

            except Exception as e:
                print(f"[hooks] Error loading hook {hook_dir.name}: {e}", flush=True)

    async def emit(self, event_type: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Fire all handlers registered for an event.

        Supports wildcard matching: handlers registered for "command:*" will
        fire for any "command:..." event. Handlers registered for a base type
        like "agent" won't fire for "agent:start" -- only exact matches and
        explicit wildcards.

        Args:
            event_type: The event identifier (e.g. "agent:start").
            context:    Optional dict with event-specific data.
        """
        if context is None:
            context = {}

        # Collect handlers: exact match + wildcard match
        handlers = list(self._handlers.get(event_type, []))

        # Check for wildcard patterns (e.g., "command:*" matches "command:reset")
        if ":" in event_type:
            base = event_type.split(":")[0]
            wildcard_key = f"{base}:*"
            handlers.extend(self._handlers.get(wildcard_key, []))

        for fn in handlers:
            try:
                result = fn(event_type, context)
                # Support both sync and async handlers
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                print(f"[hooks] Error in handler for '{event_type}': {e}", flush=True)
