"""M5: checkpoint persistence seam for ``run_conversation`` resume/save/clear.

Production: ``MimirAetherAgent`` holds a ``CheckpointPersistencePort`` (default
``_BuiltinCheckpointBackend`` delegating to ``checkpoint_manager.get_checkpoint_manager()``).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class CheckpointPersistencePort(Protocol):
    """Load/save/clear JSON checkpoints (compatible with ``CheckpointManager`` API)."""

    def load_checkpoint(self, task_id: str) -> Optional[Any]:
        ...

    def save_checkpoint(
        self,
        task_id: str,
        state: Dict[str, Any],
        current_step: int = 0,
        next_action: str = "继续执行",
    ) -> bool:
        ...

    def clear_checkpoint(self, task_id: str) -> bool:
        ...
