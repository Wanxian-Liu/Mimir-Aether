#!/usr/bin/env python3
"""List direct hermes_cli imports under the MimirAether repo (for closure audits)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    skip = {"hermes_cli", ".git", "__pycache__", ".venv", "node_modules", "mimir_vendor"}
    hits: list[tuple[Path, int, str]] = []
    for path in root.rglob("*.py"):
        if any(part in skip for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "hermes_cli" or alias.name.startswith("hermes_cli."):
                        hits.append((path, node.lineno, f"import {alias.name}"))
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module == "hermes_cli" or node.module.startswith("hermes_cli.")
                ):
                    names = ", ".join(a.name for a in node.names)
                    hits.append((path, node.lineno, f"from {node.module} import {names}"))
    hits.sort(key=lambda x: (str(x[0]), x[1]))
    for p, lineno, line in hits:
        rel = p.relative_to(root)
        print(f"{rel}:{lineno}: {line}")
    print(f"# total: {len(hits)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
