"""Backward-compatibility wrapper — delegates to mimir_constants.

All constants, path helpers, and environment-detection functions have been
migrated to ``mimir_constants``.  This module exists so that vendored
``hermes_cli`` code (which still imports ``hermes_constants``) continues
to work during the transition.
"""

from mimir_constants import *  # noqa: F401, F403, E402
