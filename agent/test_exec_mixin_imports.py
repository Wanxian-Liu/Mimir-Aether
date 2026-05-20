"""exec_mixin module-level imports after d4 split (IR-20260520)."""

from __future__ import annotations

import functools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_exec_mixin_registry_and_executor_bindings() -> None:
    import agent.exec_mixin as em

    assert hasattr(functools, "partial")
    assert em._tool_executor is not None
    assert hasattr(em._tool_registry_module.registry, "dispatch")
    assert hasattr(em._tool_registry_module.registry, "_tools")
