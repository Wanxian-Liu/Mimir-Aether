"""
Platform-agnostic tool dispatch context (MW-03).

Thin dataclass that captures the minimal context needed for tool dispatch:
  - session_id: unique session identifier
  - channel: runtime channel ('cli' | 'feishu' | 'api')
  - workspace_root: file system root for the runtime

No gateway types, no lark/openclaw imports. Pure data.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ToolDispatchContext:
    """Immutable context for tool dispatch — no platform coupling.

    Attributes:
        session_id: Unique session identifier (str, not gateway type).
        channel: Runtime channel. One of 'cli', 'feishu', 'api'.
        workspace_root: Absolute path to the workspace root directory.
    """

    session_id: str
    channel: str = "cli"
    workspace_root: str = field(default_factory=lambda: str(Path.cwd()))

    def __post_init__(self) -> None:
        """Validate channel and workspace_root."""
        if self.channel not in ("cli", "feishu", "api"):
            raise ValueError(f"Unknown channel: {self.channel!r}")
        if not os.path.isabs(self.workspace_root):
            raise ValueError(f"workspace_root must be absolute: {self.workspace_root!r}")
