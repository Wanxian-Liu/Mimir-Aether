"""Shared gateway restart constants and parsing helpers."""

# EX_TEMPFAIL from sysexits.h — used to ask the service manager to restart
# the gateway after a graceful drain/reload path completes.
GATEWAY_SERVICE_RESTART_EXIT_CODE = 75

# Default drain timeout for graceful gateway restart (in seconds)
DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT = 60.0

# Sentinel for "agent creation is pending" — used as a placeholder in
# _running_agents dict to prevent duplicate session launches.
_AGENT_PENDING_SENTINEL = object()


def parse_restart_drain_timeout(raw: object) -> float:
    """Parse a configured drain timeout, falling back to the shared default."""
    try:
        value = float(raw) if str(raw or "").strip() else DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT
    except (TypeError, ValueError):
        return DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT
    return max(0.0, value)
