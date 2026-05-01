"""
MessageRouter - Routes messages to appropriate handlers

Features:
- Command routing
- Platform-specific routing
- Middleware chain
- Error handling
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

from .message import Message, MessageType
from .session import Session, SessionManager


# Handler type: async function that takes a Message and Session
MessageHandler = Callable[[Message, Session], Coroutine[Any, Any, None]]

# Middleware type: async function that wraps handler execution
Middleware = Callable[[Message, Session, MessageHandler], Coroutine[Any, Any, None]]


@dataclass
class Route:
    """Represents a registered route."""

    pattern: str  # Regex pattern or command name
    handler: MessageHandler
    platform: Optional[str] = None  # None = all platforms
    message_type: Optional[MessageType] = None  # None = all types


class MessageRouter:
    """
    Routes incoming messages to appropriate handlers.

    Features:
    - Command-based routing (e.g., /start, /help)
    - Pattern-based routing with regex
    - Platform-specific routes
    - Message type routing
    - Middleware chain
    - Fallback handler
    """

    def __init__(self, session_manager: SessionManager):
        """
        Initialize MessageRouter.

        Args:
            session_manager: Session manager for session handling
        """
        self.session_manager = session_manager
        self.logger = logging.getLogger("gateway.router")

        # Registered routes
        self._routes: list[Route] = []
        # Command aliases (command -> canonical command)
        self._command_aliases: dict[str, str] = {}
        # Fallback handler
        self._fallback_handler: Optional[MessageHandler] = None
        # Default handler for unhandled commands
        self._default_handler: Optional[MessageHandler] = None
        # Middleware chain
        self._middleware: list[Middleware] = []
        # Platform adapters
        self._platforms: dict[str, Any] = {}

    def register_platform(self, name: str, adapter: Any) -> None:
        """
        Register a platform adapter.

        Args:
            name: Platform name (telegram, discord, feishu)
            adapter: Platform adapter instance
        """
        self._platforms[name] = adapter
        self.logger.debug(f"Registered platform: {name}")

    def command(
        self,
        pattern: str,
        handler: MessageHandler,
        platform: Optional[str] = None,
    ) -> Callable[[MessageHandler], MessageHandler]:
        """
        Decorator to register a command handler.

        Usage:
            @router.command("/start")
            async def handle_start(msg, session):
                ...

        Args:
            pattern: Command pattern (with or without leading /)
            handler: Async handler function
            platform: Optional platform restriction

        Returns:
            Decorator function
        """
        def decorator(h: MessageHandler) -> MessageHandler:
            cmd = pattern.lstrip("/")
            self._routes.append(Route(
                pattern=cmd,
                handler=h,
                platform=platform,
                message_type=MessageType.COMMAND,
            ))
            return h
        return decorator

    def message(
        self,
        pattern: str,
        handler: MessageHandler,
        platform: Optional[str] = None,
        message_type: Optional[MessageType] = None,
    ) -> Callable[[MessageHandler], MessageHandler]:
        """
        Decorator to register a message pattern handler.

        Args:
            pattern: Regex pattern to match against message text
            handler: Async handler function
            platform: Optional platform restriction
            message_type: Optional message type restriction

        Returns:
            Decorator function
        """
        def decorator(h: MessageHandler) -> MessageHandler:
            self._routes.append(Route(
                pattern=pattern,
                handler=h,
                platform=platform,
                message_type=message_type,
            ))
            return h
        return decorator

    def alias(self, alias: str, canonical: str) -> None:
        """
        Register a command alias.

        Args:
            alias: Alias command (without /)
            canonical: Canonical command name
        """
        self._command_aliases[alias.lower()] = canonical.lower()

    def middleware(self, middleware: Middleware) -> Middleware:
        """
        Decorator to register a middleware function.

        Middleware is executed in order before the handler.

        Usage:
            @router.middleware
            async def auth_middleware(msg, session, next_handler):
                if not session.metadata.get("authenticated"):
                    return
                await next_handler(msg, session)

        Args:
            middleware: Middleware function

        Returns:
            Decorator function
        """
        self._middleware.append(middleware)
        return middleware

    def fallback(self, handler: MessageHandler) -> MessageHandler:
        """
        Decorator to register a fallback handler.

        The fallback handler is called when no route matches.

        Args:
            handler: Async handler function

        Returns:
            Decorator function (also sets the handler)
        """
        self._fallback_handler = handler
        return handler

    def default(self, handler: MessageHandler) -> MessageHandler:
        """
        Decorator to register the default handler.

        The default handler is called for regular messages without commands.

        Args:
            handler: Async handler function

        Returns:
            Decorator function
        """
        self._default_handler = handler
        return handler

    async def route(self, message: Message) -> None:
        """
        Route a message to the appropriate handler.

        Args:
            message: Incoming message
        """
        if not message.context:
            self.logger.warning("Message has no context, skipping")
            return

        platform = message.context.platform

        # Get or create session
        session = await self.session_manager.get_or_create_session(message)
        message.session_id = session.id

        # Build handler chain
        handler = self._resolve_handler(message)

        # Wrap with middleware
        for mw in reversed(self._middleware):
            original_handler = handler
            handler = lambda msg, sess, next_h=original_handler: mw(msg, sess, next_h)

        # Execute
        try:
            await handler(message, session)
        except Exception as e:
            self.logger.error(f"Handler error: {e}")
            await self._handle_error(message, session, e)

    def _resolve_handler(self, message: Message) -> MessageHandler:
        """Resolve the appropriate handler for a message."""
        platform = message.context.platform if message.context else None

        for route in self._routes:
            # Platform filter
            if route.platform and route.platform != platform:
                continue

            # Message type filter
            if route.message_type and route.message_type != message.type:
                continue

            # Command match
            if message.type == MessageType.COMMAND and message.command:
                cmd = message.command.lower()
                # Check alias
                cmd = self._command_aliases.get(cmd, cmd)
                # Match
                if cmd == route.pattern.lower():
                    return route.handler

            # Pattern match (regex)
            if route.message_type is None and message.text:
                try:
                    if re.match(route.pattern, message.text, re.IGNORECASE):
                        return route.handler
                except re.error:
                    pass

        # Fall back to default handler for non-commands
        if message.type != MessageType.COMMAND and self._default_handler:
            return self._default_handler

        # Last resort: fallback handler
        if self._fallback_handler:
            return self._fallback_handler

        # No handler found
        async def noop(msg: Message, sess: Session) -> None:
            self.logger.debug(f"No handler for message: {msg.id}")
            pass

        return noop

    async def _handle_error(
        self,
        message: Message,
        session: Session,
        error: Exception,
    ) -> None:
        """Handle handler errors."""
        self.logger.error(
            f"Error processing message {message.id}: {error}",
            exc_info=True,
        )

    def list_routes(self) -> list[dict[str, Any]]:
        """List all registered routes."""
        return [
            {
                "pattern": r.pattern,
                "platform": r.platform,
                "message_type": r.message_type.value if r.message_type else None,
            }
            for r in self._routes
        ]

    async def get_stats(self) -> dict[str, Any]:
        """Get router statistics."""
        return {
            "routes_count": len(self._routes),
            "middleware_count": len(self._middleware),
            "platforms": list(self._platforms.keys()),
            "routes": self.list_routes(),
        }
