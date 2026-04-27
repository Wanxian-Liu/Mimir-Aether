"""MimCore - MimirAether Core Compatibility Layer

Re-exports from hermes_* modules under the mimcore namespace.
This provides a clean separation between Hermes-origin code and
MimirAether-specific implementations.

Usage:
    from mimcore.auth import ...
    from mimcore.config import ...
    from mimcore.constants import ...
    from mimcore.gateway.session import SessionDB
"""

# Lazy re-exports to avoid circular imports
__all__ = [
    "auth",
    "config", 
    "constants",
    "gateway",
]
