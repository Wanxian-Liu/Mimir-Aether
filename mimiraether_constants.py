
"""MimirAether专用常量 - 从hermes_constants改编"""

import os
from pathlib import Path

from utils import env_var_enabled

def get_mimiraether_home() -> Path:
    """Return the MimirAether独立home目录."""
    return Path(os.getenv("MIMIRAETHER_HOME", Path.home() / ".openclaw/mimir-aether"))

# Hermes兼容别名
def get_hermes_home() -> Path:
    """Alias for get_mimiraether_home for compatibility."""
    return get_mimiraether_home()

HERMES_HOME = get_mimiraether_home()
SKILLS_DIR = HERMES_HOME / "skills"

def get_config_path() -> Path:
    """Return the path to ``config.yaml`` under MIMIRAETHER_HOME."""
    return get_mimiraether_home() / "config.yaml"


def managed_nous_tools_enabled() -> bool:
    """Return True when the hidden Nous-managed tools feature flag is enabled."""
    return env_var_enabled("HERMES_ENABLE_NOUS_MANAGED_TOOLS")
