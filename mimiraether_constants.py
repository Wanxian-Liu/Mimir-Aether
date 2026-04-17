
"""MimirAether专用常量 - 从hermes_constants改编"""

import os
from pathlib import Path

def get_mimiraether_home() -> Path:
    """Return the MimirAether独立home目录."""
    return Path(os.getenv("MIMIRAETHER_HOME", Path.home() / ".openclaw/mimir-aether"))

# Hermes兼容别名
def get_hermes_home() -> Path:
    """Alias for get_mimiraether_home for compatibility."""
    return get_mimiraether_home()

HERMES_HOME = get_mimiraether_home()
SKILLS_DIR = HERMES_HOME / "skills"
