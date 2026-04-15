"""MimirAether专用常量 - 从hermes_constants改编"""

import os
from pathlib import Path

def get_mimiraether_home() -> Path:
    """Return the MimirAether home directory."""
    return Path(os.getenv("MIMIRAETHER_HOME", Path.home() / ".openclaw/mimir-aether"))

def get_skills_dir() -> Path:
    """Return the skills directory."""
    return get_mimiraether_home() / "skills"

HERMES_HOME = get_mimiraether_home()
SKILLS_DIR = HERMES_HOME / "skills"
