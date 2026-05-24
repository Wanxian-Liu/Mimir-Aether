"""
RouterMixin — message routing, command handling, media delivery.

Secondary split (P1-LONG-GOD): composition of gateway/router/* mixins.
"""
from __future__ import annotations

from gateway.router.inbound_prep_mixin import InboundPrepMixin
from gateway.router.core_route_mixin import CoreRouteMixin
from gateway.router.agent_route_mixin import AgentRouteMixin
from gateway.router.session_commands_mixin import SessionCommandsMixin
from gateway.router.model_commands_mixin import ModelCommandsMixin
from gateway.router.media_mixin import MediaMixin
from gateway.router.tuning_commands_mixin import TuningCommandsMixin
from gateway.router.admin_commands_mixin import AdminCommandsMixin
from gateway._shared import (
    _load_gateway_config,
    _platform_config_key,
    _resolve_gateway_model,
    _resolve_runtime_agent_kwargs,
)
from gateway.home_paths import _hermes_home

__all__ = [
    "RouterMixin",
    "_hermes_home",
    "_load_gateway_config",
    "_platform_config_key",
    "_resolve_gateway_model",
    "_resolve_runtime_agent_kwargs",
]


class RouterMixin(AdminCommandsMixin, TuningCommandsMixin, MediaMixin, ModelCommandsMixin, SessionCommandsMixin, AgentRouteMixin, CoreRouteMixin, InboundPrepMixin):
    """Message routing: inbound processing, command dispatch, media delivery.

    Designed to be mixed into GatewayRunner.
    """
